"""A 2048x2048 kit texture painted from a spec (the layout of the game's kits, measured on Mod Studio output).

Zones of the texture (kit_zones.png marks the body and the white areas; the rest is cut at fixed coordinates):
body = centre column x 650..1330 (back on top y 0..1012, front below, collar strip y >= 1870), sleeves = sides,
cuffs = thin strips, socks = side blocks x < 400 / x > 1650, y 590..1170 (logos at y~900: maker x~80 / 1968, club
x~255 / 1790), shorts = lower side blocks.

A spec: {"body", "sleeve", "cuff", "collar", "shorts", "socks": hex colours; optional "body_pattern",
"sleeve_pattern", "side_panels", "rects", "diag", "cuff_bands", "shorts_stripe", "socks_bands"; "logos": [{"file" or
"text", "x", "y", "h" or "w", optional "color", "rotate", "box", "outline", "split_x", "color_right", "tint",
"font"}]}.
"""

import functools
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from flkm.photokit.colour import hex_to_rgb

SIZE = 2048
ZONES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kit_zones.png")


@functools.cache
def zone_masks() -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray]:
    """({zone: mask} for body, collar, cuff, shorts, socks, sleeve; xs; ys) of the texture. Cached: do not change the
    arrays."""
    lab = np.array(Image.open(ZONES_FILE))
    ys, xs = np.mgrid[0:SIZE, 0:SIZE]
    white = lab == 3
    cuff = white & (
        ((ys < 1170) & (((xs >= 488) & (xs < 514)) | ((xs >= 1535) & (xs < 1561))))
        | ((xs < 28) & (ys < 640))
        | ((xs >= 2020) & (ys < 640))
    )
    # socks = the side blocks half-way down (seen on the game's Milan kit: rings + logos)
    socks = white & ~cuff & (ys >= 560) & (ys < 1175) & ((xs < 400) | (xs > 1650))
    shorts = white & ~cuff & ~socks & (ys > 560) & (ys < 1990) & ((xs < 660) | (xs > 1385))
    body = lab == 1
    collar = body & (ys >= 1870)
    body = body & ~collar
    sleeve = ~(body | collar | cuff | shorts | socks)
    zones = dict(body=body, collar=collar, cuff=cuff, shorts=shorts, socks=socks, sleeve=sleeve)
    return zones, xs, ys


def band_index(spec: dict, xs: np.ndarray, ys: np.ndarray, axis: str) -> np.ndarray:
    """Colour index of each pixel for a repeating band pattern ({"period", "bands": [(start, width)], "offset"}), -1
    between the bands. axis 'x' = vertical stripes."""
    t = (xs if axis == "x" else ys) - spec.get("offset", 0)
    t = np.mod(t, spec["period"])
    out = np.full(xs.shape, -1, np.int16)
    for i, (start, width) in enumerate(spec["bands"]):
        out[(t >= start) & (t < start + width)] = i
    return out


def render_text(text: str, font: str = "bahnschrift.ttf", size: int = 200) -> Image.Image:
    """White text on transparency, tightly cropped with a 10 pixel margin."""
    f = ImageFont.truetype(font, size)
    bb = f.getbbox(text)
    im = Image.new("RGBA", (bb[2] - bb[0] + 20, bb[3] - bb[1] + 20), (255, 255, 255, 0))
    ImageDraw.Draw(im).text((10 - bb[0], 10 - bb[1]), text, font=f, fill=(255, 255, 255, 255))
    return im


def _open_logo(logo) -> Image.Image:
    return logo if isinstance(logo, Image.Image) else Image.open(logo).convert("RGBA")


def _tinted(logo, tint: str) -> Image.Image:
    """Tonal version of a logo in one colour that keeps its details (dark parts darker)."""
    lg = _open_logo(logo)
    g = np.array(lg.convert("L")).astype(float)[..., None] / 255.0
    rgb = np.array(hex_to_rgb(tint), float) * (0.55 + 0.45 * g)
    return Image.fromarray(np.dstack([rgb.clip(0, 255).astype(np.uint8), np.array(lg.getchannel("A"))]), "RGBA")


