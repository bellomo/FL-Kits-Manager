"""Shared test set-up: no network, Qt without a screen, a temporary data folder and a fake game folder (never the
real game, never the user's settings)."""

import os
import socket
import struct
import zlib

import pytest

# Qt draws off screen in tests (CI has no display); set before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# NETWORK-GUARD: all outgoing connections except localhost are refused in tests.
# Installed when pytest loads this file, before any test module is imported.
class NetworkBlocked(OSError):
    pass


_LOCAL_NAMES = {"localhost", "127.0.0.1", "::1", None}
_AF_UNIX = getattr(socket, "AF_UNIX", None)


def _is_local_host(host) -> bool:
    host = host.decode() if isinstance(host, bytes) else host
    return host in _LOCAL_NAMES or str(host).startswith("127.")


def _guard(original):
    def guarded(self, address, *args, **kwargs):
        if self.family != _AF_UNIX and not _is_local_host(address[0]):
            raise NetworkBlocked(f"network access blocked in tests: {address}")
        return original(self, address, *args, **kwargs)

    return guarded


_getaddrinfo = socket.getaddrinfo


def _guarded_getaddrinfo(host, *args, **kwargs):
    if not _is_local_host(host):
        raise NetworkBlocked(f"network access blocked in tests: {host}")
    return _getaddrinfo(host, *args, **kwargs)


socket.socket.connect = _guard(socket.socket.connect)
socket.socket.connect_ex = _guard(socket.socket.connect_ex)
socket.getaddrinfo = _guarded_getaddrinfo


@pytest.fixture(autouse=True)
def no_claude(monkeypatch):
    """the tests never run the real Claude Code: nothing is found, and background work runs at once"""
    from flkm import claude, claude_run, main_window

    def never(*a, **k):
        raise AssertionError("the tests never run the real Claude Code")

    monkeypatch.setattr(claude, "find", lambda saved: None)
    monkeypatch.setattr(claude_run, "account", lambda cli: None)
    monkeypatch.setattr(claude_run, "run_task", never)
    monkeypatch.setattr(main_window, "run_in_thread", lambda work, done, failed: _now(work, done, failed))


def _now(work, done, failed):
    try:
        result = work()
    except Exception as e:  # noqa: BLE001
        failed(str(e))
    else:
        done(result)


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    """a temporary app data folder for every test: the user's real settings and staging are never touched"""
    h = tmp_path / "flkm_home"
    monkeypatch.setenv("FLKM_HOME", str(h))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))  # no real Mod Studio recipe either
    return h


_UTF_FORMATS = {0: ">B", 1: ">b", 2: ">H", 3: ">h", 4: ">I", 5: ">i", 6: ">Q", 7: ">q", 8: ">f"}
_UTF_SIZES = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 8, 7: 8, 8: 4, 0xA: 4, 0xB: 8}


def utf_table(name: str, columns: list[tuple[str, int]], rows: list[dict], constants: dict | None = None) -> bytes:
    """A CRI @UTF table (big endian). columns: (name, type), types 0-8 numbers (u8, s8, u16, s16, u32, s32, u64,
    s64, float), 0xA string, 0xB bytes; every column is stored per row (0x50) unless it is in `constants` (0x30)."""
    constants = constants or {}
    strings = bytearray(b"<NULL>\0")
    blobs = bytearray()
    offsets = {}

    def s(text):
        if text not in offsets:
            offsets[text] = len(strings)
            strings.extend(text.encode() + b"\0")
        return offsets[text]

    def value(t, v):
        if t in _UTF_FORMATS:
            return struct.pack(_UTF_FORMATS[t], v)
        if t == 0xB:
            blobs.extend(v)
            return struct.pack(">II", len(blobs) - len(v), len(v))
        return struct.pack(">I", s(v))  # 0xA

    name_off = s(name)
    schema = bytearray()
    for col, t in columns:
        if col in constants:
            schema += struct.pack(">BI", 0x30 | t, s(col)) + value(t, constants[col])
        else:
            schema += struct.pack(">BI", 0x50 | t, s(col))
    row_cols = [(c, t) for c, t in columns if c not in constants]
    body = b"".join(b"".join(value(t, row[c]) for c, t in row_cols) for row in rows)
    rowlen = sum(_UTF_SIZES[t] for _, t in row_cols)
    rows_off = 24 + len(schema)
    str_off = rows_off + len(body)
    data_off = str_off + len(strings)
    head = struct.pack(">HHIIIHHI", 1, rows_off, str_off, data_off, name_off, len(columns), rowlen, len(rows))
    table = head + schema + body + bytes(strings) + bytes(blobs)
    return b"@UTF" + struct.pack(">I", len(table)) + table


