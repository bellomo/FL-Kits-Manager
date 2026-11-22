"""FTEX textures of the Fox Engine (kits, numbers, names), read and decoded to RGBA.

Layout: 0x40-byte header ("FTEX", u16 format at 0x08, u16 width 0x0A, u16 height 0x0C, u8 mip count 0x10), then a
16-byte entry per mip (u32 offset, u32 size, u32 stored size, u8 mip index, u8, u16 chunk count). Each mip starts with
8-byte chunk entries (u16 stored size, u16 size, u32 offset from the mip; bit 31 = stored uncompressed), then the
zlib chunks of up to 64 KB (a size of 0 means 64 KB).
"""

import io
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

DXT1, DXT5, BC7 = 2, 4, 11
_FOURCC = {DXT1: b"DXT1", DXT5: b"DXT5"}
_DXGI_BC7 = 98


class FtexError(ValueError):
    pass


@dataclass(frozen=True)
class Mip:
    index: int  # 0 = full size
    offset: int
    size: int
    stored_size: int
    chunks: int


@dataclass
class Ftex:
    format: int
    width: int
    height: int
    mips: list[Mip]
    data: bytes


def parse(data: bytes) -> Ftex:
    if data[:4] != b"FTEX":
        raise FtexError("not an FTEX texture")
    fmt, width, height = struct.unpack_from("<HHH", data, 0x08)
    mips = []
    for i in range(data[0x10]):
        offset, size, stored, index, _, chunks = struct.unpack_from("<IIIBBH", data, 0x40 + 16 * i)
        mips.append(Mip(index, offset, size, stored, chunks))
    return Ftex(fmt, width, height, mips, data)


def load(path: Path) -> Ftex:
    return parse(Path(path).read_bytes())


def mip_data(tex: Ftex, index: int = 0) -> bytes:
    """the block data of one mip, chunks joined and uncompressed"""
    mip = next((m for m in tex.mips if m.index == index), None)
    if mip is None:
        raise FtexError(f"mip {index} not in the texture")
    out = []
    for c in range(mip.chunks):
        stored, size, offset = struct.unpack_from("<HHI", tex.data, mip.offset + 8 * c)
        raw, offset = offset & 0x80000000, offset & 0x7FFFFFFF
        size = size or 0x10000
        blob = tex.data[mip.offset + offset : mip.offset + offset + (stored or 0x10000)]
        out.append(blob if raw or stored == size else zlib.decompress(blob))
    return b"".join(out)


def _dds_header(fmt: int, width: int, height: int) -> bytes:
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000  # caps, height, width, pixel format, linear size
    fourcc = _FOURCC.get(fmt, b"DX10")
    pixel_format = struct.pack("<II4s5I", 32, 0x4, fourcc, 0, 0, 0, 0, 0)
    head = struct.pack("<4s7I", b"DDS ", 124, flags, height, width, width * height, 0, 1)
    head += b"\0" * 44 + pixel_format + struct.pack("<5I", 0x1000, 0, 0, 0, 0)
    if fourcc == b"DX10":
        head += struct.pack("<5I", _DXGI_BC7, 3, 0, 1, 0)
    return head


def to_image(tex: Ftex, mip: int = 0, opaque: bool = False) -> Image.Image:
    """one mip as an RGBA image (mip 1, 2, ... are half, a quarter, ... of the size: quick previews). opaque: alpha
    set to 255, for kit textures, whose alpha the game does not use as transparency (BC7 kits of Mod Studio keep it
    near 0)."""
    if tex.format not in (DXT1, DXT5, BC7):
        raise FtexError(f"texture format {tex.format} not supported")
    width, height = max(4, tex.width >> mip), max(4, tex.height >> mip)
    dds = _dds_header(tex.format, width, height) + mip_data(tex, mip)
    image = Image.open(io.BytesIO(dds)).convert("RGBA")
    if opaque:
        image.putalpha(255)
    return image
