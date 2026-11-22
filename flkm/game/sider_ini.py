"""sider.ini: active livecpk roots (first wins), Lua modules and the Mod Studio world; adding or removing the app's
own root, leaving every other line as it is."""

import re
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

_SETTING = re.compile(r'^\s*(cpk\.root|lua\.module)\s*=\s*"([^"]*)"')


@dataclass
class SiderIni:
    cpk_roots: list[str] = field(default_factory=list)
    lua_modules: list[str] = field(default_factory=list)
    folder: Path | None = None  # the folder of sider.ini: relative roots start there

    @property
    def world(self) -> str | None:
        """The Mod Studio world: the first root whose folder name starts with "_" (e.g. _FL26Megapack)."""
        for root in self.cpk_roots:
            name = PureWindowsPath(root).name
            if name.startswith("_"):
                return name
        return None

    def root_paths(self) -> list[Path]:
        paths = []
        for root in self.cpk_roots:
            p = Path(PureWindowsPath(root))
            paths.append(p if p.is_absolute() else self.folder / p)
        return paths


def parse(text: str, folder: Path | None = None) -> SiderIni:
    ini = SiderIni(folder=folder)
    for line in text.splitlines():
        m = _SETTING.match(line)
        if m:
            key, value = m.groups()
            (ini.cpk_roots if key == "cpk.root" else ini.lua_modules).append(value)
    return ini


def _active_root(line: str) -> str | None:
    m = _SETTING.match(line)
    return m.group(2) if m and m.group(1) == "cpk.root" else None


def _newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def with_root(text: str, root: str) -> str:
    """sider.ini with `cpk.root = "<root>"` before the first active root, where it wins; the rest unchanged"""
    lines = text.splitlines()
    roots = [_active_root(line) for line in lines]
    if root in roots:
        return text
    first = next((i for i, r in enumerate(roots) if r is not None), len(lines))
    lines.insert(first, f'cpk.root = "{root}"')
    nl = _newline(text)
    return nl.join(lines) + nl


def without_root(text: str, root: str) -> str:
    lines = text.splitlines()
    kept = [line for line in lines if _active_root(line) != root]
    if len(kept) == len(lines):
        return text
    nl = _newline(text)
    return nl.join(kept) + nl


def load(path: Path) -> SiderIni:
    return parse(path.read_text(encoding="utf-8-sig"), folder=path.parent)
