"""Kit colours: hex colours, the colours measured on a product photo (no guessing by eye), contrast."""

import colorsys
import os

import numpy as np
from PIL import Image

from flkm.photokit.photo import garment_mask, kit_part, small_array

# zones of a flat front shirt photo, as fractions of the garment's bounding box (x0, x1, y0, y1)
ZONES = {
    "body": [(0.38, 0.62, 0.45, 0.85)],
    "sleeve": [(0.04, 0.16, 0.12, 0.30), (0.84, 0.96, 0.12, 0.30)],
    "collar": [(0.43, 0.57, 0.0, 0.05)],
}


def hex_to_rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb[:3])


def colour_distance(a: str, b: str) -> float:
    """Euclidean distance of two hex colours in RGB."""
    return sum((x - y) ** 2 for x, y in zip(hex_to_rgb(a), hex_to_rgb(b))) ** 0.5


def _luminance(c: str) -> float:
    def channel(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = hex_to_rgb(c)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    """WCAG contrast ratio of two hex colours (1 to 21)."""
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _hsv(c: str) -> tuple[float, float, float]:
    return colorsys.rgb_to_hsv(*[v / 255.0 for v in hex_to_rgb(c)])


def is_shade(c: str, body: str) -> bool:
    """True if c looks like a shadow or fold of the fabric, not a real trim colour: a mid grey, or the body's own hue
    clearly darker."""
    hc, sc, vc = _hsv(c)
    hb, sb, vb = _hsv(body)
    if sc < 0.15 and 0.25 < vc < 0.8:
        return True
    dh = min(abs(hc - hb), 1 - abs(hc - hb))
    return sb >= 0.15 and sc >= 0.15 and dh < 0.05 and vc < vb * 0.8


def secondary_colour(body: str, colours, min_dist: float = 60) -> str | None:
    """First measured colour clearly different from the body and not a shadow of it, or None."""
    for c, _ in colours:
        if colour_distance(c, body) >= min_dist and not is_shade(c, body):
            return c
    return None


def tone_gain(src: str, dst: str) -> tuple[float, float, float]:
    """How much each channel of a photo's colours is multiplied by to look like another photo of the same kit: the
    same colour measured on both (src -> dst). A dark channel (under 8) tells nothing: it keeps 1."""
    return tuple(d / s if s >= 8 else 1.0 for s, d in zip(hex_to_rgb(src), hex_to_rgb(dst)))


def apply_gain(c: str, gain) -> str:
    """The colour in the other photo's tone (see tone_gain); channels stop at 255."""
    return rgb_to_hex([min(255, round(v * g)) for v, g in zip(hex_to_rgb(c), gain)])


def readable_colour(body: str, secondary: str | None = None) -> str:
    """Colour for numbers and the maker logo: the kit's secondary colour if readable, else white or near-black."""
    if secondary and contrast(body, secondary) >= 3:
        return secondary
    return "#ffffff" if contrast(body, "#ffffff") >= contrast(body, "#111111") else "#111111"


def _lit(px: np.ndarray) -> np.ndarray:
    """Colour of the lit fabric: mean of the pixels between the 55th and 90th brightness percentile (the plain mean
    is pulled down by folds and shadows of the photo)."""
    lum = px @ np.array([0.299, 0.587, 0.114])
    lo, hi = np.percentile(lum, [55, 90])
    sel = px[(lum >= lo) & (lum <= hi)]
    return (sel if len(sel) else px).mean(0)


def dominant_colours(im, k: int = 5, mask=None, merge: float = 30) -> list[tuple[str, float]]:
    """[(hex, share)] of the masked pixels of a photo (an image or a path), biggest first; near colours merged."""
    a = small_array(im)
    if mask is None:
        mask = garment_mask(a)
    px = a[mask]
    if len(px) == 0:
        return []
    q = Image.fromarray(px.reshape(-1, 1, 3)).quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    idx = np.array(q).ravel()
    groups = []  # [rgb_sum, count]
    for i in np.unique(idx):  # the palette entries in use, in palette order
        n = int((idx == i).sum())
        c = _lit(px.reshape(-1, 3)[idx == i])
        for g in groups:
            if np.linalg.norm(g[0] / g[1] - c) < merge:
                g[0] += c * n
                g[1] += n
                break
        else:
            groups.append([c * n, n])
    total = sum(g[1] for g in groups)
    out = [(rgb_to_hex(g[0] / g[1]), g[1] / total) for g in groups]
    return sorted(out, key=lambda x: -x[1])


def measure_zones(im) -> dict[str, str]:
    """{'body', 'sleeve', 'collar'} -> hex of the main colour in that part of a shirt photo; {} for a blank image."""
    a = small_array(im)
    m = garment_mask(a)
    if m.all() and len(np.unique(a.reshape(-1, 3), axis=0)) == 1:
        return {}
    ys, xs = np.nonzero(m)
    x0_, x1_, y0_, y1_ = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    out = {}
    for name, boxes in ZONES.items():
        zm = np.zeros(m.shape, bool)
        for x0, x1, y0, y1 in boxes:
            zm[
                int(y0_ + y0 * (y1_ - y0_)) : int(y0_ + y1 * (y1_ - y0_)) + 1,
                int(x0_ + x0 * (x1_ - x0_)) : int(x0_ + x1 * (x1_ - x0_)) + 1,
            ] = True
        d = dominant_colours(Image.fromarray(a), k=4, mask=zm & m)
        if d:
            out[name] = d[0][0]
    return out


def measure_folder(folder) -> dict:
    """{kit: {part: [{'file', 'colours', ['zones']}]}} for the photos of a folder (see photo.kit_part for the names);
    zones only for shirt photos."""
    res = {}
    for f in sorted(os.listdir(folder)):
        kit, part = kit_part(f)
        if not kit:
            continue
        p = os.path.join(folder, f)
        e = {"file": f, "colours": dominant_colours(p)}
        if part == "shirt":
            e["zones"] = measure_zones(p)
        res.setdefault(kit, {}).setdefault(part, []).append(e)
    return res
