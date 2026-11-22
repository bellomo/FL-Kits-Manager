"""The kitserver map, SiderAddons/content/kits/map.txt: `id, "folder"  # comment` per line. Read only."""

import re
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

_ENTRY = re.compile(r'^\s*(\d+)\s*,\s*"([^"]*)"\s*(?:#\s*(.*))?$')
_MOD_STUDIO = re.compile(r"FL26 Mod Studio:\s*(.+)/\d+")


@dataclass
class Entry:
    team_id: int
    folder: str  # relative to the kits folder, Windows separators
    league: str | None = None  # from Mod Studio's comment


@dataclass
class KitMap:
    entries: dict[int, Entry] = field(default_factory=dict)
    duplicates: list[int] = field(default_factory=list)
    kits_folder: Path | None = None

    def path_of(self, team_id: int) -> Path | None:
        entry = self.entries.get(team_id)
        return self.kits_folder / Path(PureWindowsPath(entry.folder)) if entry else None


def parse(text: str, kits_folder: Path | None = None) -> KitMap:
    m = KitMap(kits_folder=kits_folder)
    for line in text.splitlines():
        hit = _ENTRY.match(line)
        if not hit:
            continue
        team_id, folder, comment = int(hit.group(1)), hit.group(2), hit.group(3) or ""
        league = _MOD_STUDIO.search(comment)
        if team_id in m.entries:
            m.duplicates.append(team_id)
        m.entries[team_id] = Entry(team_id, folder, league.group(1).strip() if league else None)
    return m


def load(path: Path) -> KitMap:
    text = path.read_text(encoding="utf-8-sig") if path.is_file() else ""
    return parse(text, kits_folder=path.parent)
