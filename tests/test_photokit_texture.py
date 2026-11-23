"""Kit textures painted from a spec: each zone gets its colour, patterns and logos land where the spec says."""

import numpy as np
from PIL import Image

from flkm.photokit import texture

KIT = {
    "body": "#c81e28",
    "sleeve": "#1f4c9c",
    "cuff": "#111111",
    "collar": "#f0c800",
    "shorts": "#ffffff",
    "socks": "#00ff00",
}
# one pixel well inside each zone
AT = {
    "body": (1024, 1500),
    "collar": (1024, 1900),
    "sleeve": (300, 300),
    "cuff": (10, 400),
    "shorts": (300, 1500),
    "socks": (200, 900),
}


def rgb(img, xy):
    return "#%02x%02x%02x" % img.getpixel(xy)[:3]


def crest(path, colour=(200, 160, 0)):
    a = np.zeros((64, 64, 4), np.uint8)
    a[8:56, 8:56] = colour + (255,)
    a[24:40, 24:40] = (255, 255, 255, 255)  # a detail inside the crest
    Image.fromarray(a).save(path)


def test_zone_masks_cover_the_texture_once():
    zones, xs, ys = texture.zone_masks()
    total = sum(m.astype(int) for m in zones.values())
    assert (total == 1).all() and xs.shape == ys.shape == (2048, 2048)
    assert all(zones[name][y, x] for name, (x, y) in AT.items())


def test_every_zone_gets_its_colour():
    img = texture.paint_texture(KIT)
    assert img.size == (2048, 2048) and img.mode == "RGBA"
    for name, xy in AT.items():
        assert rgb(img, xy) == KIT[name], name


def test_missing_colours_fall_back():
    img = texture.paint_texture({"body": "#c81e28", "shorts": "#ffffff"})
    assert rgb(img, AT["sleeve"]) == rgb(img, AT["cuff"]) == rgb(img, AT["collar"]) == "#c81e28"
    assert rgb(img, AT["socks"]) == "#ffffff"
    img = texture.paint_texture({"body": "#c81e28", "sleeve": "#1f4c9c", "shorts": "#ffffff"})
    assert rgb(img, AT["cuff"]) == "#1f4c9c"


def test_band_index():
    xs, ys = np.meshgrid(np.arange(10), np.arange(2))
    idx = texture.band_index({"period": 5, "bands": [(0, 2), (3, 1)], "offset": 1}, xs, ys, "x")
    assert idx[0].tolist() == [-1, 0, 0, -1, 1, -1, 0, 0, -1, 1]
    assert texture.band_index({"period": 2, "bands": [(0, 1)]}, xs, ys, "y")[:, 0].tolist() == [0, -1]


def test_body_and_sleeve_patterns():
    spec = dict(
        KIT,
        body_pattern={"period": 100, "bands": [(0, 50)], "colors": ["#000000"]},
        sleeve_pattern={"period": 100, "bands": [(0, 50)], "colors": ["#ffffff"]},
    )
    img = texture.paint_texture(spec)
    assert rgb(img, (1010, 1500)) == "#000000" and rgb(img, (1060, 1500)) == KIT["body"]
    assert rgb(img, (300, 310)) == "#ffffff" and rgb(img, (300, 360)) == KIT["sleeve"]


def test_side_panels_rects_and_sash():
    spec = dict(
        KIT,
        side_panels=[{"width": 40, "color": "#000000"}, {"width": 20, "color": "#ffffff", "y": [1400, 1600]}],
        rects=[{"x": [1000, 1050], "y": [1100, 1200], "color": "#0000ff"}, {"y": [100, 200], "color": "#00ffff"}],
        diag=[
            {"line": [650, 1100, 1330, 1800], "width": 20, "color": "#ff00ff"},
            {"line": [650, 1100, 1330, 1800], "width": 20, "color": "#ff8800", "y": [1500, 1600]},
        ],
    )
    img = texture.paint_texture(spec)
    assert rgb(img, (660, 1300)) == rgb(img, (1320, 1300)) == "#000000" and rgb(img, (700, 1300)) == KIT["body"]
    assert rgb(img, (660, 1500)) == "#ffffff"
    assert rgb(img, (1020, 1150)) == "#0000ff" and rgb(img, (1020, 150)) == "#00ffff"
    assert rgb(img, (990, 1450)) == "#ff00ff" and rgb(img, (1135, 1600 - 1)) != "#ff00ff"
    assert rgb(img, (1087, 1550)) == "#ff8800"


