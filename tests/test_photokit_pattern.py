"""Stripes, panels and blocks read from shirt photos and placed on the texture."""

import numpy as np
from PIL import Image

from conftest import shirt_photo
from flkm.photokit import pattern
from flkm.photokit.colour import colour_distance

RED, BLUE, WHITE, BLACK = (200, 30, 40), (30, 70, 160), (255, 255, 255), (20, 20, 20)
RED_HEX, BLUE_HEX = "#c81e28", "#1e46a0"


def photo(**kw):
    kw.setdefault("collar", RED)
    return shirt_photo(size=800, **kw)


def near(a, b, tol=12):
    return colour_distance(a, b) < tol


def blue_rects(res):
    return [r for r in res["rects"] if near(r["color"], BLUE_HEX)]


def test_plain_shirt_has_no_rects():
    res = pattern.read_pattern(photo())
    assert near(res["body"], RED_HEX) and res["rects"] == [] and 0.9 < res["hem"] <= 1


def test_vertical_stripes_become_rects_on_the_front():
    stripes = [(BLUE, x, x + 0.04) for x in (0.34, 0.42, 0.50, 0.58)]
    res = pattern.read_pattern(photo(stripes=stripes))
    rects = blue_rects(res)
    assert len(rects) == 4 and near(res["body"], RED_HEX)
    # the first stripe is 0.04 to 0.08 of the image right of the torso edge (0.30), the torso 0.40 wide
    assert sorted(r["x"] for r in rects)[0] == [pattern.texture_x(0.1), pattern.texture_x(0.2)]
    assert all(r["y"] == list(pattern.FRONT_Y) for r in rects)  # collar seam to hem


def test_a_sponsor_crossing_a_stripe_does_not_cut_it():
    stripes = [(BLUE, 0.48, 0.52)]
    sponsor = (WHITE, (0.40, 0.42, 0.60, 0.50))
    rects = blue_rects(pattern.read_pattern(photo(stripes=stripes, logos=[sponsor])))
    assert len(rects) == 1


def test_horizontal_band_across_the_torso():
    band = (BLUE, (0.30, 0.55, 0.70, 0.65))
    rects = blue_rects(pattern.read_pattern(photo(logos=[band])))
    assert len(rects) == 1 and rects[0]["x"] == list(pattern.BODY_X)
    assert pattern.FRONT_Y[0] < rects[0]["y"][0] < rects[0]["y"][1] < pattern.FRONT_Y[1]


def test_side_panels_are_paired_and_go_round_the_flanks():
    panels = [(BLUE, (0.30, 0.30, 0.36, 0.90)), (BLUE, (0.645, 0.30, 0.70, 0.90))]  # not quite symmetric
    rects = blue_rects(pattern.read_pattern(photo(logos=panels)))
    assert len(rects) == 2
    left, right = sorted(rects, key=lambda r: r["x"][0])
    assert left["x"][0] == pattern.BODY_X[0] and right["x"][1] == pattern.BODY_X[1]
    assert left["x"][1] + right["x"][0] == 2048  # the same width, symmetric about the torso centre
    assert left["y"] == right["y"]


def test_read_pattern_of_a_back_photo_mirrors_x():
    res = pattern.read_pattern(photo(stripes=[(BLUE, 0.34, 0.38)]), side="back")
    (r,) = blue_rects(res)
    assert r["x"][0] > 1024 and r["y"][0] == pattern.BACK_Y[0] and r["y"][1] <= pattern.BACK_Y[1]


def test_read_pattern_debug():
    res = pattern.read_pattern(photo(), debug=True)
    assert res["_grid"].shape[1] == pattern.COLS and res["_shade"][res["_body"]] == res["body"]


def test_read_pattern_of_a_garment_split_in_two():
    a = np.full((400, 400, 3), 255, np.uint8)
    a[50:350, 60:190] = RED  # two halves with a gap down the middle
    a[50:350, 210:340] = RED
    res = pattern.read_pattern(Image.fromarray(a))
    assert near(res["body"], RED_HEX)


