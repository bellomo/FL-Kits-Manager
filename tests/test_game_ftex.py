"""FTEX textures (kits, numbers, names): header, mip table, mips in zlib chunks, decoded to an RGBA image.
Formats met in the game: 2 = DXT1, 4 = DXT5, 11 = BC7."""

import pytest

from conftest import bc7_block, build_ftex, dxt1_block, dxt5_block
from flkm.game import ftex

RED565, BLUE565 = 0xF800, 0x001F


def solid(block: bytes, width: int, height: int) -> bytes:
    return block * ((width // 4) * (height // 4))


def test_header_gives_format_size_and_mips():
    data = build_ftex(4, 16, 8, [solid(dxt5_block(RED565), 16, 8), solid(dxt5_block(RED565), 8, 4)])
    tex = ftex.parse(data)
    assert (tex.format, tex.width, tex.height) == (4, 16, 8)
    assert [m.index for m in tex.mips] == [0, 1]


def test_mip_0_is_the_largest_whole_after_the_chunks_are_joined():
    big = solid(dxt5_block(RED565), 256, 128)  # 32 KB: three 16 KB chunks
    tex = ftex.parse(build_ftex(4, 256, 128, [big, solid(dxt5_block(RED565), 128, 64)]))
    assert ftex.mip_data(tex, 0) == big


def test_chunks_stored_without_compression_are_read_as_they_are():
    big = solid(dxt1_block(BLUE565), 64, 64)
    tex = ftex.parse(build_ftex(2, 64, 64, [big], raw=True))
    assert ftex.mip_data(tex, 0) == big


def test_full_size_chunk_of_64_kb_is_read():
    big = solid(dxt5_block(RED565), 256, 256)  # 64 KB in one chunk: its size field wraps to 0
    tex = ftex.parse(build_ftex(4, 256, 256, [big], chunk=0x10000))
    assert ftex.mip_data(tex, 0) == big


@pytest.mark.parametrize(
    "fmt, block, colour",
    [
        (4, dxt5_block(RED565), (255, 0, 0, 255)),
        (4, dxt5_block(BLUE565, alpha=0), (0, 0, 255, 0)),
        (2, dxt1_block(BLUE565), (0, 0, 255, 255)),
        (11, bc7_block(255, 129, 1), (255, 129, 1, 255)),
    ],
)
def test_decodes_to_rgba(fmt, block, colour):
    tex = ftex.parse(build_ftex(fmt, 8, 8, [solid(block, 8, 8)]))
    image = ftex.to_image(tex)
    assert image.mode == "RGBA" and image.size == (8, 8)
    assert image.getpixel((0, 0)) == colour and image.getpixel((7, 7)) == colour


def test_opaque_ignores_alpha_for_kit_previews():
    # some BC7 kits of Mod Studio worlds keep alpha near 0, which the game does not use as transparency
    tex = ftex.parse(build_ftex(11, 4, 4, [bc7_block(255, 129, 1, a=1)]))
    assert ftex.to_image(tex).getpixel((0, 0))[3] == 1
    assert ftex.to_image(tex, opaque=True).getpixel((0, 0)) == (255, 129, 1, 255)


def test_smaller_mip_for_quick_previews():
    tex = ftex.parse(build_ftex(4, 16, 16, [solid(dxt5_block(RED565), 16, 16), solid(dxt5_block(BLUE565), 8, 8)]))
    image = ftex.to_image(tex, mip=1)
    assert image.size == (8, 8) and image.getpixel((0, 0)) == (0, 0, 255, 255)


def test_not_an_ftex_is_refused():
    with pytest.raises(ftex.FtexError):
        ftex.parse(b"DDS " + b"\0" * 100)


def test_unknown_format_is_refused_when_decoding():
    tex = ftex.parse(build_ftex(7, 4, 4, [b"\0" * 16]))
    with pytest.raises(ftex.FtexError, match="format 7"):
        ftex.to_image(tex)


def test_missing_mip_is_refused():
    tex = ftex.parse(build_ftex(4, 4, 4, [dxt5_block(RED565)]))
    with pytest.raises(ftex.FtexError, match="mip 3"):
        ftex.mip_data(tex, 3)


def test_load_reads_a_file(tmp_path):
    p = tmp_path / "u0186p1.ftex"
    p.write_bytes(build_ftex(4, 4, 4, [dxt5_block(RED565)]))
    assert ftex.load(p).width == 4