def test_cuff_bands_shorts_stripe_and_socks_bands():
    spec = dict(
        KIT,
        cuff_bands=[(5, 4, "#ffffff")],
        shorts_stripe={"width": 30, "color": "#000000"},
        socks_bands=[{"y": 100, "h": 20, "color": "#ff0000"}],
    )
    img = texture.paint_texture(spec)
    for x in (6, 495, 1554, 2041):  # the four cuff strips, 5..8 pixels from their outer edge
        assert rgb(img, (x, 1000 if 400 < x < 1700 else 400)) == "#ffffff", x
    assert rgb(img, (20, 1500)) == rgb(img, (2030, 1500)) == "#000000" and rgb(img, (300, 1500)) == "#ffffff"
    assert rgb(img, (200, 700)) == "#ff0000" and rgb(img, (200, 900)) == KIT["socks"]


def test_logos_from_a_file_relative_or_absolute_and_from_text(tmp_path):
    crest(tmp_path / "crest.png")
    spec = dict(
        KIT,
        logos=[
            {"file": "crest.png", "x": 1142, "y": 1135, "h": 108},
            {"file": str(tmp_path / "crest.png"), "x": 900, "y": 1500, "w": 100, "color": "#000000"},
            {"text": "1899", "x": 1024, "y": 960, "h": 34, "rotate": 180, "color": "#ffffff"},
        ],
    )
    img = texture.paint_texture(spec, str(tmp_path))
    assert rgb(img, (1142 - 40, 1135)) == "#c8a000" and rgb(img, (1142, 1135)) == "#ffffff"
    assert rgb(img, (900, 1500)) == "#000000"  # one colour: the white detail is painted too
    a = np.array(img.crop((990, 940, 1060, 980)))
    assert (a[..., :3] == 255).all(2).any()


def test_paste_logo_tint_keeps_the_detail(tmp_path):
    p = tmp_path / "c.png"
    crest(p)
    canvas = Image.new("RGBA", (200, 200), (0, 0, 0, 255))
    texture.paste_logo(canvas, str(p), 100, 100, h=64, tint="#404040")
    outer, detail = canvas.getpixel((100 - 25, 100)), canvas.getpixel((100, 100))
    assert outer[0] < detail[0] <= 0x40  # both in the tint, the white detail lighter


def test_paste_logo_split_colour():
    logo = Image.new("RGBA", (100, 20), (255, 255, 255, 255))
    canvas = Image.new("RGBA", (2048, 2048), (0, 0, 0, 255))
    texture.paste_logo(canvas, logo, 1024, 100, w=100, color="#ff0000", split_x=1024, color_right="#0000ff")
    assert canvas.getpixel((1000, 100))[:3] == (255, 0, 0) and canvas.getpixel((1050, 100))[:3] == (0, 0, 255)


def test_paste_logo_box_and_outline():
    logo = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
    logo.paste((255, 255, 255, 255), (5, 5, 35, 15))
    for box, outline in (
        ({"color": "#00ff00", "pad": 20}, None),
        ({"color": "#00ff00", "pad": 4}, None),
        (None, {"color": "#00ff00", "width": 3}),
    ):
        canvas = Image.new("RGBA", (200, 200), (0, 0, 0, 255))
        texture.paste_logo(canvas, logo, 100, 100, w=30, color="#ffffff", box=box, outline=outline)
        assert canvas.getpixel((100, 100))[:3] == (255, 255, 255)
        assert canvas.getpixel((100, 100 - 6))[:3] == (0, 255, 0)  # just above the logo: the patch or outline


def test_paste_logo_of_a_fully_transparent_image():
    canvas = Image.new("RGBA", (50, 50), (0, 0, 0, 255))
    texture.paste_logo(canvas, Image.new("RGBA", (10, 10), (255, 255, 255, 0)), 25, 25, h=10)
    assert canvas.getpixel((25, 25)) == (0, 0, 0, 255)