def test_texture_mapping():
    assert pattern.texture_x(0.5) == 1024 and pattern.texture_x(0) == 764 and pattern.texture_x(0, back=True) == 1284
    assert pattern.front_texture_y(0.0, 0.98) == pattern.FRONT_Y[0]  # clamped at the collar seam
    assert pattern.front_texture_y(0.98, 0.98) == pattern.FRONT_Y[1]
    assert pattern.front_texture_y(0.4, 0.98) == round(897 + 1133 * 0.4)
    assert pattern.back_texture_y(0.98, 0.98) == pattern.BACK_Y[0]
    assert pattern.back_texture_y(0.0, 0.98) == pattern.BACK_Y[1]  # clamped
    assert pattern.back_texture_y(0.4, 0.98) == round(1155 - 1133 * 0.4)
    for y in (1200, 1700):
        assert pattern.front_texture_y(pattern._front_cy(y, 0.98), 0.98) == y


def test_mirror_rects_to_back():
    front = [
        {"region": "body", "x": [990, 1060], "y": [1012, 1870], "color": "#a"},  # full-height stripe
        {"x": [650, 1330], "y": [1300, 1400], "color": "#b"},  # band across
        {"region": "body", "x": [650, 700], "y": [1012, 1870], "color": "#c"},  # one side panel: not invented
        {"region": "sleeve", "x": [0, 10], "y": [1012, 1870], "color": "#d"},
        {"region": "body", "x": [900, 950], "y": [900, 1000], "color": "#e"},  # on the back already
        {"region": "body", "x": [1300, 1330], "y": [1012, 1870], "color": "#f"},  # the other side panel alone
    ]
    out = pattern.mirror_rects_to_back(front)
    by = {r["color"]: r for r in out}
    assert set(by) == {"#a", "#b"}
    assert by["#a"]["x"] == [988, 1058] and by["#a"]["y"] == [0, 1012]
    assert by["#b"]["x"] == list(pattern.BODY_X) and 0 < by["#b"]["y"][0] < by["#b"]["y"][1] < 1012


def test_mirror_rects_to_back_of_a_stripe_off_the_body_column():
    out = pattern.mirror_rects_to_back([{"x": [1300, 1320], "y": [1012, 1870], "color": "#a"}])
    assert out[0]["x"] == [728, 748]
    off = [{"x": [660, 700], "y": [1012, 1870], "color": "#a"}]  # mirrored, it falls off the body column
    assert pattern.mirror_rects_to_back(off) == []


def test_one_cell_stripes_and_partial_side_pipings_are_left_out():
    thin = [(BLUE, 0.50, 0.505)]  # one grid cell wide
    piping = (BLUE, (0.30, 0.55, 0.31, 0.90))  # on the side seam, only the lower half
    assert blue_rects(pattern.read_pattern(photo(stripes=thin, logos=[piping]))) == []


def test_pair_side_rects():
    shade = {1: "#111111", 2: "#222222"}
    sides = [
        {"left": True, "w": 30, "y": [1100, 1800], "col": 1},
        {"left": False, "w": 40, "y": [1120, 1820], "col": 1},  # its mate: averaged
        {"left": True, "w": 10, "y": [1012, 1870], "col": 2},  # a piping without a mate
    ]
    out = pattern.pair_side_rects(sides, shade)
    assert out[0] == {"region": "body", "x": [1284 + 26 - 35, 1330], "y": [1110, 1810], "color": "#111111"}
    assert out[1]["x"] == [650, 764 - 26 + 35]
    assert out[2] == {"region": "body", "x": [650, 660], "y": [1012, 1870], "color": "#222222"}
    right_piping = pattern.pair_side_rects([{"left": False, "w": 8, "y": [0, 10], "col": 2}], shade)
    assert right_piping[0]["x"] == [1322, 1330]


