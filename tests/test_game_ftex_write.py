"""Writing FTEX textures: from an image (DXT5, every mip down to 1x1 like the game's kits), from a DDS file (its blocks
kept when it has every mip, else decoded and encoded again), and from the file the user chooses for a kit (.ftex,
.png or .dds; square, 256 to 4096 pixels). The header of the kit being replaced can be kept, as the game's own tool
chain does: the rebuilt file then differs from the game's only in the texture."""

import io
import struct

import pytest
from PIL import Image

from conftest import bc7_block, build_ftex, dxt1_block, dxt5_block
from flkm.game import ftex, ftex_write

RED = (220, 20, 30, 255)


def picture(size, colour=RED):
    return Image.new("RGBA", (size, size), colour)


def png(tmp_path, size, colour=RED, name="kit.png", width=None):
    p = tmp_path / name
    Image.new("RGBA", (width or size, size), colour).save(p)
    return p


def dds(fmt, size, mips, dxgi=None):
    """a DDS file: header (DX10 extension when dxgi is given) and the mips' blocks"""
    fourcc = b"DX10" if dxgi is not None else fmt
    pixel_format = struct.pack("<II4s5I", 32, 0x4, fourcc, 0, 0, 0, 0, 0)
    head = struct.pack("<4s7I", b"DDS ", 124, 0x1 | 0x2 | 0x4 | 0x1000 | 0x20000, size, size, 0, 0, len(mips))
    head += b"\0" * 44 + pixel_format + struct.pack("<5I", 0x1000 | 0x400000, 0, 0, 0, 0)
    if dxgi is not None:
        head += struct.pack("<5I", dxgi, 3, 0, 1, 0)
    return head + b"".join(mips)


