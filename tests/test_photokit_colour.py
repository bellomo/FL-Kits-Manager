"""Kit colours measured on product photos, and the colour helpers (contrast, shades, readable colour)."""

import numpy as np
from PIL import Image

from conftest import shirt_photo
from flkm.photokit import colour

RED, BLACK, YELLOW = (200, 30, 40), (20, 20, 20), (240, 200, 0)


def near(a, b, tol=10):
    return colour.colour_distance(a, b) < tol


def test_hex_round_trip():
    assert colour.rgb_to_hex((216, 36, 44)) == "#d8242c"
    assert colour.hex_to_rgb("#d8242c") == (216, 36, 44)
    assert colour.hex_to_rgb("d8242c") == (216, 36, 44)


def test_colour_distance():
    assert colour.colour_distance("#000000", "#030400") == 5


def test_contrast():
    assert round(colour.contrast("#ffffff", "#000000")) == 21
    assert colour.contrast("#123456", "#123456") == 1
    assert colour.contrast("#000000", "#ffffff") == colour.contrast("#ffffff", "#000000")


def test_is_shade():
    assert colour.is_shade("#808080", "#c81e28")  # a mid grey: a fold
    assert colour.is_shade("#7a1218", "#c81e28")  # the body's red, darker
    assert not colour.is_shade("#1f4c9c", "#c81e28")  # blue on red: a real trim
    assert not colour.is_shade("#c01c26", "#c81e28")  # nearly as light: the body itself
    assert not colour.is_shade("#ffffff", "#c81e28")


def test_secondary_colour_skips_the_body_and_its_shades():
    measured = [("#c81e28", 0.6), ("#7a1218", 0.2), ("#f0c800", 0.1)]
    assert colour.secondary_colour("#c81e28", measured) == "#f0c800"
    assert colour.secondary_colour("#c81e28", measured[:2]) is None


def test_readable_colour():
    assert colour.readable_colour("#c81e28", "#f0c800") == "#f0c800"  # yellow on red reads
    assert colour.readable_colour("#c81e28", "#d02a30") == "#ffffff"  # too close: white
    assert colour.readable_colour("#f4eecc") == "#111111"  # cream: near-black


def test_dominant_colours_biggest_first():
    d = colour.dominant_colours(shirt_photo(sleeve=BLACK), k=4)
    assert near(d[0][0], "#c81e28") and near(d[1][0], "#141414")
    assert abs(sum(f for _, f in d) - 1.0) < 1e-6 and d[0][1] > d[1][1]


def test_dominant_colours_merges_near_colours():
    d = colour.dominant_colours(shirt_photo(sleeve=(205, 34, 44)), k=4)
    assert len([c for c, _ in d if near(c, "#c81e28", 20)]) == 1


def test_dominant_colours_of_an_empty_mask():
    im = Image.fromarray(np.zeros((20, 20, 3), np.uint8))
    assert colour.dominant_colours(im, k=3, mask=np.zeros((20, 20), bool)) == []


def test_dominant_colours_of_a_shaded_area_is_the_lit_fabric():
    a = np.zeros((40, 40, 3), np.uint8)
    a[:] = (200, 30, 40)
    a[:, :10] = (100, 15, 20)  # a fold in the shadow, close enough to merge
    d = colour.dominant_colours(Image.fromarray(a), k=1, mask=np.ones((40, 40), bool))
    assert near(d[0][0], "#c81e28", 5)


def test_measure_zones():
    z = colour.measure_zones(shirt_photo(sleeve=BLACK, collar=YELLOW))
    assert near(z["body"], "#c81e28") and near(z["sleeve"], "#141414") and near(z["collar"], "#f0c800")


def test_measure_zones_of_a_blank_image():
    assert colour.measure_zones(Image.new("RGB", (100, 100), (255, 255, 255))) == {}


def test_measure_zones_of_a_photo_without_background():
    a = np.zeros((100, 100, 3), np.uint8)
    a[:] = (200, 30, 40)
    a[40:60, 40:60] = (210, 40, 50)  # close to the border colour: nothing stands out, the whole photo is measured
    z = colour.measure_zones(Image.fromarray(a))
    assert near(z["body"], "#c81e28", 20) and near(z["sleeve"], "#c81e28")


def test_measure_zones_skips_a_zone_outside_the_garment():
    neck = ((255, 255, 255), (0.40, 0.15, 0.60, 0.20))  # a neck opening of the background colour over the collar zone
    assert set(colour.measure_zones(shirt_photo(logos=[neck]))) == {"body", "sleeve"}


def test_measure_folder(tmp_path):
    shirt_photo(sleeve=BLACK).save(tmp_path / "h1.png")
    Image.new("RGB", (60, 60), (31, 76, 156)).save(tmp_path / "hs.png")
    shirt_photo(body=(240, 240, 220)).save(tmp_path / "back_home.png")
    (tmp_path / "notes.txt").write_text("not a photo")
    res = colour.measure_folder(tmp_path)
    assert set(res) == {"home"} and set(res["home"]) == {"shirt", "shorts", "back"}
    shirt = res["home"]["shirt"][0]
    assert shirt["file"] == "h1.png" and near(shirt["zones"]["sleeve"], "#141414")
    assert "zones" not in res["home"]["shorts"][0] and near(res["home"]["shorts"][0]["colours"][0][0], "#1f4c9c")
