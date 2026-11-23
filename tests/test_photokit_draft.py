"""team.json drafted from the photos of a team folder: colours, logos, crest and maker positions, pattern."""

import json

import pytest
from PIL import Image

from conftest import shirt_photo
from flkm.photokit import PhotoKitError, draft
from flkm.photokit.colour import colour_distance

RED, BLACK, YELLOW, WHITE, BLUE = (200, 30, 40), (20, 20, 20), (240, 200, 0), (255, 255, 255), (30, 70, 160)
CREAM = (240, 230, 190)  # a white shirt on a white background would be background
MAKER = (BLACK, (0.36, 0.29, 0.42, 0.33))
CREST = (YELLOW, (0.58, 0.28, 0.64, 0.35))
SPONSOR = (WHITE, (0.40, 0.42, 0.60, 0.50))
OFF_CENTRE = (BLACK, (0.49, 0.42, 0.63, 0.50))  # crosses the centre but is not centred: to check


def photo(**kw):
    kw.setdefault("collar", kw.get("body", RED))
    return shirt_photo(size=800, **kw)


@pytest.fixture
def team(tmp_path):
    d = tmp_path / "Test FC"
    (d / "ref").mkdir(parents=True)
    photo(logos=[MAKER, CREST, SPONSOR], stripes=[(BLUE, 0.48, 0.52)]).save(d / "ref" / "h1.png")
    Image.new("RGB", (60, 60), BLACK).save(d / "ref" / "hs.png")
    Image.new("RGB", (60, 60), WHITE).save(d / "ref" / "hso.png")
    photo(logos=[(WHITE, (0.40, 0.30, 0.60, 0.36))]).save(d / "ref" / "back_home.png")
    photo(body=CREAM, sleeve=BLUE, collar=BLUE, logos=[OFF_CENTRE]).save(d / "ref" / "a1.png")
    photo(body=CREAM).save(d / "ref" / "back_away.png")  # a back without sponsors
    photo(body=(0, 160, 80)).save(d / "ref" / "g1.png")  # a goalkeeper shirt alone: no back photo, no logos
    return d


def read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_draft_kit_colours():
    parts = {
        "shirt": [
            {
                "file": "h1.png",
                "colours": [("#c81e28", 0.7), ("#f0c800", 0.1)],
                "zones": {"body": "#c81e28", "sleeve": "#c3202a", "collar": "#c81e28"},
            }
        ],
    }
    k = draft.draft_kit(parts)
    assert (k["body"], k["sleeve"], k["collar"], k["cuff"]) == ("#c81e28", "#c81e28", "#f0c800", "#f0c800")
    assert k["shorts"] == k["socks"] == "#c81e28" and k["numbers"] == k["maker_color"] == "#f0c800"
    assert k["_draft"] == {"sources": ["h1.png"], "deduced": ["shorts", "socks", "back"], "secondary": "#f0c800"}


def test_draft_kit_without_zones_and_with_a_collar_of_its_own():
    parts = {
        "shirt": [{"file": "a1.png", "colours": [("#ffffff", 0.8)], "zones": {"collar": "#1e46a0"}}],
        "shorts": [{"file": "as_.png", "colours": [("#111111", 1.0)]}],
        "socks": [{"file": "aso.png", "colours": [("#222222", 1.0)]}],
        "back": [{"file": "back_away.png", "colours": [("#ffffff", 1.0)]}],
    }
    k = draft.draft_kit(parts)
    assert (k["body"], k["collar"], k["shorts"], k["socks"], k["numbers"]) == (
        "#ffffff",
        "#1e46a0",
        "#111111",
        "#222222",
        "#111111",
    )
    assert k["_draft"]["deduced"] == [] and k["_draft"]["sources"][-1] == "back_away.png"
    assert draft.draft_kit({"shorts": parts["shorts"]}) is None


def test_draft_team_measures_everything(team):
    out, missing, notes = draft.draft_team(str(team), crest="crest.png", maker="errea")
    assert out.endswith("team.json") and missing == ["third"]
    t = read(out)
    assert (t["crest"], t["maker"], list(t["kits"])) == ("crest.png", "errea", ["home", "away", "gk"])
    home, away = t["kits"]["home"], t["kits"]["away"]
    assert home["maker_logo"]["file"].startswith("logos/h1_c") and home["crest_pos"]["from"].startswith("logos/h1_c")
    assert len(home["chest_logos"]) == 1 and len(home["back_logos"]) == 1
    assert home["rects"] and home["_draft"]["auto"]["rects"] == len(home["rects"])
    assert home["shorts"] == "#141414" and home["socks"] == "#ffffff"
    # away: no crest and no maker on its photo -> the home kit's positions
    assert away["crest_pos"] == home["crest_pos"] and away["maker_pos"]["from"] == home["maker_logo"]["file"]
    assert away["_draft"]["auto"]["check"] and "back_logos" not in away  # the off-centre sponsor is to check
    assert away["sleeve"] == "#1e46a0" and home["sleeve"] == home["body"]
    assert any("away: crest position taken from" in n for n in notes)
    assert any("away: maker position taken from" in n for n in notes)
    assert any(n.startswith("away: check ") for n in notes)
    assert any(n.startswith("home: maker found, crest found, 1 chest sponsor(s), 1 back sponsor(s)") for n in notes)
    assert any("away: maker NOT FOUND, crest NOT FOUND" in n for n in notes)
    with open(out, encoding="utf-8") as f:
        assert f.read().count("\n") == 9  # one line per kit


