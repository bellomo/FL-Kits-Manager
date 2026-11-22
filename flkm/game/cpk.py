"""CRI CPK archives (Data/*.cpk, download/*.cpk): list and read files. READ ONLY: the app never writes a CPK.

The game's CPKs are not encrypted and their files are stored uncompressed; a CRILAYLA-compressed file is refused.
"""

import struct
from dataclasses import dataclass
from pathlib import Path


class CpkError(ValueError):
    pass


@dataclass(frozen=True)
class Entry:
    path: str  # folders separated by "/"
    offset: int  # from the start of the archive
    size: int
    extract_size: int


def _value(buf: bytes, t: int, pos: int, strings: int, data: int):
    """One @UTF value of type t at pos -> (value, bytes used)."""
    if t in (0, 1):
        return struct.unpack_from(">B" if t == 0 else ">b", buf, pos)[0], 1
    if t in (2, 3):
        return struct.unpack_from(">H" if t == 2 else ">h", buf, pos)[0], 2
    if t in (4, 5):
        return struct.unpack_from(">I" if t == 4 else ">i", buf, pos)[0], 4
    if t in (6, 7):
        return struct.unpack_from(">Q" if t == 6 else ">q", buf, pos)[0], 8
    if t == 8:
        return struct.unpack_from(">f", buf, pos)[0], 4
    if t == 0xA:
        start = strings + struct.unpack_from(">I", buf, pos)[0]
        return buf[start : buf.index(b"\0", start)].decode("utf-8", "replace"), 4
    if t == 0xB:
        off, n = struct.unpack_from(">II", buf, pos)
        return buf[data + off : data + off + n], 8
    raise CpkError(f"unknown @UTF column type {t}")


def parse_utf(buf: bytes) -> list[dict]:
    """A CRI @UTF table (big endian) -> one dict per row."""
    if buf[:4] != b"@UTF":
        raise CpkError("@UTF table not found (the archive may be encrypted)")
    base = 8
    _, rows_off, str_off, data_off, _, ncol, rowlen, nrows = struct.unpack_from(">HHIIIHHI", buf, base)
    strings, data = base + str_off, base + data_off
    columns, pos = [], base + 24
    for _ in range(ncol):
        flags, name_off = struct.unpack_from(">BI", buf, pos)
        pos += 5
        storage, t = flags & 0xF0, flags & 0x0F
        constant = None
        if storage in (0x30, 0x70):
            constant, n = _value(buf, t, pos, strings, data)
            pos += n
        name = buf[strings + name_off : buf.index(b"\0", strings + name_off)].decode("utf-8", "replace")
        columns.append((name, storage, t, constant))
    rows = []
    for r in range(nrows):
        p = base + rows_off + r * rowlen
        row = {}
        for name, storage, t, constant in columns:
            if storage == 0x50:
                row[name], n = _value(buf, t, p, strings, data)
                p += n
            else:
                row[name] = constant
        rows.append(row)
    return rows


def _chunk(f, offset: int, magic: bytes) -> list[dict]:
    f.seek(offset)
    head = f.read(16)
    if head[:4] != magic:
        raise CpkError(f"{magic.decode().strip()} table not found at 0x{offset:x}")
    (size,) = struct.unpack_from("<Q", head, 8)
    return parse_utf(f.read(size))


class Cpk:
    def __init__(self, path: Path):
        self.path = Path(path)
        with open(self.path, "rb") as f:
            header = _chunk(f, 0, b"CPK ")[0]
            toc = header.get("TocOffset") or 0
            content = header.get("ContentOffset") or toc
            self.entries: list[Entry] = []
            if toc:
                shift = min(content, toc)
                for r in _chunk(f, toc, b"TOC "):
                    folder = (r.get("DirName") or "").replace("\\", "/")
                    path = f"{folder}/{r['FileName']}" if folder else r["FileName"]
                    extract = r.get("ExtractSize") or r["FileSize"]
                    self.entries.append(Entry(path, r["FileOffset"] + shift, r["FileSize"], extract))
        self._by_path = {e.path: e for e in self.entries}

    def get(self, path: str) -> Entry | None:
        return self._by_path.get(path)

    def read(self, path: str) -> bytes:
        entry = self._by_path[path]
        with open(self.path, "rb") as f:
            f.seek(entry.offset)
            data = f.read(entry.size)
        if entry.size != entry.extract_size or data[:8] == b"CRILAYLA":
            raise CpkError(f"CRILAYLA-compressed file, not supported: {path}")
        return data
