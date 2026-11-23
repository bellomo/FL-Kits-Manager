"""A team's kits from photos, end to end, on a fake game made here: crest from the game, maker from the photo and the
makers' cache, one texture per kit, staged like Replace…"""

import json

import numpy as np
import pytest
from PIL import Image

from conftest import build_ftex, dxt5_block, shirt_photo
from flkm.game import ftex, kits
from flkm.game.files import GameFiles
from flkm.photokit import PhotoKitError, team
from flkm.photokit.maker import save_maker
from flkm.staging import Staging

RED, BLACK, YELLOW, WHITE, BLUE = (200, 30, 40), (20, 20, 20), (240, 200, 0), (255, 255, 255), (30, 70, 160)
CREAM = (240, 230, 190)
MAKER = (BLACK, (0.36, 0.29, 0.42, 0.33))
CREST = (YELLOW, (0.58, 0.28, 0.64, 0.35))
SPONSOR = (WHITE, (0.40, 0.42, 0.60, 0.50))
CREST_COLOUR = (0, 160, 80, 255)


@pytest.fixture
def fake_game(game):
    """a fake game whose livecpk has the 512 px crest of team 186"""
    (game / "SiderAddons" / "sider.ini").write_text('cpk.root = ".\\livecpk\\_World"\n', encoding="utf-8")
    flag = game / "SiderAddons" / "livecpk" / "_World" / "common" / "render" / "symbol" / "flag"
    flag.mkdir(parents=True)
    Image.new("RGBA", (512, 512), CREST_COLOUR).save(flag / "e_000186_r_ll.png")
    (game / "Data").mkdir()
    return GameFiles(game)


def photos(tmp_path):
    src = tmp_path / "photos"
    src.mkdir()
    shirt_photo(size=800, collar=RED, logos=[MAKER, CREST, SPONSOR]).save(src / "home front.png")
    Image.new("RGB", (60, 60), BLACK).save(src / "home shorts.jpg")
    shirt_photo(size=800, body=CREAM, collar=CREAM, sleeve=BLUE).save(src / "away.png")
    return src


def test_copy_photos_names_them_for_the_draft(tmp_path):
    src = photos(tmp_path)
    ref = team.copy_photos(
        {
            "home": {"shirt": [src / "home front.png"], "shorts": [src / "home shorts.jpg"]},
            "away": {"shirt": [src / "away.png"], "back": [src / "away.png"], "socks": [src / "away.png"]},
        },
        tmp_path / "work",
    )
    names = sorted(p.name for p in ref.iterdir())
    assert names == ["away_1.png", "away_socks_1.png", "back_away_1.png", "home_1.png", "home_shorts_1.jpg"]
    team.copy_photos({"gk": {"shirt": [src / "away.png", src / "away.png"]}}, tmp_path / "work")  # replaces them
    assert sorted(p.name for p in ref.iterdir()) == ["gk_1.png", "gk_2.png"]


def test_copy_photos_refuses_what_is_not_a_kit_photo(tmp_path):
    (tmp_path / "notes.txt").write_text("x")
    for choice, message in (
        ({"training": {"shirt": [tmp_path / "a.png"]}}, "not a kit photo"),
        ({"home": {"hat": [tmp_path / "a.png"]}}, "not a kit photo"),
        ({"home": {"shirt": [tmp_path / "notes.txt"]}}, "notes.txt"),
    ):
        with pytest.raises(PhotoKitError, match=message):
            team.copy_photos(choice, tmp_path / "work")
    assert not (tmp_path / "work").exists()


def test_make_team_end_to_end(fake_game, tmp_path):
    src, work, makers = photos(tmp_path), tmp_path / "work", tmp_path / "makers"
    team.copy_photos(
        {
            "home": {"shirt": [src / "home front.png"], "shorts": [src / "home shorts.jpg"]},
            "away": {"shirt": [src / "away.png"]},
        },
        work,
    )
    made = team.make_team(fake_game, 186, work, makers)
    assert set(made.textures) == {"p1", "p2"} and made.missing == ["third", "gk"]
    assert (made.maker, made.new_maker) == ("maker_1", True) and (makers / "maker_1.png").is_file()
    assert "maker: maker_1 (new in the cache)" in made.notes
    back = "the back (the front mirrored, no back sponsor)"
    assert f"home: no photo of {back}, the socks (the shorts colour)" in made.notes
    assert f"away: no photo of {back}, the shorts (the shirt colour), the socks (the shorts colour)" in made.notes
    t = json.loads((work / "team.json").read_text(encoding="utf-8"))
    assert (t["crest"], t["maker"]) == ("crest.png", "maker_1")
    home = Image.open(made.textures["p1"])
    assert home.size == (2048, 2048) and home.getpixel((1024, 1500))[:3] == RED
    crest = t["kits"]["home"]["crest_pos"]
    x, y = round(1024 + (crest["tx"] - 0.5) * 520), round(897 + 1133 * crest["cy"])
    assert home.getpixel((x, y))[:3] == CREST_COLOUR[:3]  # the game's crest where the photo has its crest
    # away: no maker on its photo -> the cached mask, in the away kit's maker colour, where home has its maker
    away, pos = Image.open(made.textures["p2"]), t["kits"]["away"]["maker_pos"]
    x, y = round(1024 + (pos["tx"] - 0.5) * 520), round(897 + 1133 * pos["cy"])
    assert "#%02x%02x%02x" % away.getpixel((x, y))[:3] == t["kits"]["away"]["maker_color"]

    # the same team again with the home photos only: the maker comes from the cache, the old away texture goes
    team.copy_photos({"home": {"shirt": [src / "home front.png"]}}, work)
    again = team.make_team(fake_game, 186, work, makers)
    assert (again.maker, again.new_maker, set(again.textures)) == ("maker_1", False, {"p1"})
    assert not (work / "away.png").exists() and "maker: maker_1 (from the cache)" in again.notes


