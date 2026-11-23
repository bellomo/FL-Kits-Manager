"""Claude Code, the claude CLI the app uses for its Claude features (optional: without it everything else works).

Where it is looked for, in order: the file the user chose; `claude` on PATH; where the native installer puts it
(%USERPROFILE%\\.local\\bin); npm's global folder (%APPDATA%\\npm); inside the Claude desktop app
(%LOCALAPPDATA%\\Claude-Data\\<app>\\claude-code\\<version>\\<build>\\claude.exe, newest version first). A candidate
counts only when `claude --version` answers with a version.
"""

import os
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

TIMEOUT = 20  # seconds for `claude --version`
_VERSION = re.compile(r"\d+(?:\.\d+)+")


@dataclass(frozen=True)
class Cli:
    path: Path
    version: str
    source: str  # "chosen", "PATH", "installer", "npm" or "desktop app"


def version(path, run: Callable = subprocess.run) -> str | None:
    """the version `path --version` prints, None when it does not run or prints none"""
    try:
        done = run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    found = _VERSION.search(done.stdout or "") if done.returncode == 0 else None
    return found.group(0) if found else None


def _version_key(folder: Path) -> tuple:
    return tuple(int(n) for n in folder.name.split(".") if n.isdigit())


def _desktop(local: str) -> list[Path]:
    root = Path(local) / "Claude-Data"
    found = [p for p in root.glob("*/claude-code/*/*/claude.exe") if p.is_file()]
    return sorted(found, key=lambda p: _version_key(p.parent.parent), reverse=True)


def candidates(
    saved: str | None, env: Mapping[str, str] = os.environ, which: Callable = shutil.which
) -> list[tuple[Path, str]]:
    """the files that may be Claude Code, in the order they are tried, with where each was found"""
    out: list[tuple[Path, str]] = []
    if saved and Path(saved).is_file():
        out.append((Path(saved), "chosen"))
    on_path = which("claude")
    if on_path:
        out.append((Path(on_path), "PATH"))
    for var, rel, source in (
        ("USERPROFILE", ".local/bin/claude.exe", "installer"),
        ("APPDATA", "npm/claude.cmd", "npm"),
    ):
        if env.get(var) and (Path(env[var]) / rel).is_file():
            out.append((Path(env[var]) / rel, source))
    if env.get("LOCALAPPDATA"):
        out += [(p, "desktop app") for p in _desktop(env["LOCALAPPDATA"])]
    return out


def find(
    saved: str | None,
    run: Callable = subprocess.run,
    env: Mapping[str, str] = os.environ,
    which: Callable = shutil.which,
) -> Cli | None:
    """the first candidate that answers --version, None when there is none"""
    for path, source in candidates(saved, env, which):
        v = version(path, run)
        if v:
            return Cli(path, v, source)
    return None


def check(path, run: Callable = subprocess.run) -> Cli | None:
    """a file the user chose, if it is Claude Code"""
    v = version(path, run)
    return Cli(Path(path), v, "chosen") if v else None


def describe(cli: Cli | None) -> str:
    return f"Claude Code {cli.version}" if cli else "Claude Code not found"
