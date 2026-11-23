"""team.json -> texture specs: where crest, maker, sponsors and measured logos land on the texture."""

import json
import os

import numpy as np
import pytest
from PIL import Image

from flkm.photokit import PhotoKitError, spec

KIT = {
    "body": "#c81e28",
    "sleeve": "#c81e28",
    "cuff": "#111111",
    "collar": "#111111",
    "shorts": "#111111",
    "socks": "#111111",
    "maker_color": "#111111",
    "numbers": "#ffffff",
}


def logo_png(path, colour=(200, 160, 0)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    a = np.zeros((40, 60, 4), np.uint8)
    a[5:35, 5:55] = colour + (255,)
    Image.fromarray(a).save(path)


@pytest.fixture
def team(tmp_path):
    d = tmp_path / "Test FC"
    logo_png(d / "crest.png")
    return d


def write_team(d, kit=None, **top):
    t = {"crest": "crest.png", **top, "kits": {"home": dict(KIT, **(kit or {}))}}
    (d / "team.json").write_text(json.dumps(t), encoding="utf-8")


def files(s, name):
    return [lg for lg in s["logos"] if os.path.basename(lg.get("file", "")) == name]


def test_front_and_back_logo_positions():
    m = {"file": "logos/a.png", "tx": 0.5, "tw": 0.5, "cy": 0.4, "color": "#000000"}
    e = spec.front_logo(m, "C:/team")
    assert (e["x"], e["y"], e["w"], e["color"]) == (1024, round(897 + 1133 * 0.4), 260, "#000000")
    assert e["file"] == os.path.join("C:/team", "logos/a.png")
    b = spec.back_logo(dict(m, tx=0.6), "C:/team")
    assert (b["x"], b["y"], b["rotate"]) == (1024 - 52, round(1155 - 1133 * 0.4), 180)
    assert spec.front_logo(dict(m, x=5, y=6, w=7, file="D:/abs.png"), "C:/team")["file"] == "D:/abs.png"
    assert (spec.back_logo(dict(m, x=5, y=6), "C:/team")["x"], spec.back_logo(dict(m, y=6), "C:/team")["y"]) == (5, 6)


def test_plain_kit_gets_crest_on_chest_and_shorts(team):
    write_team(team)
    s = spec.expand_team(str(team))["home"]
    crest = files(s, "crest.png")
    assert [(c["x"], c["y"]) for c in crest] == [(1142, 1135), (125, 1690)]
    assert os.path.isabs(crest[0]["file"])
    assert s["body"] == KIT["body"] and "maker_color" not in s and s["numbers"] == "#ffffff"
    assert s["cfg"]["ShirtColor2"] == "#111111" and s["cfg"]["SocksColor"] == "#111111"


def test_relative_team_folder(team, monkeypatch):
    write_team(team)
    monkeypatch.chdir(team.parent)
    s = spec.expand_team("Test FC")["home"]
    assert all(os.path.isabs(lg["file"]) and os.path.exists(lg["file"]) for lg in s["logos"])


def test_missing_crest_is_an_error(team):
    write_team(team)
    os.remove(team / "crest.png")
    with pytest.raises(PhotoKitError, match="crest.png"):
        spec.expand_team(str(team))
    (team / "team.json").write_text(json.dumps({"kits": {"home": KIT}}), encoding="utf-8")
    with pytest.raises(PhotoKitError, match="none given"):
        spec.expand_team(str(team))


def test_maker_mask_from_the_makers_folder(team, tmp_path):
    logo_png(tmp_path / "makers" / "errea.png", (255, 255, 255))
    write_team(team, {"maker_color_shorts": "#eeeeee"}, maker="errea")
    s = spec.expand_team(str(team), str(tmp_path / "makers"))["home"]
    mk = files(s, "errea.png")
    assert [(m["x"], m["y"], m["color"]) for m in mk] == [
        (906, 1140, "#111111"),
        (1923, 1690, "#eeeeee"),
        (80, 920, "#eeeeee"),
        (1968, 920, "#eeeeee"),
    ]
    assert "maker_color_shorts" not in s


def test_maker_without_a_makers_folder_is_left_out(team):
    write_team(team, maker="errea")
    assert not files(spec.expand_team(str(team))["home"], "errea.png")


def test_maker_logo_from_the_photo_makes_a_mask(team):
    logo_png(team / "logos" / "home_1_c02.png", (10, 20, 200))
    write_team(team, {"maker_logo": {"file": "logos/home_1_c02.png", "tx": 0.25, "tw": 0.12, "cy": 0.22}})
    s = spec.expand_team(str(team))["home"]
    chest = files(s, "home_1_c02.png")
    assert len(chest) == 1 and "color" not in chest[0]  # the photo's own colours on the chest
    masks = files(s, "_maker_mask_home.png")
    assert len(masks) == 3 and all(m["color"] == "#111111" for m in masks)  # shorts and socks only
    mask = Image.open(team / "logos" / "_maker_mask_home.png")
    assert mask.getpixel((20, 20)) == (255, 255, 255, 255) and mask.getpixel((1, 1))[3] == 0


def test_maker_position_from_another_kit(team, tmp_path):
    logo_png(tmp_path / "makers" / "errea.png", (255, 255, 255))
    write_team(team, {"maker_pos": {"from": "logos/away_1_c02.png", "tx": 0.25, "tw": 0.1, "cy": 0.22}}, maker="errea")
    s = spec.expand_team(str(team), str(tmp_path / "makers"))["home"]
    chest = files(s, "errea.png")[0]
    assert (chest["x"], chest["w"], chest["color"]) == (round(1024 - 0.25 * 520), 52, "#111111")


def test_crest_position_and_tint(team):
    write_team(
        team,
        {"crest_pos": {"from": "logos/home_1_c05.png", "tx": 0.75, "tw": 0.2, "cy": 0.22}, "crest_tint": "#333333"},
    )
    s = spec.expand_team(str(team))["home"]
    crest = files(s, "crest.png")
    assert (crest[0]["x"], crest[0]["w"]) == (1154, 104) and all(c["tint"] == "#333333" for c in crest)
    assert "crest_tint" not in s and "crest_pos" not in s


def test_sponsors_text_and_file(team):
    write_team(
        team,
        {
            "sponsor": {"text": "ACME", "color": "#ffffff", "box": {"color": "#000000"}},
            "sponsor2": {"file": "s2.png", "h": 50, "font": "x"},
        },
    )
    s = spec.expand_team(str(team))["home"]
    sp = [lg for lg in s["logos"] if lg.get("text") == "ACME"][0]
    assert (sp["x"], sp["y"], sp["w"], sp["box"]) == (1024, 1305, 370, {"color": "#000000"})
    s2 = files(s, "s2.png")[0]
    assert (s2["y"], s2["h"], "w" in s2) == (1430, 50, False)


def test_measured_chest_and_back_logos(team):
    m = {"tx": 0.5, "tw": 0.4, "cy": 0.5}
    write_team(team, {"chest_logos": [dict(m, file="logos/c1.png")], "back_logos": [dict(m, file="logos/b1.png")]})
    s = spec.expand_team(str(team))["home"]
    assert files(s, "c1.png")[0]["y"] == round(897 + 1133 * 0.5)
    assert files(s, "b1.png")[0]["rotate"] == 180


def test_back_sponsors_back_text_and_sock_text(team):
    write_team(
        team,
        {
            "back_sponsor": [
                {"text": "B", "color": "#ffffff", "outline": {"color": "#000000"}},
                {"file": "bs.png", "color": "#ffffff", "y": 800},
            ],
            "back_text": {"text": "1899", "color": "#ffffff"},
            "sock_text": {"text": "SCR", "color": "#000000"},
        },
    )
    s = spec.expand_team(str(team))["home"]
    texts = [(lg["text"], lg["x"], lg["y"]) for lg in s["logos"] if "text" in lg]
    assert texts == [("B", 1024, 890), ("1899", 1024, 960), ("SCR", 80, 860), ("SCR", 1968, 860)]
    assert files(s, "bs.png")[0]["y"] == 800
    write_team(team, {"back_sponsor": {"file": "bs.png", "color": "#ffffff"}})
    assert files(spec.expand_team(str(team))["home"], "bs.png")[0]["rotate"] == 180


def test_defaults_without_optional_colours(team):
    (team / "team.json").write_text(
        json.dumps({"crest": str(team / "crest.png"), "kits": {"gk": {"body": "#00ff00", "shorts": "#000000"}}}),
        encoding="utf-8",
    )
    s = spec.expand_team(str(team))["gk"]
    assert s["numbers"] == "#ffffff"
    assert s["cfg"]["ShirtColor2"] == s["cfg"]["UndershirtColor"] == "#00ff00" and s["cfg"]["SocksColor"] == "#000000"
