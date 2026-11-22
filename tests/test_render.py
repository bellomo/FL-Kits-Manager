"""Kit pictures from a kit texture: unrolled (the texture itself, scaled) and folded (front and back of the shirt with
shorts and socks, re-assembled from the zones of the texture, as the kit looks in the game). Any texture size works:
the zones are measured on 2048x2048 and scaled."""

import pytest
from PIL import Image, ImageDraw

from flkm import render

SLEEVE, BODY, COLLAR, CUFF = (200, 30, 30), (30, 60, 200), (250, 250, 0), (0, 0, 0)
SHORTS, SOCKS = (255, 255, 255), (0, 160, 60)


def zone_texture(size=2048):
    """a texture painted one flat colour per zone, at the places of the game's kit layout"""
    s = size / 2048
    img = Image.new("RGB", (2048, 2048), SLEEVE)
    d = ImageDraw.Draw(img)
    d.rectangle((650, 0, 1329, 1869), fill=BODY)
    d.rectangle((650, 1870, 1329, 2047), fill=COLLAR)
    d.rectangle((0, 0, 27, 639), fill=CUFF)
    d.rectangle((2020, 0, 2047, 639), fill=CUFF)
    d.rectangle((4, 1175, 657, 1969), fill=SHORTS)
    d.rectangle((1386, 1175, 2043, 1969), fill=SHORTS)
    d.rectangle((4, 627, 378, 1174), fill=SOCKS)
    return img if s == 1 else img.resize((size, size), Image.NEAREST)


def near(a, b, tol=12):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def test_unrolled_is_the_texture_scaled():
    out = render.unrolled(zone_texture(1024), 256)
    assert out.size == (256, 256) and out.mode == "RGB"
    assert near(out.getpixel((128, 100)), BODY)


@pytest.mark.parametrize("size", [2048, 1024, 512])
def test_folded_shows_front_and_back(size):
    out = render.folded(zone_texture(size))
    assert out.size == (2 * render.VIEW_W, render.VIEW_H) and out.mode == "RGB"
    w = render.VIEW_W
    for x0 in (0, w):  # front, then back
        assert near(out.getpixel((x0 + 210, 330)), BODY)  # torso
        assert near(out.getpixel((x0 + 90, 160)), SLEEVE)  # sleeves
        assert near(out.getpixel((x0 + w - 90, 160)), SLEEVE)
        assert near(out.getpixel((x0 + 165, 470)), SHORTS)
        assert near(out.getpixel((x0 + 167, 600)), SOCKS)
        assert out.getpixel((x0 + 10, 10)) == render.BACKGROUND
    assert near(out.getpixel((210, 150)), BODY)  # upper front (where the logos are)
    assert near(out.getpixel((w + 210, 78)), COLLAR)  # collar band on the back


def test_folded_cuffs_and_neck_take_the_colours_of_the_texture():
    out = render.folded(zone_texture(1024))
    assert near(out.getpixel((150, 72)), COLLAR)  # collar line on the shoulder
    assert near(out.getpixel((67, 220)), CUFF)  # cuff band at the end of the left sleeve


def test_perspective_solver_maps_corners():
    c = render.perspective_coeffs([(0, 0), (10, 0), (10, 20), (0, 20)], [(0, 0), (5, 0), (5, 10), (0, 10)])
    a, b, cc, d, e, f, g, h = c
    x, y = 10, 20
    den = g * x + h * y + 1
    assert (round((a * x + b * y + cc) / den, 6), round((d * x + e * y + f) / den, 6)) == (5, 10)


def test_singular_quad_is_refused():
    with pytest.raises(ValueError):
        render.perspective_coeffs([(0, 0)] * 4, [(0, 0), (1, 0), (1, 1), (0, 1)])
