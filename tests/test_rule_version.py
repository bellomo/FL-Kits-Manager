"""Versions are semver (MAJOR.MINOR.PATCH) and the same in flkm/__init__.py, pyproject.toml and the latest entry of
CHANGELOG.md; the release workflow names the zip after it."""

import re
from pathlib import Path

import flkm

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def test_version_is_semver():
    assert SEMVER.match(flkm.__version__)


def test_version_matches_pyproject():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert m and m.group(1) == flkm.__version__


def test_version_is_the_latest_changelog_entry():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"^## (\d+\.\d+\.\d+)", text, re.MULTILINE)
    assert m and m.group(1) == flkm.__version__
