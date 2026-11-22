"""Team crests and competition logos: where the game keeps them, reading the one the game uses, and the files of a new
one made from a picture.

- crest of team 186: common/render/symbol/flag/e_000186_r.png (128 px), e_000186_r_l.png (256), e_000186_r_ll.png (512)
- logo of competition 17: common/render/symbol/emblemLc/emb_0017{,_b,_w}_{l,ll}.png (256, 512): normal, dark (for
  light backgrounds), white (for dark backgrounds)
A new logo is the picture centred on a transparent square and resized to every size."""

import io

import pytest
from PIL import Image

from flkm.game import files, logos

FLAG = "common/render/symbol/flag/"
EMB = "common/render/symbol/emblemLc/"
RED, BLUE = (220, 20, 30, 255), (20, 60, 200, 255)


def png(size, colour=RED, width=None):
    buf = io.BytesIO()
    Image.new("RGBA", (width or size, size), colour).save(buf, "PNG")
    return buf.getvalue()


def make_game(game, make_cpk, loose=None, packed=None):
    sider = game / "SiderAddons"
    (sider / "sider.ini").write_text('cpk.root = ".\\livecpk\\_World"\n', encoding="utf-8")
    root = sider / "livecpk" / "_World"
    for path, data in (loose or {}).items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_bytes(data)
    (game / "Data").mkdir()
    if packed:
        (game / "Data" / "dt15_x64.cpk").write_bytes(make_cpk("dt.cpk", packed).read_bytes())
    return files.GameFiles(game)


def test_crest_file_names():
    assert logos.crest_files(186) == {
        128: FLAG + "e_000186_r.png",
        256: FLAG + "e_000186_r_l.png",
        512: FLAG + "e_000186_r_ll.png",
    }
    assert logos.crest_files(73947)[512] == FLAG + "e_073947_r_ll.png"


def test_competition_logo_file_names():
    names = logos.emblem_files(17)
    assert names[("", 256)] == EMB + "emb_0017_l.png" and names[("w", 512)] == EMB + "emb_0017_w_ll.png"
    assert sorted(names) == [(v, s) for v in ("", "b", "w") for s in (256, 512)]
    assert logos.VARIANTS == {"": "Normal", "b": "Dark", "w": "White"}


def test_the_crest_the_game_uses_is_its_largest(game, make_cpk):
    gf = make_game(game, make_cpk, {FLAG + "e_000186_r_l.png": png(256, BLUE)}, {FLAG + "e_000186_r.png": png(128)})
    found = logos.find_crest(gf, 186)
    assert found.source == "livecpk\\_World" and found.path == FLAG + "e_000186_r_l.png"
    assert logos.picture(found).size == (256, 256)
    assert logos.find_crest(gf, 5) is None


def test_a_crest_from_the_game_archives(game, make_cpk):
    gf = make_game(game, make_cpk, packed={FLAG + "e_000186_r.png": png(128)})
    found = logos.find_crest(gf, 186)
    assert found.source == "Data\\dt15_x64.cpk" and logos.picture(found).getpixel((5, 5)) == RED


def test_the_competition_logo_the_game_uses(game, make_cpk):
    gf = make_game(game, make_cpk, {EMB + "emb_0017_w_ll.png": png(512, BLUE)}, {EMB + "emb_0017_w_l.png": png(256)})
    assert logos.find_emblem(gf, 17, "w").path == EMB + "emb_0017_w_ll.png"
    assert logos.find_emblem(gf, 17, "b") is None


def test_a_new_crest_has_every_size(tmp_path):
    files_ = logos.make_crest(Image.new("RGBA", (600, 600), RED), 186)
    assert sorted(files_) == sorted(logos.crest_files(186).values())
    for size, name in logos.crest_files(186).items():
        im = Image.open(io.BytesIO(files_[name]))
        assert (im.format, im.mode, im.size) == ("PNG", "RGBA", (size, size))
        assert im.getpixel((size // 2, size // 2)) == RED


def test_a_picture_that_is_not_square_is_centred_on_transparency():
    files_ = logos.make_crest(Image.new("RGB", (200, 100), (0, 255, 0)), 186)
    im = Image.open(io.BytesIO(files_[FLAG + "e_000186_r.png"]))
    assert im.getpixel((64, 64)) == (0, 255, 0, 255)
    assert im.getpixel((64, 5))[3] == 0 and im.getpixel((64, 122))[3] == 0  # bands above and below


def test_a_new_competition_logo_has_every_size_of_each_variant():
    pictures = {"": Image.new("RGBA", (300, 300), RED), "w": Image.new("RGBA", (300, 300), BLUE)}
    files_ = logos.make_emblem(pictures, 17)
    assert sorted(files_) == sorted(n for (v, _), n in logos.emblem_files(17).items() if v in ("", "w"))
    im = Image.open(io.BytesIO(files_[EMB + "emb_0017_w_ll.png"]))
    assert im.size == (512, 512) and im.getpixel((256, 256)) == BLUE


def test_load_a_picture(tmp_path):
    p = tmp_path / "crest.png"
    p.write_bytes(png(64, width=32))
    assert logos.load(p).size == (32, 64)
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"nope")
    with pytest.raises(logos.LogoError, match="bad.png cannot be read as a picture"):
        logos.load(bad)
    with pytest.raises(logos.LogoError, match="cannot be read as a picture"):
        logos.load(tmp_path / "missing.png")
