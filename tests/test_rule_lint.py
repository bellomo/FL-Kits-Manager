"""The code follows the lint rules of pyproject.toml ([tool.ruff]): pyflakes (unused imports and variables, undefined
names, ...), the pycodestyle errors E4, E7, E9 and lines of at most 120 characters, and ruff's format. Ruff's cache
goes to a temporary folder, never into the repository."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ruff(*args: str, cache: Path, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    command = [sys.executable, "-m", "ruff", "check", "--cache-dir", str(cache), "--output-format", "concise", *args]
    return subprocess.run(command, capture_output=True, text=True, cwd=cwd)


def test_the_code_passes_ruff(tmp_path):
    result = ruff(cache=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_code_is_formatted(tmp_path):
    command = [sys.executable, "-m", "ruff", "format", "--check", "--cache-dir", str(tmp_path)]
    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_rules_catch_long_lines_and_unused_imports(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text('import os\n\nx = "' + "a" * 120 + '"\n')
    result = ruff("--config", str(ROOT / "pyproject.toml"), str(sample), cache=tmp_path / "cache")
    assert "F401" in result.stdout and "E501" in result.stdout, result.stdout + result.stderr
