"""The naming rule of CLAUDE.md: a test file names the module it tests (`test_<module>.py` for flkm/<module>.py,
`test_<package>_<module>.py` for flkm/<package>/<module>.py, `test_main.py` for flkm/__main__.py), or the repository
rule it checks (`test_rule_<rule>.py`)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "flkm"


def what_it_tests(name: str, pkg: Path = PKG) -> Path | str | None:
    """What a test file tests: the module's path, 'rule', or None for a name that follows no rule."""
    stem = name.removeprefix("test_").removesuffix(".py")
    if not name.startswith("test_") or not name.endswith(".py") or not stem:
        return None
    if stem.startswith("rule_"):
        return "rule" if stem != "rule_" else None
    if stem == "main":
        return pkg / "__main__.py"
    candidates = [pkg / f"{stem}.py"]
    if "_" in stem:
        package, module = stem.split("_", 1)
        candidates.append(pkg / package / f"{module}.py")
    for p in candidates:
        if p.is_file() and p.name != "__init__.py":
            return p
    return None


def test_every_test_file_names_its_module_or_rule():
    wrong = sorted(p.name for p in (ROOT / "tests").glob("test_*.py") if what_it_tests(p.name) is None)
    assert not wrong, f'test files named after no module and no rule (CLAUDE.md, "Test files"): {wrong}'


def test_a_name_that_follows_no_rule_would_be_caught(tmp_path):
    pkg = tmp_path / "flkm"
    (pkg / "game").mkdir(parents=True)
    for f in ("__init__.py", "__main__.py", "cli.py", "main_window.py", "game/__init__.py", "game/cpk.py"):
        (pkg / f).write_text("")
    assert what_it_tests("test_cli.py", pkg) == pkg / "cli.py"
    assert what_it_tests("test_main_window.py", pkg) == pkg / "main_window.py"
    assert what_it_tests("test_game_cpk.py", pkg) == pkg / "game" / "cpk.py"
    assert what_it_tests("test_main.py", pkg) == pkg / "__main__.py"
    assert what_it_tests("test_rule_lint.py", pkg) == "rule"
    for name in ("test_cli_ops.py", "test_rule_.py", "test___init__.py", "test_.py", "cli_test.py", "test_game.py"):
        assert what_it_tests(name, pkg) is None, name