def test_deduced_notes():
    kits = {
        "home": {"_draft": {"deduced": []}},
        "away": {"_draft": {"deduced": ["shorts", "socks", "back"]}},
        "gk": {"_draft": {"deduced": ["socks"]}},
        "third": {},  # a team.json written by hand
    }
    assert team.deduced_notes({"kits": kits}) == [
        "away: no photo of the back (the front mirrored, no back sponsor), the shorts (the shirt colour), "
        "the socks (the shorts colour)",
        "gk: no photo of the socks (the shorts colour)",
    ]


def test_make_team_without_a_crest_in_the_game(fake_game, tmp_path):
    with pytest.raises(PhotoKitError, match="no crest for team 7"):
        team.make_team(fake_game, 7, tmp_path, tmp_path / "makers")


def fake_steps(monkeypatch, kits_json):
    """draft and build replaced by fakes: the draft writes kits_json, the build writes nothing"""

    def draft(folder, crest=None, force=False, tones=None):
        drafted.append(tones)
        path = f"{folder}/team.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"crest": crest, "kits": kits_json}, f)
        return path, [], []

    drafted = []
    monkeypatch.setattr(team, "draft_team", draft)
    monkeypatch.setattr(team, "build_team", lambda folder, makers: {})
    return drafted


def test_make_team_keeps_the_logos_when_asked_and_has_no_maker(fake_game, tmp_path, monkeypatch):
    fake_steps(monkeypatch, {"home": {"body": "#000000"}})
    (tmp_path / "logos").mkdir()
    (tmp_path / "home.png").write_bytes(b"old")
    (tmp_path / "crest.png").write_bytes(b"")
    made = team.make_team(fake_game, 186, tmp_path, tmp_path / "makers", keep_logos=True)
    assert (tmp_path / "logos").is_dir() and made.maker is None and made.textures == {}
    assert "maker" not in json.loads((tmp_path / "team.json").read_text(encoding="utf-8"))
    assert not (tmp_path / "home.png").exists() and (tmp_path / "crest.png").stat().st_size > 0
    team.make_team(fake_game, 186, tmp_path, tmp_path / "makers")
    assert not (tmp_path / "logos").exists()


def maker_logo(path, shape):
    a = np.zeros((40, 80, 4), np.uint8)
    if shape == "bar":
        a[10:30, :] = (0, 0, 0, 255)
    else:
        a[:, 30:50] = (0, 0, 0, 255)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(a).save(path)
    return Image.fromarray(a)


def test_cached_maker(tmp_path):
    makers = tmp_path / "makers"
    shown = {"kits": {"away": {}, "home": {"maker_logo": {"file": "logos/home_1_c01.png"}}}}
    hidden = {"kits": {"home": {}}}
    bar = maker_logo(tmp_path / "logos" / "home_1_c01.png", "bar")
    assert team._cached_maker(tmp_path, hidden, makers, None) == (None, False)
    assert team._cached_maker(tmp_path, hidden, makers, "errea") == (None, False)  # not in the cache
    assert team._cached_maker(tmp_path, shown, makers, "errea") == ("errea", True)  # saved under the name given
    assert team._cached_maker(tmp_path, shown, makers, "errea") == ("errea", False)
    assert team._cached_maker(tmp_path, hidden, makers, "errea") == ("errea", False)  # hidden, but cached
    assert team._cached_maker(tmp_path, shown, makers, None) == ("errea", False)  # recognised
    save_maker(bar, makers, "errea")
    maker_logo(tmp_path / "logos" / "home_1_c01.png", "post")
    assert team._cached_maker(tmp_path, shown, makers, None) == ("maker_1", True)  # another shape: a new maker


