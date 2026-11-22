"""The kitserver map, SiderAddons/content/kits/map.txt: `id, "folder"  # comment` per line.

The kitserver (modules/common/kits.lua) reads only this file and, when a team has more lines, the last one wins. The
app keeps its own lines in a marked block at the end, so that they win without touching the other lines; a Mod Studio
Build that rewrites map.txt drops the block, which the app can then write again.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

APP_FOLDER = "FLKitsManager"  # the app's folder under content/kits
_ENTRY = re.compile(r'^\s*(\d+)\s*,\s*"([^"]*)"\s*(?:#\s*(.*))?$')
_MOD_STUDIO = re.compile(r"FL26 Mod Studio:\s*(.+)/\d+")
_BEGIN = "# >>> FL Kits Manager: the lines below are written by the app, do not edit them >>>"
_END = "# <<< FL Kits Manager <<<"
_APP_ENTRY = re.compile(rf'^\s*(\d+)\s*,\s*"{APP_FOLDER}\\([^"]*)"')


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
        league = league.group(1).strip() if league else None
        if team_id in m.entries:
            m.duplicates.append(team_id)
            league = league or m.entries[team_id].league  # e.g. the app's line after Mod Studio's
        m.entries[team_id] = Entry(team_id, folder, league)
    return m


def _newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _split(lines: list[str]) -> tuple[list[str], list[str] | None]:
    """the lines outside the app block, and the lines inside it (None without a block)"""
    if _BEGIN not in lines:
        return lines, None
    start = lines.index(_BEGIN)
    end = lines.index(_END, start) if _END in lines[start:] else len(lines)
    return lines[:start] + lines[end + 1 :], lines[start + 1 : end]


def with_app_block(text: str, entries: list[tuple[int, str]]) -> str:
    """map.txt with the app's block (team id, folder under the app's kits folder) at the end, where it wins over the
    other lines for the same team; no entries = no block"""
    outside, _ = _split(text.splitlines())
    if entries:
        outside = outside + [_BEGIN, *(f'{team_id}, "{APP_FOLDER}\\{folder}"' for team_id, folder in entries), _END]
    nl = _newline(text)
    return nl.join(outside) + nl if outside else ""


def app_block(text: str) -> list[tuple[int, str]] | None:
    """the entries of the app's block, None when map.txt has no block"""
    _, block = _split(text.splitlines())
    if block is None:
        return None
    return [(int(m.group(1)), m.group(2)) for m in map(_APP_ENTRY.match, block) if m]


def load(path: Path) -> KitMap:
    text = path.read_text(encoding="utf-8-sig") if path.is_file() else ""
    return parse(text, kits_folder=path.parent)
