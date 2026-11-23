"""The disk cache of kit makers' logos (%APPDATA%\\FLKitsManager\\makers\\<name>.png): white-on-transparent masks cut
from the photos. The game has no separate maker files (makers are painted inside the kit textures), so the first
team of a maker gives its mask; the next teams recognise it by its shape and reuse it, also on kits whose photo hides
the maker. A new mask is named maker_<n> until the user names it."""

import os
import re
from pathlib import Path

import numpy as np
from PIL import Image

from flkm import settings

SHAPE = 64  # side of the square the shapes are compared at
MIN_SIMILARITY = 0.6


def makers_folder() -> Path:
    return settings.home() / "makers"


def white_mask(logo: Image.Image) -> Image.Image:
    """The logo's shape in white on transparency (spec.py paints it in the kit's maker_color)."""
    out = Image.new("RGBA", logo.size, (255, 255, 255, 0))
    out.putalpha(logo.convert("RGBA").getchannel("A"))
    return out


def _shape(logo: Image.Image) -> np.ndarray | None:
    """The logo's opaque pixels, cropped and centred on a SHAPE x SHAPE square keeping its proportions."""
    alpha = logo.convert("RGBA").getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    box = alpha.getbbox()
    if not box:
        return None
    alpha = alpha.crop(box)
    scale = SHAPE / max(alpha.size)
    alpha = alpha.resize((max(1, round(alpha.width * scale)), max(1, round(alpha.height * scale))), Image.NEAREST)
    square = Image.new("L", (SHAPE, SHAPE), 0)
    square.paste(alpha, ((SHAPE - alpha.width) // 2, (SHAPE - alpha.height) // 2))
    return np.array(square) > 0


def similarity(a: Image.Image, b: Image.Image) -> float:
    """How much two logos have the same shape (intersection over union of their shapes, 0 to 1); colours and size do
    not count."""
    sa, sb = _shape(a), _shape(b)
    if sa is None or sb is None:
        return 0.0
    return float((sa & sb).sum() / (sa | sb).sum())


def list_makers(folder) -> list[str]:
    """The names of the cached makers, sorted."""
    folder = Path(folder)
    return sorted(p.stem for p in folder.glob("*.png")) if folder.is_dir() else []


def find_maker(logo: Image.Image, folder, min_similarity: float = MIN_SIMILARITY) -> str | None:
    """The cached maker whose shape is most like the logo's (at least min_similarity), or None."""
    scores = [(similarity(logo, Image.open(Path(folder) / f"{name}.png")), name) for name in list_makers(folder)]
    best = max(scores, default=(0.0, None))
    return best[1] if best[0] >= min_similarity else None


def save_maker(logo: Image.Image, folder, name: str | None = None) -> str:
    """Saves the logo's white mask in the cache as <name>.png (replacing one of that name), or as the first free
    maker_<n>; returns the name."""
    folder = Path(folder)
    if name is None:
        used = {int(m.group(1)) for n in list_makers(folder) if (m := re.fullmatch(r"maker_(\d+)", n))}
        name = f"maker_{next(n for n in range(1, len(used) + 2) if n not in used)}"
    os.makedirs(folder, exist_ok=True)
    white_mask(logo).save(folder / f"{name}.png")
    return name