def test_stage_textures_like_replace(tmp_path):
    png = tmp_path / "home.png"
    Image.new("RGBA", (256, 256), (200, 30, 40, 255)).save(png)
    old = tmp_path / "u186p1.ftex"
    header = bytearray(build_ftex(4, 4, 4, [dxt5_block(0)])[:0x40])
    old.write_bytes(build_ftex(4, 4, 4, [dxt5_block(0)]))
    current = {"p1": kits.Kit(186, "p1", "kitserver", file=old)}
    made = team.MadeTeam(tmp_path, {"p1": png, "p2": png}, None)
    staging = Staging(tmp_path / "staging")
    changes = team.stage_textures(staging, 186, "Test FC", made, current)
    assert [(c.slot, c.source) for c in changes] == [("p1", str(png)), ("p2", str(png))]
    tex = ftex.parse(staging.path(changes[0]).read_bytes())
    assert tex.width == 256 and staging.path(changes[0]).read_bytes()[:4] == bytes(header[:4])
    assert set(staging.for_team(186)) == {"p1", "p2"}


def test_place_photos_by_name_then_in_the_first_empty_cells(tmp_path):
    named = [tmp_path / "away_shorts_1.png", tmp_path / "h1.jpg", tmp_path / "back_home.png"]
    other = [tmp_path / "IMG_0001.jpg", tmp_path / "IMG_0002.webp"]
    chosen, left = team.place_photos(named + other, {("home", "shirt"): tmp_path / "old.png"})
    assert chosen[("away", "shorts")] == named[0] and chosen[("home", "back")] == named[2]
    assert chosen[("home", "shirt")] == named[1]  # the name says so: it replaces the old one
    assert chosen[("home", "shorts")] == other[0] and chosen[("home", "socks")] == other[1]  # next empty cells
    assert left == []
    full = {cell: tmp_path / "x.png" for cell in team.CELLS}
    chosen, left = team.place_photos(other, full)
    assert chosen == full and left == other


def test_photos_in_folder(tmp_path):
    for name in ("b.png", "a.JPG", "c.webp", "notes.txt", "_grid.png"):
        (tmp_path / name).write_bytes(b"")
    (tmp_path / "sub").mkdir()
    assert [p.name for p in team.photos_in_folder(tmp_path)] == ["_grid.png", "a.JPG", "b.png", "c.webp"]


def test_save_pasted_numbers_the_pictures(tmp_path):
    first = team.save_pasted(Image.new("RGBA", (10, 10), (255, 0, 0, 255)), tmp_path)
    second = team.save_pasted(Image.new("RGB", (10, 10)), tmp_path)
    assert (first.name, second.name) == ("pasted_1.png", "pasted_2.png") and first.parent == tmp_path / "pasted"
    assert Image.open(first).getpixel((0, 0))[:3] == (255, 0, 0)


def test_chosen_to_photos():
    chosen = {("home", "shirt"): "h.png", ("home", "back"): "b.png", ("away", "socks"): "s.png"}
    assert team.chosen_to_photos(chosen) == {
        "home": {"shirt": ["h.png"], "back": ["b.png"]},
        "away": {"socks": ["s.png"]},
    }


def test_make_team_with_a_crest_given(fake_game, tmp_path, monkeypatch):
    fake_steps(monkeypatch, {"home": {"body": "#000000"}})
    team.make_team(fake_game, 7, tmp_path, tmp_path / "makers", crest=Image.new("RGBA", (64, 64), (1, 2, 3, 255)))
    assert Image.open(tmp_path / "crest.png").getpixel((5, 5)) == (1, 2, 3, 255)  # the team has none in the game


def test_make_team_with_the_colours_of_one_photo(fake_game, tmp_path, monkeypatch):
    drafted = fake_steps(monkeypatch, {"home": {"body": "#000000"}})
    team.make_team(fake_game, 186, tmp_path, tmp_path / "makers", tones={"home": "back"})
    team.make_team(fake_game, 186, tmp_path, tmp_path / "makers")
    assert drafted == [{"home": "back"}, None]


def test_saved_tones(tmp_path):
    assert team.saved_tones(tmp_path) == {}  # never made
    kits = {"home": {"_draft": {"tone": "back"}}, "away": {"_draft": {}}, "gk": {}}
    (tmp_path / "team.json").write_text(json.dumps({"kits": kits}), encoding="utf-8")
    assert team.saved_tones(tmp_path) == {"home": "back"}


def test_copy_photos_from_the_photos_copied_before(tmp_path):
    src = photos(tmp_path)
    ref = team.copy_photos({"home": {"shirt": [src / "away.png"]}}, tmp_path / "work")
    again = team.copy_photos({"away": {"shirt": [ref / "home_1.png"]}}, tmp_path / "work")
    assert [p.name for p in again.iterdir()] == ["away_1.png"]
    assert (again / "away_1.png").read_bytes() == (src / "away.png").read_bytes()


def test_made_before(tmp_path):
    assert team.made_before(tmp_path) is None
    (tmp_path / "away.png").write_bytes(b"png")
    (tmp_path / "crest.png").write_bytes(b"png")
    made = team.made_before(tmp_path)
    assert (made.folder, made.textures, made.maker, made.notes) == (tmp_path, {"p2": tmp_path / "away.png"}, None, [])
