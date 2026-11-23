"""The disk cache of kit makers' logos: masks cut from photos, recognised and reused on the next team."""

import numpy as np
from PIL import Image

from flkm import settings
from flkm.photokit import maker


def logo(shape="bar", size=(120, 60), colour=(20, 20, 20, 255)):
    """A maker logo as cut from a photo: its colours on transparency."""
    a = np.zeros((size[1], size[0], 4), np.uint8)
    h, w = size[1], size[0]
    if shape == "bar":
        a[h // 4 : 3 * h // 4, :] = colour
    elif shape == "tick":
        for x in range(w):
            y = int(h - 1 - (h - 1) * abs(x - w / 3) / w * 1.5)
            a[max(0, y - h // 6) : y + 1, x] = colour
    else:  # ring
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
        a[(r < 1) & (r > 0.6)] = colour
    return Image.fromarray(a, "RGBA")


def test_makers_folder_is_in_the_app_data(home):
    assert maker.makers_folder() == settings.home() / "makers"


def test_white_mask_keeps_the_shape_only():
    m = maker.white_mask(logo())
    a = np.array(m)
    assert m.mode == "RGBA" and (a[..., :3] == 255).all()
    assert a[30, 60, 3] == 255 and a[2, 60, 3] == 0


def test_similarity_of_the_same_shape_at_another_size():
    assert maker.similarity(logo(), logo(size=(240, 120))) > 0.9
    assert maker.similarity(logo("bar"), logo("ring")) < 0.6
    assert maker.similarity(logo(), Image.new("RGBA", (10, 10))) == 0


def test_save_find_and_list(tmp_path):
    folder = tmp_path / "makers"
    assert maker.list_makers(folder) == [] and maker.find_maker(logo(), folder) is None
    assert maker.save_maker(logo("tick"), folder) == "maker_1"
    assert maker.save_maker(logo("ring"), folder) == "maker_2"
    assert maker.save_maker(logo("bar"), folder, "errea") == "errea"
    assert maker.list_makers(folder) == ["errea", "maker_1", "maker_2"]
    saved = Image.open(folder / "errea.png")
    assert np.array(saved)[..., :3].min() == 255  # a white mask, like the ones spec.py paints in maker_color
    assert maker.find_maker(logo("ring", size=(90, 45), colour=(250, 0, 0, 255)), folder) == "maker_2"
    assert maker.find_maker(logo("bar", size=(300, 150)), folder) == "errea"
    (folder / "notes.txt").write_text("not a mask")
    assert maker.list_makers(folder) == ["errea", "maker_1", "maker_2"]


def test_new_names_skip_the_used_ones(tmp_path):
    maker.save_maker(logo(), tmp_path, "maker_1")
    maker.save_maker(logo("ring"), tmp_path, "maker_3")
    assert maker.save_maker(logo("tick"), tmp_path) == "maker_2"
    assert maker.save_maker(logo("tick"), tmp_path) == "maker_4"
