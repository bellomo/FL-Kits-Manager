"""Writing FTEX textures (layout in ftex.py): from blocks, from an image, from a DDS file, and the texture of a kit from
the file the user chooses.

- An image becomes DXT5 with every mip down to 1x1 (mips under 4x4 still take a whole block), like the game's kits
  (2048x2048: 12 mips). The DXT5 blocks come from Pillow's DDS encoder.
- A DDS keeps its blocks (DXT1, DXT5/BC3, BC7) when it has every mip; else it is decoded and encoded again.
- The header of the kit being replaced can be kept: only format, size and mip count change (rebuilding the game's
  files this way works in the game).
"""

import io
import struct
import zlib
from pathlib import Path

from PIL import Image

from flkm.game import ftex
from flkm.game.ftex import BC7, DXT1, DXT5, FtexError

CHUNK = 0x4000  # the game's files keep each mip in zlib chunks of 16 KB
KIT_SIDES = (256, 512, 1024, 2048, 4096)
_FOURCC = {b"DXT1": DXT1, b"DXT5": DXT5}
_DXGI = {71: DXT1, 72: DXT1, 77: DXT5, 78: DXT5, 98: BC7, 99: BC7}  # BC1, BC3, BC7 (UNORM and SRGB)
_DDS_MIPS = 0x20000  # DDS header flag: the mip count is set


def build(fmt: int, width: int, height: int, mips: list[bytes], header: bytes | None = None) -> bytes:
    """an FTEX texture from the blocks of each mip (largest first); header: the 0x40 bytes of a texture to keep"""
    body_start = 0x40 + 16 * len(mips)
    stored = []
    for index, mip in enumerate(mips):
        pieces = [mip[i : i + CHUNK] for i in range(0, len(mip), CHUNK)] or [b""]
        blobs = [zlib.compress(p) if len(zlib.compress(p)) < len(p) else p for p in pieces]
        chunk_table, pos = b"", 8 * len(blobs)
        for piece, blob in zip(pieces, blobs):
            raw = 0x80000000 if blob is piece else 0
            chunk_table += struct.pack("<HHI", len(blob) & 0xFFFF, len(piece) & 0xFFFF, pos | raw)
            pos += len(blob)
        stored.append((index, mip, chunk_table + b"".join(blobs), len(blobs)))
    table, data = b"", b""
    for index, mip, blob, chunks in reversed(stored):  # data from the smallest mip to the largest, as the game's
        table = struct.pack("<IIIBBH", body_start + len(data), len(mip), len(blob), index, 0, chunks) + table
        data += blob + b"\0" * (-len(blob) % 8)
    if header:
        head = bytearray(header[:0x40])
    else:
        head = bytearray((b"FTEX" + struct.pack("<fHHHH", 2.03, 0, 0, 0, 1)).ljust(0x40, b"\0"))
    struct.pack_into("<HHH", head, 0x08, fmt, width, height)
    head[0x10] = len(mips)
    return bytes(head) + table + data


def _dxt5(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, "DDS", pixel_format="DXT5")
    return buf.getvalue()[128:]  # the blocks, without the DDS header


def encode(image: Image.Image, header: bytes | None = None) -> bytes:
    """a square image with a power-of-two side as DXT5 with every mip"""
    width, height = image.size
    if width != height:
        raise FtexError(f"The image must be square: it is {width}x{height} pixels.")
    if width < 4 or width & (width - 1):
        raise FtexError(f"The image side must be a power of two (4, 8, ..., 2048, 4096): it is {width} pixels.")
    rgba = image.convert("RGBA")
    mips, size = [], width
    while size >= 1:
        mip = rgba if size == width else rgba.resize((size, size), Image.LANCZOS)
        mips.append(_dxt5(mip if size >= 4 else mip.resize((4, 4), Image.NEAREST)))
        size //= 2
    return build(DXT5, width, width, mips, header)


def from_dds(data: bytes, header: bytes | None = None) -> bytes:
    if data[:4] != b"DDS " or len(data) < 128:
        raise FtexError("This is not a DDS file.")
    flags, height, width = struct.unpack_from("<III", data, 8)
    count = max(1, struct.unpack_from("<I", data, 28)[0]) if flags & _DDS_MIPS else 1
    fourcc, start = data[84:88], 128
    if fourcc == b"DX10":
        dxgi = struct.unpack_from("<I", data, 128)[0]
        fmt, start = _DXGI.get(dxgi), 148
        if fmt is None:
            raise FtexError(f"DDS format {dxgi} is not supported: use DXT1, DXT5 or BC7.")
    else:
        fmt = _FOURCC.get(fourcc)
        if fmt is None:
            raise FtexError(f"DDS format {fourcc.decode('ascii', 'replace')} is not supported: use DXT1, DXT5 or BC7.")
    if count < max(width, height).bit_length():  # not every mip: decode it and make them
        try:
            image = Image.open(io.BytesIO(data))
            image.load()
        except (OSError, ValueError) as e:
            raise FtexError(f"The DDS file cannot be read: {e}") from e
        return encode(image, header)
    block = 8 if fmt == DXT1 else 16
    mips, pos = [], start
    for i in range(count):
        size = max(1, ((width >> i) + 3) // 4) * max(1, ((height >> i) + 3) // 4) * block
        if pos + size > len(data):
            raise FtexError("The DDS file is too short for its size and mips.")
        mips.append(data[pos : pos + size])
        pos += size
    return build(fmt, width, height, mips, header)


def _check_kit(width: int, height: int) -> None:
    if width != height:
        raise FtexError(f"A kit texture must be square: this one is {width}x{height} pixels.")
    if width not in KIT_SIDES:
        raise FtexError(f"A kit texture must be 256, 512, 1024, 2048 or 4096 pixels wide: this one is {width}.")


def kit_texture(path: Path, header: bytes | None = None) -> bytes:
    """the FTEX texture of a kit from an .ftex (as it is), .png or .dds file; header: the kit it replaces"""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".ftex":
        data = path.read_bytes()
        ftex.parse(data)
        return data
    if suffix == ".png":
        try:
            image = Image.open(path)
            image.load()
        except (OSError, ValueError) as e:
            raise FtexError(f"{path.name} cannot be read as an image: {e}") from e
        _check_kit(*image.size)
        return encode(image, header)
    if suffix == ".dds":
        out = from_dds(path.read_bytes(), header)
        tex = ftex.parse(out)
        _check_kit(tex.width, tex.height)
        return out
    raise FtexError("Choose an .ftex, .png or .dds file.")