def chain(block, size):
    """the blocks of every mip of a one-colour texture: size, size/2, ... 1 (at least one 4x4 block each)"""
    out = []
    while size >= 1:
        out.append(block * max(1, size // 4) ** 2)
        size //= 2
    return out


# --- build -----------------------------------------------------------------------------------------------------------


def test_build_writes_what_parse_reads():
    mips = chain(dxt5_block(0xF800), 8)
    tex = ftex.parse(ftex_write.build(ftex.DXT5, 8, 8, mips))
    assert (tex.format, tex.width, tex.height, [m.index for m in tex.mips]) == (ftex.DXT5, 8, 8, [0, 1, 2, 3])
    assert [ftex.mip_data(tex, i) for i in range(4)] == mips


def test_build_splits_large_mips_in_16_kb_chunks():
    mip = bytes(range(256)) * 256  # 64 KB that zlib can make smaller
    tex = ftex.parse(ftex_write.build(ftex.DXT5, 256, 256, [mip]))
    assert tex.mips[0].chunks == 4 and ftex.mip_data(tex) == mip


def test_build_keeps_a_chunk_zlib_cannot_make_smaller():
    noise = bytes((i * 7919 + i // 3) % 251 for i in range(64))
    assert ftex.mip_data(ftex.parse(ftex_write.build(ftex.DXT5, 8, 8, [noise]))) == noise


def test_build_keeps_the_template_header_but_its_size_and_format():
    template = build_ftex(ftex.BC7, 4, 4, [bc7_block(1, 2, 3)])
    template = template[:0x20] + b"\xab" * 8 + template[0x28:]
    out = ftex_write.build(ftex.DXT5, 8, 8, chain(dxt5_block(0), 8), header=template[:0x40])
    assert out[0x20:0x28] == b"\xab" * 8 and out[:0x08] == template[:0x08]
    tex = ftex.parse(out)
    assert (tex.format, tex.width, len(tex.mips)) == (ftex.DXT5, 8, 4)


def test_file_size_is_a_multiple_of_8():
    assert len(ftex_write.build(ftex.DXT5, 4, 4, [dxt5_block(1)])) % 8 == 0


# --- from an image ---------------------------------------------------------------------------------------------------


def test_an_image_becomes_dxt5_with_every_mip():
    tex = ftex.parse(ftex_write.encode(picture(16)))
    assert (tex.format, tex.width, [m.index for m in tex.mips]) == (ftex.DXT5, 16, [0, 1, 2, 3, 4])
    assert [m.size for m in tex.mips] == [256, 64, 16, 16, 16]  # mips under 4x4 still take a whole block
    r, g, b, _ = ftex.to_image(tex).getpixel((5, 5))
    assert abs(r - 220) < 10 and g < 30 and b < 40
    assert ftex.to_image(tex, mip=4).size == (4, 4)


def test_an_image_that_is_not_square_or_not_a_power_of_two_is_refused():
    with pytest.raises(ftex.FtexError, match="square"):
        ftex_write.encode(Image.new("RGBA", (16, 8)))
    with pytest.raises(ftex.FtexError, match="power of two"):
        ftex_write.encode(picture(12))


# --- from a DDS ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fourcc, dxgi, block, fmt",
    [
        (b"DXT5", None, dxt5_block(0x07E0), ftex.DXT5),
        (b"DXT1", None, dxt1_block(0x07E0), ftex.DXT1),
        (None, 98, bc7_block(0, 255, 0), ftex.BC7),
        (None, 99, bc7_block(0, 255, 0), ftex.BC7),
        (None, 77, dxt5_block(0x07E0), ftex.DXT5),
        (None, 71, dxt1_block(0x07E0), ftex.DXT1),
    ],
)
def test_a_dds_with_every_mip_keeps_its_blocks(fourcc, dxgi, block, fmt):
    mips = chain(block, 16)
    tex = ftex.parse(ftex_write.from_dds(dds(fourcc, 16, mips, dxgi)))
    assert (tex.format, tex.width, len(tex.mips)) == (fmt, 16, 5)
    assert [ftex.mip_data(tex, i) for i in range(5)] == mips


def test_a_dds_without_its_mips_is_encoded_again():
    single = Image.new("RGBA", (16, 16), (0, 0, 255, 255))
    buf = io.BytesIO()
    single.save(buf, "DDS", pixel_format="DXT1")
    tex = ftex.parse(ftex_write.from_dds(buf.getvalue()))
    assert (tex.format, len(tex.mips)) == (ftex.DXT5, 5)
    assert ftex.to_image(tex).getpixel((1, 1))[2] > 200


def test_a_dds_that_cannot_be_used():
    with pytest.raises(ftex.FtexError, match="not a DDS"):
        ftex_write.from_dds(b"PNG...")
    with pytest.raises(ftex.FtexError, match="DDS format ATI2 is not supported"):
        ftex_write.from_dds(dds(b"ATI2", 4, [b"\0" * 16]))
    with pytest.raises(ftex.FtexError, match="DDS format 28 is not supported"):
        ftex_write.from_dds(dds(None, 4, [b"\0" * 16], dxgi=28))
    with pytest.raises(ftex.FtexError, match="too short"):
        ftex_write.from_dds(dds(b"DXT5", 16, chain(dxt5_block(0), 16))[:-20])
    with pytest.raises(ftex.FtexError, match="DDS file cannot be read"):
        ftex_write.from_dds(dds(b"DXT5", 16, [b"\0" * 10]))  # one mip only, and too short to decode


# --- the file the user chooses for a kit ------------------------------------------------------------------------------


def test_kit_from_a_png(tmp_path):
    tex = ftex.parse(ftex_write.kit_texture(png(tmp_path, 256)))
    assert (tex.format, tex.width, len(tex.mips)) == (ftex.DXT5, 256, 9)


def test_kit_from_a_png_keeps_the_header_of_the_kit_it_replaces(tmp_path):
    template = build_ftex(ftex.DXT5, 4, 4, [dxt5_block(0)])
    template = template[:0x30] + b"\xcd" * 4 + template[0x34:]
    out = ftex_write.kit_texture(png(tmp_path, 256), header=template[:0x40])
    assert out[0x30:0x34] == b"\xcd" * 4


def test_kit_from_a_dds(tmp_path):
    p = tmp_path / "kit.dds"
    p.write_bytes(dds(b"DXT5", 256, chain(dxt5_block(0x001F), 256)))
    assert ftex.parse(ftex_write.kit_texture(p)).width == 256


def test_kit_from_an_ftex_is_taken_as_it_is(tmp_path):
    p = tmp_path / "u0186p1.ftex"
    p.write_bytes(build_ftex(ftex.DXT5, 4, 4, [dxt5_block(0)]))
    assert ftex_write.kit_texture(p) == p.read_bytes()
    p.write_bytes(b"nope")
    with pytest.raises(ftex.FtexError, match="not an FTEX"):
        ftex_write.kit_texture(p)


def test_kit_images_must_be_square_and_from_256_to_4096_pixels(tmp_path):
    with pytest.raises(ftex.FtexError, match="A kit texture must be square"):
        ftex_write.kit_texture(png(tmp_path, 256, width=512))
    with pytest.raises(ftex.FtexError, match="256, 512, 1024, 2048 or 4096"):
        ftex_write.kit_texture(png(tmp_path, 128))
    p = tmp_path / "small.dds"
    p.write_bytes(dds(b"DXT5", 16, chain(dxt5_block(0), 16)))
    with pytest.raises(ftex.FtexError, match="256, 512, 1024, 2048 or 4096"):
        ftex_write.kit_texture(p)


def test_kit_from_another_kind_of_file_or_a_broken_image(tmp_path):
    with pytest.raises(ftex.FtexError, match=r"Choose an \.ftex, \.png or \.dds file"):
        ftex_write.kit_texture(tmp_path / "kit.jpg")
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"\x89PNG broken")
    with pytest.raises(ftex.FtexError, match="cannot be read as an image"):
        ftex_write.kit_texture(broken)