def test_draft_team_with_the_colours_of_the_front_or_the_back_photo(team):
    photo(body=(130, 20, 25), logos=[(WHITE, (0.40, 0.30, 0.60, 0.36))]).save(team / "ref" / "back_home.png")
    out, _, notes = draft.draft_team(str(team), force=True)
    home = read(out)["kits"]["home"]
    assert [0, 1012] in [r["y"] for r in home["rects"] if r["x"] == [650, 1330]] and "tone" not in home["_draft"]
    out, _, notes = draft.draft_team(str(team), force=True, tones={"home": "front", "gk": "back"})
    home = read(out)["kits"]["home"]
    assert [0, 1012] not in [r["y"] for r in home["rects"] if r["x"] == [650, 1330]] and home["body"] == "#c81e28"
    assert home["_draft"]["tone"] == "front" and "home: the colours of the front photo" in notes
    assert "tone" not in read(out)["kits"]["gk"]["_draft"]  # no back photo: nothing to choose
    out, _, notes = draft.draft_team(str(team), force=True, tones={"home": "back"})
    home = read(out)["kits"]["home"]
    assert colour_distance(home["body"], "#82141a") < 12 and home["sleeve"] == home["body"]
    assert home["shorts"] == "#141414"  # measured on its own photo: not in the back's tone
    assert colour_distance(home["socks"], "#ffffff") < 1 and home["_draft"]["tone"] == "back"
    assert "home: the colours of the back photo" in notes


def test_apply_tone_follows_the_deduced_parts():
    kit = {"body": "#c81e28", "sleeve": "#c81e28", "cuff": "#f0c800", "collar": "#f0c800", "shorts": "#c81e28"}
    kit.update(socks="#c81e28", maker_color="#f0c800", numbers="#f0c800")
    kit["_draft"] = {"deduced": ["shorts", "socks"], "secondary": "#f0c800"}
    draft.apply_tone(kit, (0.5, 0.5, 0.5))
    assert (kit["body"], kit["cuff"], kit["shorts"], kit["socks"]) == ("#640f14", "#786400", "#640f14", "#640f14")
    assert kit["_draft"]["secondary"] == "#786400" and kit["numbers"] == kit["maker_color"] == "#ffffff"  # unreadable
    kit = {"body": "#ffffff", "sleeve": "#ffffff", "cuff": "#ffffff", "collar": "#ffffff", "shorts": "#000000"}
    kit.update(socks="#000000", _draft={"deduced": [], "secondary": None})
    draft.apply_tone(kit, (0.5, 0.5, 0.5))
    assert kit["shorts"] == "#000000" and kit["numbers"] == "#111111"  # the more readable of white or black


def test_draft_team_leaves_the_player_name_and_number_out_of_the_back(team):
    name, under = (WHITE, (0.42, 0.22, 0.58, 0.26)), (WHITE, (0.42, 0.65, 0.58, 0.70))
    digits = [(WHITE, (0.40, 0.30, 0.48, 0.55)), (WHITE, (0.52, 0.30, 0.60, 0.55))]
    photo(logos=[name, *digits, under]).save(team / "ref" / "back_home.png")
    out, _, notes = draft.draft_team(str(team), force=True)
    home = read(out)["kits"]["home"]
    assert len(home["back_logos"]) == 1 and home["back_logos"][0]["cy"] > 0.6  # the sponsor only
    assert not [r for r in home["rects"] if r["color"] == "#ffffff"]  # the digits are not white stripes
    assert "home: player name and number left out of the back photo" in notes


def test_draft_team_keeps_an_existing_team_json(team):
    (team / "team.json").write_text("{}", encoding="utf-8")
    out, _, _ = draft.draft_team(str(team))
    assert out.endswith("team.draft.json") and "crest" not in read(out)
    assert (team / "team.json").read_text(encoding="utf-8") == "{}"
    out, _, _ = draft.draft_team(str(team), force=True)
    assert out.endswith("team.json") and "kits" in read(out)


def test_draft_team_without_a_shirt_photo(tmp_path):
    (tmp_path / "ref").mkdir()
    Image.new("RGB", (60, 60), BLACK).save(tmp_path / "ref" / "hs.png")
    with pytest.raises(PhotoKitError, match="no shirt photo"):
        draft.draft_team(str(tmp_path))


def test_candidates_of_an_old_json_and_a_joined_logo(tmp_path):
    (tmp_path / "logos").mkdir()
    old = [
        {"file": "h1_c01.png", "box": [0, 0, 100, 20], "cx": 0.5, "cy": 0.4, "w": 0.3, "h": 0.1, "tx": 0.5, "tw": 0.4},
        {"file": "h1_c02.png", "box": [0, 30, 100, 50], "cx": 0.5, "cy": 0.5, "w": 0.3, "h": 0.1, "tx": 0.5, "tw": 0.4},
        {
            "file": "h1_j01-02.png",
            "box": [0, 0, 100, 50],
            "cx": 0.5,
            "cy": 0.45,
            "w": 0.3,
            "h": 0.2,
            "tx": 0.5,
            "tw": 0.4,
            "role": "sponsor",
        },
        {
            "file": "h1_c03.png",
            "box": [300, 0, 400, 20],
            "cx": 0.5,
            "cy": 0.9,
            "w": 0.3,
            "h": 0.1,
            "tx": 0.5,
            "tw": 0.4,
        },
    ]
    (tmp_path / "logos" / "_candidates_h1.json").write_text(json.dumps(old), encoding="utf-8")
    kept = draft._candidates(str(tmp_path), "h1.png")
    assert [m["file"] for m in kept] == ["h1_j01-02.png", "h1_c03.png"] and kept[1]["role"] == "other"