def test_find_band_rects_straightens_bands():
    grid = np.zeros((20, 20), int)
    grid[:, 5:8] = 1  # a vertical band...
    grid[3, 8] = 1  # ...wobbling by a cell
    grid[15, 15] = 3  # a speck: not a band
    assert pattern.find_band_rects(grid, 0) == [(1, 5, 0, 8, 20)]
    grid = np.zeros((20, 20), int)
    grid[10:12, :] = 2  # a horizontal band...
    grid[12, 3] = 2  # ...wobbling by a cell
    assert pattern.find_band_rects(grid, 0) == [(2, 0, 10, 20, 12)]


def test_is_band():
    m = np.zeros((10, 10), bool)
    m[0:2, 0:2] = True
    assert pattern._is_band(m, 0, 0, 2, 2)  # tall-ish at the side
    m2 = np.zeros((10, 10), bool)
    m2[4:6, 4:6] = True
    assert not pattern._is_band(m2, 4, 4, 6, 6)
    diag = np.eye(10, dtype=bool)
    assert not pattern._is_band(diag, 0, 0, 10, 10)  # fills only a tenth of its box


def test_same_fabric():
    assert pattern._same_fabric((200, 30, 40), (210, 40, 45))  # close
    assert pattern._same_fabric((200, 30, 40), (120, 18, 24))  # a shadow
    assert pattern._same_fabric((120, 18, 24), (200, 30, 40))  # either way
    assert pattern._same_fabric((250, 250, 250), (200, 200, 205))  # whites in different light
    assert pattern._same_fabric((240, 200, 0), (200, 170, 10))  # highlight on yellow
    assert not pattern._same_fabric((20, 30, 90), (120, 180, 240))  # navy and sky blue
    assert not pattern._same_fabric((200, 30, 40), (30, 70, 160))


def test_fill_vertical():
    g = np.array([[1, 2], [0, 0], [3, 0]])
    unknown = np.array([[False, True], [True, True], [False, True]])
    assert pattern._fill_vertical(g, unknown).tolist() == [[1, 2], [1, 0], [3, 0]]


def test_paint_row():
    res = {
        "body": "#a",
        "rects": [
            {"x": [650, 652], "y": [0, 10], "color": "#b"},
            {"region": "sleeve", "x": [650, 660], "y": [0, 10], "color": "#c"},
        ],
    }
    assert pattern.paint_row(res, 5, 650, 654) == ["#b", "#b", "#a", "#a"]
    assert pattern.paint_row(res, 20, 650, 652) == ["#a", "#a"]


def test_read_kit_pattern_mirrors_the_front_without_a_back_photo(tmp_path):
    photo(stripes=[(BLUE, 0.48, 0.52)]).save(tmp_path / "home.png")
    res = pattern.read_kit_pattern(str(tmp_path / "home.png"))
    ys = sorted(r["y"][0] for r in blue_rects(res))
    assert len(ys) == 2 and ys[0] == 0  # front and its mirror on the back


def test_read_kit_pattern_with_a_back_of_another_colour(tmp_path):
    photo(stripes=[(BLUE, 0.48, 0.52)]).save(tmp_path / "home.png")
    photo(body=BLUE).save(tmp_path / "back_home.png")
    res = pattern.read_kit_pattern(str(tmp_path / "home.png"), str(tmp_path / "back_home.png"))
    backs = [r for r in res["rects"] if r["y"] == list(pattern.BACK_Y)]
    assert len(backs) == 1 and near(backs[0]["color"], BLUE_HEX) and backs[0]["x"] == list(pattern.BODY_X)
    photo().save(tmp_path / "back_home.png")  # a back of the body's colour: nothing added
    res = pattern.read_kit_pattern(str(tmp_path / "home.png"), str(tmp_path / "back_home.png"))
    assert len(blue_rects(res)) == 1