def build_cpk(files: dict[str, bytes], toc: bool = True) -> bytes:
    """A tiny CRI CPK with the given files (path -> data), laid out like the game's: header, TOC, then contents."""
    header_cols = [("TocOffset", 6), ("ContentOffset", 6)]
    toc_cols = [("DirName", 0xA), ("FileName", 0xA), ("FileSize", 4), ("ExtractSize", 4), ("FileOffset", 6)]

    def chunk(magic, table):
        return magic + b"\xff\0\0\0" + struct.pack("<Q", len(table)) + table

    header_len = len(chunk(b"CPK ", utf_table("CpkHeader", header_cols, [{"TocOffset": 0, "ContentOffset": 0}])))
    toc_off = 0x800 if toc else 0
    rows, blobs, pos = [], b"", 0
    for path, data in files.items():
        d, _, f = path.rpartition("/")
        rows.append({"DirName": d, "FileName": f, "FileSize": len(data), "ExtractSize": len(data), "FileOffset": pos})
        blobs += data
        pos += len(data)
    toc_chunk = chunk(b"TOC ", utf_table("CpkTocInfo", toc_cols, rows))
    content_off = toc_off + len(toc_chunk) if toc else 0
    # file offsets are relative to min(content, toc) = toc: shift them past the TOC
    for r in rows:
        r["FileOffset"] += len(toc_chunk)
    toc_chunk = chunk(b"TOC ", utf_table("CpkTocInfo", toc_cols, rows))
    header = chunk(b"CPK ", utf_table("CpkHeader", header_cols, [{"TocOffset": toc_off, "ContentOffset": content_off}]))
    assert len(header) == header_len < 0x800
    if not toc:
        return header
    return header.ljust(toc_off, b"\0") + toc_chunk + blobs


@pytest.fixture
def make_cpk(tmp_path):
    """write a tiny CPK: make_cpk("name.cpk", {"dir/file": b"data"}) -> path"""

    def make(name, files, toc=True):
        p = tmp_path / name
        p.write_bytes(build_cpk(files, toc=toc))
        return p

    return make


def dxt1_block(rgb565: int) -> bytes:
    """a 4x4 DXT1/BC1 block of one colour"""
    return struct.pack("<HHI", rgb565, rgb565, 0)


def dxt5_block(rgb565: int, alpha: int = 255) -> bytes:
    """a 4x4 DXT5/BC3 block of one colour and one alpha"""
    return struct.pack("<BB", alpha, alpha) + b"\0" * 6 + dxt1_block(rgb565)


def bc7_block(r: int, g: int, b: int, a: int = 255) -> bytes:
    """a 4x4 BC7 mode 6 block of one colour: both endpoints the same, every index 0 (channels must be odd: 7 bits
    plus a p-bit of 1)"""
    bits, n = 1 << 6, 7  # mode 6
    for value in (r, r, g, g, b, b, a, a):
        bits |= (value >> 1) << n
        n += 7
    bits |= 1 << n | 1 << (n + 1)  # p-bits
    return bits.to_bytes(16, "little")


def build_ftex(fmt: int, width: int, height: int, mips: list[bytes], chunk: int = 0x4000, raw: bool = False) -> bytes:
    """an FTEX texture (largest mip first in `mips`), each mip split in zlib chunks like the game's files"""
    body_start = 0x40 + 16 * len(mips)
    stored = []
    for index, mip in enumerate(mips):
        pieces = [mip[i : i + chunk] for i in range(0, len(mip), chunk)] or [b""]
        # like the game's files: a chunk that zlib does not make smaller is stored as it is
        blobs = [p if raw or len(zlib.compress(p)) >= len(p) else zlib.compress(p) for p in pieces]
        chunk_table, pos = b"", 8 * len(blobs)
        for piece, blob in zip(pieces, blobs):
            chunk_table += struct.pack("<HHI", len(blob) & 0xFFFF, len(piece) & 0xFFFF, pos | (0x80000000 * raw))
            pos += len(blob)
        stored.append((index, mip, chunk_table + b"".join(blobs), len(blobs)))
    table, data = b"", b""
    for index, mip, blob, nchunks in reversed(stored):  # data from the smallest mip to the largest
        stored_at = body_start + len(data)
        data += blob + b"\0" * (-len(blob) % 8)
        table = struct.pack("<IIIBBH", stored_at, len(mip), len(blob), index, 0, nchunks) + table
    head = b"FTEX" + struct.pack("<fHHHH", 2.03, fmt, width, height, 1) + bytes([len(mips)])
    return head.ljust(0x40, b"\0") + table + data


