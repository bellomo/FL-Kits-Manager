"""What a product photo shows (from its file name) and where the garment is on it."""

import numpy as np
import pytest
from PIL import Image

from conftest import shirt_photo
from flkm.photokit import photo


@pytest.mark.parametrize(
    "name,expected",
    [
        ("h1.png", ("home", "shirt")),
        ("hs.png", ("home", "shorts")),
        ("hso.png", ("home", "socks")),
        ("a2.png", ("away", "shirt")),
        ("as_.png", ("away", "shorts")),
        ("aso.png", ("away", "socks")),
        ("t1.png", ("third", "shirt")),
        ("g1.png", ("gk", "shirt")),
        ("home_front.jpg", ("home", "shirt")),
        ("away_shorts_1.png", ("away", "shorts")),
        ("gk_socks.webp", ("gk", "socks")),
        ("back_home.png", ("home", "back")),
        ("team.png", (None, None)),
        ("_grid.png", (None, None)),
        ("asb1.png", (None, None)),
        ("h1.txt", (None, None)),
    ],
)
def test_kit_part_reads_the_file_name(name, expected):
    assert photo.kit_part(name) == expected


def test_photo_side():
    assert photo.photo_side("ref/back_home_1.png") == "back"
    assert photo.photo_side("ref/home_1.png") == "front"


def test_rgb_array_turns_transparent_pixels_black():
    im = Image.new("RGBA", (2, 1), (200, 100, 50, 255))
    im.putpixel((1, 0), (200, 100, 50, 0))
    a = photo.rgb_array(im)
    assert a[0, 0].tolist() == [200, 100, 50] and a[0, 1].tolist() == [0, 0, 0]


def test_small_array_takes_a_path_and_shrinks(tmp_path):
    p = tmp_path / "h1.png"
    shirt_photo(size=800).save(p)
    assert photo.small_array(p).shape == (400, 400, 3)
    assert photo.small_array(str(p)).shape == (400, 400, 3)
    assert photo.small_array(shirt_photo(size=100)).shape == (100, 100, 3)


def test_background_is_the_border_median():
    assert photo.background_colour(np.array(shirt_photo(bg=(250, 250, 250)))) == (250, 250, 250)


def test_garment_mask_leaves_out_the_background():
    m = photo.garment_mask(np.array(shirt_photo()))
    assert not m[5, 5] and m[200, 200]


def test_garment_mask_of_a_plain_image_is_everything():
    a = np.zeros((50, 50, 3), np.uint8)
    a[:] = (10, 200, 10)
    assert photo.garment_mask(a).all()


def test_label_regions_counts_4_connected_regions():
    m = np.zeros((5, 5), bool)
    m[0, 0] = m[0, 1] = True  # one region
    m[1, 2] = True  # touches (0, 1) only diagonally: a second one
    m[4, 4] = True
    lab, n = photo.label_regions(m)
    assert n == 3 and lab[0, 0] == lab[0, 1] != lab[1, 2] and lab[2, 2] == 0


def test_filled_garment_mask_keeps_a_white_sponsor_on_a_white_background():
    a = np.array(shirt_photo(logos=[((255, 255, 255), (0.40, 0.40, 0.60, 0.50))]))
    assert not photo.garment_mask(a)[180, 200]
    filled = photo.filled_garment_mask(a)
    assert filled[180, 200] and not filled[5, 5]
