"""Product photos of a kit: what a photo shows, from its file name, and where the garment is on it.

File names (both styles work):

- short: h1 a2 t1 g1 = shirt, hs as_ ts = shorts, hso aso = socks (h home, a away, t third, g goalkeeper);
- long: home_*.png, away_shorts_*.png, gk_socks.png, back_home.png (the back of the shirt).
"""

import os
import re
from collections import deque

import numpy as np
from PIL import Image

KITS = {"h": "home", "a": "away", "t": "third", "g": "gk"}
EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


def kit_part(name: str) -> tuple[str | None, str | None]:
    """File name -> (kit, part) with part in shirt/shorts/socks/back, or (None, None)."""
    stem, ext = os.path.splitext(name.lower())
    if ext not in EXTENSIONS or stem.startswith("_"):
        return None, None
    m = re.match(r"^([hatg])(\d+|so|s_?)$", stem)
    if m:
        part = {"so": "socks"}.get(m.group(2), "shorts" if m.group(2).startswith("s") else "shirt")
        return KITS[m.group(1)], part
    m = re.match(r"^back_(home|away|third|gk)(_.*)?$", stem)
    if m:
        return m.group(1), "back"
    m = re.match(r"^(home|away|third|gk)(?:_(shorts|socks|back))?(_.*)?$", stem)
    if m:
        return m.group(1), m.group(2) or "shirt"
    return None, None


def photo_side(name: str) -> str:
    """'back' for a photo of the back of a shirt (back_home_1.png), else 'front'."""
    return "back" if os.path.basename(name).lower().startswith("back") else "front"


def rgb_array(im: Image.Image) -> np.ndarray:
    """RGB array; transparent pixels become pure black (the background of transparent PNGs)."""
    a = np.array(im.convert("RGBA"))
    rgb = a[..., :3].copy()
    rgb[a[..., 3] < 128] = 0
    return rgb


def small_array(im) -> np.ndarray:
    """RGB array of a photo (an image or a path) at most 400 pixels wide and high: enough for colours, and fast."""
    if isinstance(im, (str, os.PathLike)):
        im = Image.open(im)
    im = im.convert("RGB")
    im.thumbnail((400, 400))
    return np.array(im)


def background_colour(a: np.ndarray) -> tuple[int, int, int]:
    """Median colour of the image border (product photos have a plain background)."""
    b = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    return tuple(int(v) for v in np.median(b[:, :3], axis=0))


def garment_mask(a: np.ndarray, tol: int = 40) -> np.ndarray:
    """True where the pixel is far from the background; the whole image if nothing stands out."""
    d = np.abs(a[..., :3].astype(int) - np.array(background_colour(a))).sum(2)
    m = d > tol
    return m if m.any() else np.ones(m.shape, bool)


def label_regions(mask: np.ndarray) -> tuple[np.ndarray, int]:
    """4-connected regions of a mask: (labels, count); label 0 is outside the mask."""
    lab = np.zeros(mask.shape, np.int32)
    n = 0
    h, w = mask.shape
    for y, x in zip(*np.nonzero(mask)):
        if lab[y, x]:
            continue
        n += 1
        lab[y, x] = n
        q = deque([(y, x)])
        while q:
            cy, cx = q.popleft()
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                    lab[ny, nx] = n
                    q.append((ny, nx))
    return lab, n


def filled_garment_mask(a: np.ndarray) -> np.ndarray:
    """Garment mask with holes filled: a white sponsor on a white-background photo is part of the shirt; only
    background-coloured areas connected to the image border are background."""
    g = garment_mask(a)
    lab, _ = label_regions(~g)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    return g | ((lab > 0) & ~np.isin(lab, list(border)))