def wesys(table: bytes) -> bytes:
    """a pesdb table packed like the game's: 16-byte WESYS header, then zlib"""
    packed = zlib.compress(table)
    return b"\x00\x01\x01WESYS" + struct.pack("<II", len(packed), len(table)) + packed


def team_record(team_id: int, name: str, abbr: str) -> bytes:
    """a 1532-byte Team.bin record: id at 8, English name at 368 (70 bytes), abbreviation at 882"""
    r = bytearray(1532)
    struct.pack_into("<I", r, 8, team_id)
    r[368 : 368 + 70] = name.encode().ljust(70, b"\0")
    r[882 : 882 + 10] = abbr.encode().ljust(10, b"\0")
    return bytes(r)


def competition_record(comp_id: int, name: str) -> bytes:
    """a 36-byte Competition.bin record: 0x64c8 at 0, id low byte at 5 and high byte at 7, name at 8"""
    r = bytearray(36)
    r[0:2] = b"\x64\xc8"
    r[5], r[7] = comp_id & 0xFF, comp_id >> 8
    r[8:36] = name.encode().ljust(28, b"\0")
    return bytes(r)


def entry_record(team_id: int, comp_id: int, position: int = 0) -> bytes:
    """a 12-byte CompetitionEntry.bin record: team, an unknown u32, then competition and position packed in a u32"""
    return struct.pack("<III", team_id, 0, (comp_id & 0xFF) | position << 8 | (comp_id >> 8) << 24)


def regulation_record(code: str, english: str, other: str = "", low_id: int = 0) -> bytes:
    """a 2352-byte CompetitionRegulation.bin record: 20-byte header, names in 115-byte language slots (9 from 20, the
    English one at 480; more from 1087), the competition's code name at 1055 (32 bytes); the low byte of the
    competition's id at 8"""
    r = bytearray(2352)
    r[8] = low_id
    for k in range(9):
        name = english if k == 4 else ("" if k == 3 else other)
        r[20 + 115 * k : 20 + 115 * (k + 1)] = name.encode().ljust(115, b"\0")
    r[1055 : 1055 + 32] = code.encode().ljust(32, b"\0")
    return bytes(r)


def country_record(country_id: int, name: str, continent: int, confederation: int) -> bytes:
    """a 1420-byte Country.bin record: id in the low 10 bits at 0, continent at 4, confederation at 5, upper case
    English name at 288"""
    r = bytearray(1420)
    struct.pack_into("<I", r, 0, country_id | 0x5000)
    r[4], r[5] = continent, confederation
    r[288 : 288 + 70] = name.encode().ljust(70, b"\0")
    return bytes(r)


@pytest.fixture
def game(tmp_path):
    """an empty fake game folder; tests add the files they need (sider.ini, map.txt, tiny CPK/FTEX)"""
    g = tmp_path / "game"
    (g / "SiderAddons").mkdir(parents=True)
    return g


def shirt_photo(
    body=(200, 30, 40),
    sleeve=None,
    collar=(240, 200, 0),
    bg=(255, 255, 255),
    size=400,
    stripes=(),
    logos=(),
):
    """A flat product photo of a shirt (a PIL image): torso, sleeves and collar on a plain background, no real kit.
    Fractions of the image: torso x 0.30-0.70 y 0.15-0.90, sleeves x 0.10-0.30 / 0.70-0.90 y 0.15-0.375, collar x
    0.425-0.575 y 0.15-0.18. stripes: [(colour, x0, x1)] vertical bands down the torso below the collar; logos:
    [(colour, (x0, y0, x1, y1))] solid boxes."""
    import numpy as np
    from PIL import Image

    a = np.zeros((size, size, 3), np.uint8)
    a[:] = bg

    def box(x0, y0, x1, y1, colour):
        a[int(y0 * size) : int(y1 * size), int(x0 * size) : int(x1 * size)] = colour

    box(0.30, 0.15, 0.70, 0.90, body)
    box(0.10, 0.15, 0.30, 0.375, sleeve or body)
    box(0.70, 0.15, 0.90, 0.375, sleeve or body)
    for colour, x0, x1 in stripes:
        box(x0, 0.18, x1, 0.90, colour)
    box(0.425, 0.15, 0.575, 0.18, collar)
    for colour, (x0, y0, x1, y1) in logos:
        box(x0, y0, x1, y1, colour)
    return Image.fromarray(a)


def buttons_without_tooltip(widget) -> list[str]:
    """The text of every button in widget (hidden ones too) that has no tooltip: every button of the app explains what
    it does when the mouse is over it."""
    from PySide6.QtWidgets import QPushButton

    return [b.text() for b in widget.findChildren(QPushButton) if not b.toolTip().strip()]
