"""The team catalog of the installed game: the teams of the active Team.bin, with the league Mod Studio wrote in the
kitserver map. Read only."""

import unicodedata
from dataclasses import dataclass
from pathlib import Path

from flkm.game import kitmap, kits, pesdb
from flkm.game.files import GameFiles

TEAM_BIN = "common/etc/pesdb/Team.bin"


@dataclass(frozen=True)
class Team:
    id: int
    name: str
    abbr: str
    league: str | None  # None until the competition tables are read (teams Mod Studio did not add)


def _fold(text: str) -> str:
    """lower case without accents, for searching"""
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


class Catalog:
    def __init__(self, game_files: GameFiles, kit_map: kitmap.KitMap, teams: list[Team]):
        self.files = game_files
        self.kit_map = kit_map
        self.teams = teams
        self._by_id = {t.id: t for t in teams}

    def get(self, team_id: int) -> Team | None:
        return self._by_id.get(team_id)

    def by_league(self) -> dict[str | None, list[Team]]:
        """leagues by name, teams without a league last; teams sorted by name"""
        groups: dict[str | None, list[Team]] = {}
        for t in sorted(self.teams, key=lambda t: _fold(t.name)):
            groups.setdefault(t.league, []).append(t)
        return dict(sorted(groups.items(), key=lambda kv: (kv[0] is None, _fold(kv[0] or ""))))

    def search(self, text: str) -> list[Team]:
        q = _fold(text.strip())
        return [t for t in self.teams if q in _fold(t.name) or q == str(t.id)] if q else self.teams

    def kits(self, team_id: int) -> list[kits.Kit]:
        return kits.team_kits(team_id, self.kit_map, self.files)


def load(game_dir: Path) -> Catalog:
    gf = GameFiles(game_dir)
    km = kitmap.load(gf.sider_folder / "content" / "kits" / "map.txt")
    found = gf.find(TEAM_BIN)
    teams = []
    if found:
        for t in pesdb.teams(found.read()):
            entry = km.entries.get(t.id)
            teams.append(Team(t.id, t.name, t.abbr, entry.league if entry else None))
    return Catalog(gf, km, teams)
