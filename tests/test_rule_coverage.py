"""The rule of CLAUDE.md, 100% coverage, is kept by the coverage settings of pyproject.toml: the run with --cov fails
below 100% (a test cannot check the total of the run it is part of). Nothing else may leave code out."""

from pathlib import Path

import coverage
from coverage.config import DEFAULT_EXCLUDE

ROOT = Path(__file__).resolve().parents[1]


def test_coverage_below_100_percent_fails_the_run():
    config = coverage.Coverage(config_file=str(ROOT / "pyproject.toml")).config  # as the coverage run reads it
    assert config.fail_under == 100
    assert config.branch  # every branch of an if, not only every line: an untaken else is missed coverage
    # besides coverage's defaults, only the script entry point
    assert [e for e in config.exclude_list if e not in DEFAULT_EXCLUDE] == ["if __name__ == .__main__.:"]


def test_no_code_left_out_of_coverage_by_a_pragma():
    files = list((ROOT / "flkm").rglob("*.py"))
    assert len(files) >= 4
    hits = [str(f.relative_to(ROOT)) for f in files if "pragma: no cover" in f.read_text(encoding="utf-8")]
    assert hits == []
