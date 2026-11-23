"""Logos found on a flat shirt photo and cut out: where they are, what they are, what is cut."""

import json

import numpy as np
import pytest
from PIL import Image

from conftest import shirt_photo
from flkm.photokit import PhotoKitError, logo

RED, BLACK, YELLOW, WHITE, BLUE = (200, 30, 40), (20, 20, 20), (240, 200, 0), (255, 255, 255), (30, 70, 160)
MAKER = (BLACK, (0.36, 0.29, 0.42, 0.33))  # upper left chest
CREST = (YELLOW, (0.58, 0.28, 0.64, 0.35))  # upper right chest
SPONSOR = (WHITE, (0.40, 0.42, 0.60, 0.50))  # centred on the chest


def kit_photo(size=800, **kw):
    kw.setdefault("logos", [MAKER, CREST, SPONSOR])
    kw.setdefault("collar", RED)
    return shirt_photo(size=size, **kw)


def roles(cands, side="front"):
    return sorted(logo.logo_role(c, side) for c in cands)


def test_find_logos_finds_maker_crest_and_sponsor():
    cands = logo.find_logos(kit_photo())
    assert roles(cands) == ["crest", "maker", "sponsor"]
    sponsor = [c for c in cands if logo.logo_role(c) == "sponsor"][0]
    assert sponsor["tx"] == pytest.approx(0.5, abs=0.02) and sponsor["tw"] == pytest.approx(0.5, abs=0.03)
    assert sponsor["cy"] == pytest.approx((0.46 - 0.15) / 0.75, abs=0.02)
    a = np.array(sponsor["image"])
    assert a[a.shape[0] // 2, a.shape[1] // 2, 3] == 255 and a[0, 0, 3] == 0  # the logo opaque, the cloth around cut


def test_find_logos_on_a_big_photo_measures_the_same():
    small, big = logo.find_logos(kit_photo()), logo.find_logos(kit_photo(size=1600))
    assert roles(big) == roles(small)
    assert [round(c["tx"], 2) for c in big] == pytest.approx([round(c["tx"], 2) for c in small], abs=0.01)
    assert max(c["box"][2] for c in big) > 800  # boxes in the photo's own pixels


def test_find_logos_limit():
    assert len(logo.find_logos(kit_photo(), limit=1)) == 1


def test_find_logos_on_stripes_does_not_take_the_stripes():
    stripes = [(BLUE, x, x + 0.04) for x in (0.32, 0.40, 0.48, 0.56, 0.64)]
    cands = logo.find_logos(kit_photo(stripes=stripes, logos=[(WHITE, (0.38, 0.50, 0.62, 0.56))]))
    assert roles(cands) == ["sponsor"]


def test_logo_on_a_tall_panel_is_found_inside_it():
    panel = [(BLUE, 0.34, 0.44)]  # a stripe narrower than the fabric test, holding the maker
    cands = logo.find_logos(kit_photo(stripes=panel, logos=[(WHITE, (0.37, 0.29, 0.41, 0.33))]))
    assert "maker" in roles(cands)
    assert not [c for c in cands if c["h"] > 0.5]  # the panel itself is not a logo


def test_logo_role():
    base = {"tx": 0.5, "tw": 0.4, "cy": 0.4, "w": 0.3, "h": 0.1}
    assert logo.logo_role(base) == "sponsor"
    assert logo.logo_role(dict(base, tx=0.22, tw=0.12, cy=0.22)) == "maker"
    assert logo.logo_role(dict(base, tx=0.78, tw=0.12, cy=0.22)) == "crest"
    assert logo.logo_role(dict(base, tx=0.5, tw=0.12, cy=0.22)) == "other"  # high in the middle: neither
    assert logo.logo_role(dict(base, tx=0.0)) == "other"  # off the torso
    assert logo.logo_role(dict(base, tx=1.0)) == "other"
    assert logo.logo_role(dict(base, tw=0.03)) == "other"  # too thin
    assert logo.logo_role(dict(base, h=0.7)) == "other"  # tall: a stripe
    assert logo.logo_role(dict(base, cy=0.05)) == logo.logo_role(dict(base, cy=0.9)) == "other"
    assert logo.logo_role(base, "back") == "sponsor"
    assert logo.logo_role(dict(base, tx=0.7), "back") == "other"


def test_share_inside():
    assert logo.share_inside((0, 0, 10, 10), (5, 0, 20, 10)) == 0.5
    assert logo.share_inside((0, 0, 0, 10), (0, 0, 10, 10)) == 0


def test_merge_keeps_the_bigger_box_holding_the_other():
    out = [{"box": [10, 10, 50, 30]}]
    logo._merge(out, {"box": [8, 10, 50, 30]})  # the same logo with its first letter: replaces
    assert out == [{"box": [8, 10, 50, 30]}]
    logo._merge(out, {"box": [9, 11, 49, 29]})  # the same logo, smaller: dropped
    assert out == [{"box": [8, 10, 50, 30]}]
    logo._merge(out, {"box": [100, 100, 120, 120]})
    assert len(out) == 2
    assert logo._iou([0, 0, 0, 0], [0, 0, 0, 0]) == 0


def test_unions_and_fragments_are_dropped():
    top, bottom = {"box": [0, 0, 100, 20]}, {"box": [0, 30, 100, 50]}
    union = {"box": [0, 0, 100, 50]}
    word, piece = {"box": [200, 0, 300, 20]}, {"box": [210, 2, 250, 18]}
    side = [{"box": [400, 0, 440, 20]}, {"box": [450, 0, 490, 20]}, {"box": [400, 0, 490, 20]}]
    kept = logo._drop_unions_and_fragments([top, bottom, union, word, piece] + side)
    assert kept == [top, bottom, word, side[2]]


def test_find_torso_edges():
    g = np.zeros((10, 20), bool)
    g[:, 5:15] = True
    assert logo.find_torso_edges(g, 0, 20, 0, 10) == (5, 15)
    g[:, 9:11] = False  # nothing at the centre: the whole garment box
    assert logo.find_torso_edges(g, 0, 20, 0, 10) == (0, 20)
    g[:] = True
    assert logo.find_torso_edges(g, 0, 20, 0, 10) == (0, 20)


def test_find_fabric_colours_leaves_out_a_big_sponsor():
    im = kit_photo(logos=[(WHITE, (0.32, 0.40, 0.68, 0.60))])
    pal = logo.find_fabric_colours(im)
    assert pal == [pal[0]] and sum(abs(a - b) for a, b in zip(pal[0], RED)) < 30
    assert len(logo.find_fabric_colours(im, min_share=0.0, min_spread=0)) >= 2


def test_find_fabric_colours_keeps_the_first_when_nothing_is_spread():
    assert len(logo.find_fabric_colours(kit_photo(), min_spread=2)) == 1


def test_find_fabric_colours_of_tiny_shares():
    im = kit_photo(logos=[], sleeve=BLACK)
    assert len(logo.find_fabric_colours(im, min_share=0.99)) == 1  # no colour that big: the biggest one


def test_logo_alpha_keeps_letters_inside_a_plate():
    crop = np.zeros((60, 100, 3), np.uint8)
    crop[:] = RED
    crop[10:50, 10:90] = WHITE  # a plate...
    crop[20:40, 20:80] = RED  # ...with big red letters on it: they stay
    crop[28:31, 45:48] = RED  # ...unless tiny (the hole of a letter)
    al = logo._logo_alpha(crop, fabric=[RED])
    assert al[30, 30] == 255 and al[15, 15] == 255 and al[2, 2] == 0


def test_logo_alpha_with_two_cloth_colours_and_a_border_colour_off_the_fabric():
    crop = np.zeros((60, 100, 3), np.uint8)
    crop[:, :50], crop[:, 50:] = RED, BLUE  # the logo on a seam between two panels
    crop[20:40, 30:70] = WHITE
    crop[:5, :] = YELLOW  # the logo touching the crop edge: not cloth
    al = logo._logo_alpha(crop, fabric=[RED, BLUE])
    assert al[30, 50] == 255 and al[50, 10] == 0 and al[50, 90] == 0 and al[2, 50] == 255
    assert logo._logo_alpha(crop)[2, 50] == 0  # without the fabric colours the border is all cloth


def test_cut_logos_writes_pictures_and_measurements(tmp_path):
    photo = tmp_path / "ref" / "home_1.png"
    photo.parent.mkdir()
    kit_photo().save(photo)
    files = logo.cut_logos(str(photo), str(tmp_path / "logos"))
    assert [p.split("\\")[-1].split("/")[-1] for p in files] == ["home_1_c01.png", "home_1_c02.png", "home_1_c03.png"]
    meta = json.loads((tmp_path / "logos" / "_candidates_home_1.json").read_text(encoding="utf-8"))
    assert sorted(m["role"] for m in meta) == ["crest", "maker", "sponsor"]
    assert set(meta[0]) == {"file", "box", "cx", "cy", "w", "h", "tx", "tw", "role"}


def test_cut_logos_of_a_back_photo(tmp_path):
    photo = tmp_path / "back_home_1.png"
    kit_photo(logos=[(WHITE, (0.40, 0.30, 0.60, 0.36))]).save(photo)
    logo.cut_logos(str(photo), str(tmp_path))
    meta = json.loads((tmp_path / "_candidates_back_home_1.json").read_text(encoding="utf-8"))
    assert [m["role"] for m in meta] == ["sponsor"]


def test_join_candidates_makes_one_logo_and_a_redo_replaces_it(tmp_path):
    photo = tmp_path / "home_1.png"
    left, right = (WHITE, (0.40, 0.44, 0.48, 0.50)), (WHITE, (0.52, 0.44, 0.60, 0.50))
    kit_photo(logos=[left, right]).save(photo)
    logo.cut_logos(str(photo), str(tmp_path))
    joined = logo.join_candidates(str(photo), [1, 2], str(tmp_path))
    assert joined.endswith("home_1_j01-02.png")
    im = Image.open(joined)
    assert im.width > 2.2 * im.height  # both halves
    logo.join_candidates(str(photo), [1, 2], str(tmp_path))
    meta = json.loads((tmp_path / "_candidates_home_1.json").read_text(encoding="utf-8"))
    assert [m["file"] for m in meta].count("home_1_j01-02.png") == 1


def test_join_logos_drops_a_stroke_or_clips_it():
    word = (WHITE, (0.46, 0.44, 0.54, 0.50))
    stroke = (WHITE, (0.32, 0.47, 0.68, 0.48))  # a line of the same colour crossing the torso and the word
    speck = (WHITE, (0.45, 0.60, 0.452, 0.602))
    im = kit_photo(logos=[word, stroke, speck])
    box = [int(0.45 * 800), int(0.43 * 800), int(0.55 * 800), int(0.51 * 800)]
    with pytest.raises(PhotoKitError):
        logo.join_logos(im, [box])  # word and stroke are one part, mostly outside the box
    c = logo.join_logos(im, [box], clip=True)
    assert c["w"] == pytest.approx(0.10 / 0.8, abs=0.02)


def test_wide_part_is_split_by_colour():
    # a white sponsor glued to a black band across shoulders and sleeves, wider than a logo can be: split by colour,
    # the sponsor stays and the band goes
    band = (BLACK, (0.12, 0.30, 0.88, 0.34))
    glued = (WHITE, (0.42, 0.34, 0.58, 0.40))
    cands = logo.find_logos(kit_photo(logos=[band, glued]))
    assert [c["w"] < 0.3 for c in cands] == [True] and logo.logo_role(cands[0]) == "sponsor"


def test_tall_part_of_mixed_colours_stays_one_candidate():
    rungs = [((BLACK, WHITE, BLUE)[i % 3], (0.47, 0.30 + i * 0.01, 0.53, 0.31 + i * 0.01)) for i in range(45)]
    cands = logo.find_logos(kit_photo(logos=rungs))
    assert [logo.logo_role(c) for c in cands] == ["other"] and cands[0]["h"] > 2 * cands[0]["w"]


def test_width_of_an_empty_mask():
    assert logo._width(np.zeros((3, 3), bool)) == 0


# the back of a player's shirt: name, number (two digits), a sponsor under them
NAME = (WHITE, (0.42, 0.22, 0.58, 0.26))
DIGITS = [(WHITE, (0.40, 0.30, 0.48, 0.55)), (WHITE, (0.52, 0.30, 0.60, 0.55))]
UNDER = (WHITE, (0.42, 0.65, 0.58, 0.70))


def mark(cx, cy, w, h, tx=None, tw=None):
    return {"cx": cx, "cy": cy, "w": w, "h": h, "tx": cx if tx is None else tx, "tw": w if tw is None else tw}


def test_player_marks_are_the_number_and_the_name_above_it():
    digits = [mark(0.44, 0.37, 0.1, 0.33, tx=0.35), mark(0.56, 0.37, 0.1, 0.33, tx=0.65)]
    name = mark(0.5, 0.12, 0.2, 0.05, tx=0.5, tw=0.4)
    sponsor = mark(0.5, 0.7, 0.2, 0.07)
    assert logo.player_marks(digits + [name, sponsor]) == digits + [name]
    assert logo.player_marks([name, sponsor]) == []  # no number: nothing is the player's
    stripe = mark(0.5, 0.5, 0.05, 0.85)  # a stripe down the whole back is not a number
    assert logo.player_marks([stripe, name]) == []
    one = mark(0.5, 0.4, 0.25, 0.3)  # a number cut as one piece ("10" glued together)
    high = mark(0.5, 0.05, 0.2, 0.04)  # far above the number: not the name
    assert logo.player_marks([one, high, sponsor]) == [one]


def test_cut_logos_of_a_back_photo_marks_the_number_and_the_name(tmp_path):
    photo = tmp_path / "back_home_1.png"
    kit_photo(logos=[NAME, *DIGITS, UNDER]).save(photo)
    logo.cut_logos(str(photo), str(tmp_path))
    meta = json.loads((tmp_path / "_candidates_back_home_1.json").read_text(encoding="utf-8"))
    assert sorted(m["role"] for m in meta) == ["player", "player", "player", "sponsor"]
    assert [m["cy"] > 0.6 for m in meta if m["role"] == "sponsor"] == [True]


def test_dark_marks_on_a_back_with_sleeves_of_their_colour(tmp_path):
    # the sleeves' black is a fabric colour, yet the name, number and sponsor in black on the torso are not fabric:
    # they do not touch the sleeves (Alcione away: black sleeves, black number and sponsor on a khaki back)
    photo = tmp_path / "back_away_1.png"
    marks = [(BLACK, box) for _, box in (NAME, *DIGITS, UNDER)]
    kit_photo(body=(150, 145, 120), sleeve=BLACK, collar=BLACK, logos=marks).save(photo)
    logo.cut_logos(str(photo), str(tmp_path))
    meta = json.loads((tmp_path / "_candidates_back_away_1.json").read_text(encoding="utf-8"))
    assert sorted(m["role"] for m in meta) == ["player", "player", "player", "sponsor"]
