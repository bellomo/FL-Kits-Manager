"""The textures of a team folder in one call."""

import json

import numpy as np
from PIL import Image

from flkm.photokit import build

KIT = {"body": "#c81e28", "shorts": "#111111"}


def test_build_team_writes_a_texture_per_kit(tmp_path, monkeypatch):
    a = np.zeros((40, 40, 4), np.uint8)
    a[5:35, 5:35] = (200, 160, 0, 255)
    Image.fromarray(a).save(tmp_path / "crest.png")
    kits = {"gk": dict(KIT, body="#00ff00"), "home": KIT, "training": KIT}
    (tmp_path / "team.json").write_text(json.dumps({"crest": "crest.png", "kits": kits}), encoding="utf-8")
    monkeypatch.chdir(tmp_path.parent)
    done = build.build_team(tmp_path.name)
    assert list(done) == ["home", "gk"]  # kit order; other names left out
    assert done["home"] == str(tmp_path / "home.png")
    img = Image.open(done["gk"])
    assert img.size == (2048, 2048) and img.getpixel((1024, 1500))[:3] == (0, 255, 0)
    assert img.getpixel((1142, 1135))[:3] == (200, 160, 0)  # the crest
