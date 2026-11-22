"""sider.ini: active livecpk roots (first wins), Lua modules and the Mod Studio world. Read only."""

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


def load(path: Path) -> SiderIni:
    return parse(path.read_text(encoding="utf-8-sig"), folder=path.parent)
