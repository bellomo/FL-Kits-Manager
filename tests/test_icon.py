"""The app's icon: the logo of docs/images/flkm-logo.svg made into flkm/flkm.ico (`python -m flkm.icon`), the icon of
the exe (scripts/build.ps1) and of the app's windows."""

from pathlib import Path

import numpy as np
from PIL import Image

from flkm import icon

LOGO = Path(__file__).resolve().parents[1] / "docs" / "images" / "flkm-logo.svg"


def test_render_svg_keeps_the_transparency_around_the_logo():
    im = icon.render_svg(LOGO, 96)
    assert im.mode == "RGBA" and im.size == (96, 96)
    assert im.getpixel((1, 1))[3] == 0  # outside the green disc
    assert im.getpixel((48, 60))[:3] == (0xF4, 0xF4, 0xF4)  # the white shirt
    assert im.getpixel((48, 90))[:3] == (0x1F, 0x6F, 0x43)  # the green disc under it


def test_write_icon_has_every_windows_size(tmp_path):
    ico = tmp_path / "app.ico"
    icon.write_icon(LOGO, ico)
    with Image.open(ico) as im:
        assert im.format == "ICO" and set(icon.SIZES) <= im.info["sizes"]


def test_the_icon_in_the_repo_is_the_logo():
    """run `python -m flkm.icon` after changing the logo (a small difference allowed: antialiasing elsewhere)"""
    with Image.open(icon.ICON) as im:
        im.size = (256, 256)
        saved = np.asarray(im.convert("RGBA"), dtype=int)
    fresh = np.asarray(icon.render_svg(LOGO, 256), dtype=int)
    assert np.abs(saved - fresh).max() <= 8


def test_app_icon(qapp):
    assert not icon.app_icon().isNull()