def paste_logo(
    canvas: Image.Image,
    logo,
    cx: int,
    cy: int,
    h: int | None = None,
    w: int | None = None,
    color: str | None = None,
    rotate: float = 0,
    box: dict | None = None,
    outline: dict | None = None,
    split_x: int | None = None,
    color_right: str | None = None,
    tint: str | None = None,
) -> None:
    """Pastes a logo (a path or an image) centred on (cx, cy), h or w pixels high or wide. color: the logo's shape in
    one colour; box / outline: a solid patch or an outline around it; split_x / color_right: the part right of texture
    x = split_x gets color_right; tint: tonal version in that colour keeping the details."""
    if tint:
        logo = _tinted(logo, tint)
    if split_x is not None and color_right:
        left = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        paste_logo(left, logo, cx, cy, h, w, color, rotate, box, outline)
        right = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        paste_logo(right, logo, cx, cy, h, w, color_right, rotate, box, outline)
        left.paste(right.crop((split_x, 0, SIZE, SIZE)), (split_x, 0))
        canvas.alpha_composite(left)
        return
    lg = _open_logo(logo)
    bb = lg.getchannel("A").getbbox()
    if bb:
        lg = lg.crop(bb)
    if rotate:
        lg = lg.rotate(rotate, expand=True, resample=Image.BICUBIC)
    if w:
        lg = lg.resize((w, round(lg.height * w / lg.width)), Image.LANCZOS)
    else:
        lg = lg.resize((round(lg.width * h / lg.height), h), Image.LANCZOS)
    a = lg.getchannel("A")
    layers = []
    if box:  # solid shape around the text (e.g. sponsor patch)
        r = box.get("pad", 20) | 1
        m = a.point(lambda v: 255 if v > 60 else 0)
        pad = Image.new("L", (m.width + 2 * r, m.height + 2 * r), 0)
        pad.paste(m, (r, r))
        for _ in range(max(1, r // 9)):
            pad = pad.filter(ImageFilter.MaxFilter(19 if r >= 9 else 3))
        layers.append((pad, hex_to_rgb(box["color"]), (-r, -r)))
    if outline:
        r = outline.get("width", 3)
        pad = Image.new("L", (a.width + 2 * r + 2, a.height + 2 * r + 2), 0)
        pad.paste(a, (r + 1, r + 1))
        pad = pad.filter(ImageFilter.MaxFilter(2 * r + 1))
        layers.append((pad, hex_to_rgb(outline["color"]), (-r - 1, -r - 1)))
    if color:
        layers.append((a, hex_to_rgb(color), (0, 0)))
    else:
        layers.append((None, lg, (0, 0)))
    x0, y0 = cx - lg.width // 2, cy - lg.height // 2
    for m, c, (dx, dy) in layers:
        if m is None:
            canvas.alpha_composite(c, (x0, y0))
        else:
            solid = Image.new("RGBA", m.size, c + (255,))
            solid.putalpha(m)
            canvas.alpha_composite(solid, (x0 + dx, y0 + dy))


def _cuff_offset(xs: np.ndarray) -> np.ndarray:
    """Position across the cuff strip (0..25) of each x: the cuff strips run vertically in the texture."""
    return np.where(xs < 1024, np.where(xs < 300, xs, xs - 488), np.where(xs > 1700, 2047 - xs, 1560 - xs))


def paint_texture(spec: dict, base_dir: str = "") -> Image.Image:
    """The RGBA kit texture of a spec; relative logo files are read from base_dir."""
    zone, xs, ys = zone_masks()
    img = np.zeros((SIZE, SIZE, 3), np.uint8)
    img[:] = hex_to_rgb(spec["body"])
    bp = spec.get("body_pattern")  # vertical/horizontal bands
    if bp:
        idx = band_index(bp, xs, ys, bp.get("axis", "x"))
        for i, c in enumerate(bp["colors"]):
            img[zone["body"] & (idx == i)] = hex_to_rgb(c)
    img[zone["sleeve"]] = hex_to_rgb(spec.get("sleeve", spec["body"]))
    sp = spec.get("sleeve_pattern")
    if sp:  # on the sleeves the shirt's vertical stripes run horizontally in the texture
        idx = band_index(sp, xs, ys, sp.get("axis", "y"))
        for i, c in enumerate(sp["colors"]):
            img[zone["sleeve"] & (idx == i)] = hex_to_rgb(c)
    for side in spec.get("side_panels", []):  # bands at both edges of the body column
        w = side["width"]
        m = zone["body"] & (((xs >= 650) & (xs < 650 + w)) | ((xs >= 1330 - w) & (xs < 1330)))
        if "y" in side:
            m &= (ys >= side["y"][0]) & (ys < side["y"][1])
        img[m] = hex_to_rgb(side["color"])
    for rc in spec.get("rects", []):  # tonal bands etc.: {"region": "body", "x": [a, b], "y": [a, b], "color"}
        x = rc.get("x", [0, SIZE])
        m = zone[rc.get("region", "body")] & (xs >= x[0]) & (xs < x[1]) & (ys >= rc["y"][0]) & (ys < rc["y"][1])
        img[m] = hex_to_rgb(rc["color"])
    for dg in spec.get("diag", []):  # diagonal sash: band of 'width' px around the line (x0, y0)-(x1, y1)
        x0, y0, x1, y1 = dg["line"]
        nx, ny = y1 - y0, -(x1 - x0)
        n = (nx * nx + ny * ny) ** 0.5
        dist = np.abs((xs - x0) * nx + (ys - y0) * ny) / n
        m = zone[dg.get("region", "body")] & (dist < dg["width"] / 2)
        if "y" in dg:
            m &= (ys >= dg["y"][0]) & (ys < dg["y"][1])
        img[m] = hex_to_rgb(dg["color"])
    img[zone["cuff"]] = hex_to_rgb(spec.get("cuff", spec.get("sleeve", spec["body"])))
    for start, width, c in spec.get("cuff_bands", []):  # stripes along the cuff
        rel = _cuff_offset(xs)
        img[zone["cuff"] & (rel >= start) & (rel < start + width)] = hex_to_rgb(c)
    img[zone["collar"]] = hex_to_rgb(spec.get("collar", spec["body"]))
    img[zone["shorts"]] = hex_to_rgb(spec["shorts"])
    st = spec.get("shorts_stripe")
    if st:  # stripe along the outer side of each leg
        w = st["width"]
        img[zone["shorts"] & ((xs < 4 + w) | (xs >= 2044 - w))] = hex_to_rgb(st["color"])
    img[zone["socks"]] = hex_to_rgb(spec.get("socks", spec["shorts"]))
    for band in spec.get("socks_bands", []):  # horizontal rings, y measured from the sock top (590)
        m = zone["socks"] & (ys >= 590 + band["y"]) & (ys < 590 + band["y"] + band["h"])
        img[m] = hex_to_rgb(band["color"])
    canvas = Image.fromarray(img).convert("RGBA")
    for lg in spec.get("logos", []):
        if "text" in lg:
            logo = render_text(lg["text"], lg.get("font", "bahnschrift.ttf"))
        else:
            logo = lg["file"] if os.path.isabs(lg["file"]) else os.path.join(base_dir, lg["file"])
        paste_logo(
            canvas,
            logo,
            lg["x"],
            lg["y"],
            h=lg.get("h"),
            w=lg.get("w"),
            color=lg.get("color"),
            rotate=lg.get("rotate", 0),
            box=lg.get("box"),
            outline=lg.get("outline"),
            split_x=lg.get("split_x"),
            color_right=lg.get("color_right"),
            tint=lg.get("tint"),
        )
    return canvas
