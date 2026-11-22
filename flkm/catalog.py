"""The team catalog of the installed game: the teams of the active Team.bin with their league, country and federation.
Read only.

- League: the team's domestic league in CompetitionEntry.bin, with the name Mod Studio gave it in the kitserver map
  (the most common one among its teams), else a name made from the game's code (ITALY_D1_LEAGUE -> Italy D1). A team
  in no league keeps the league of its map line, if any.
- Country: from the code of a game league, or from the Mod Studio recipe for the leagues Mod Studio adds; a team in no
  league whose name is a country's (a national team) gets that country.
- Federation: the confederation of the country in Country.bin.
"""

import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from flkm.game import kitmap, kits, pesdb, recipe
from flkm.game.files import GameFiles

PESDB = "common/etc/pesdb/"
TEAM_BIN = PESDB + "Team.bin"
_CODE_ALIASES = {"US": "USA", "KSA": "SAUDI ARABIA"}  # game league codes that are not the country's name
# national teams whose name is not the country's name in Country.bin
_NATIONAL_ALIASES = {"United States": "USA", "South Korea": "REPUBLIC OF KOREA", "North Korea": "KOREA DPR"}
_LOWER = {"AND", "OF", "THE"}
_UPPER = {"DPR", "DR", "USA", "UAE", "FYR"}


@dataclass(frozen=True)
class Team:
    id: int
    name: str
    abbr: str
    league: str | None
    country: str | None
    federation: str | None


def _fold(text: str) -> str:
    """lower case without accents, for searching and matching"""
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def pretty_country(name: str) -> str:
    """the game's upper case country name in title case: TURKS AND CAICOS IS. -> Turks and Caicos Is."""
    words = []
    for w in name.split():
        words.append(w.lower() if w in _LOWER else w if w in _UPPER else w.title())
    return " ".join(words)


def _sorted(groups: dict) -> dict:
    """by name, None last"""
    return dict(sorted(groups.items(), key=lambda kv: (kv[0] is None, _fold(kv[0] or ""))))


class Catalog:
    def __init__(self, game_files: GameFiles, kit_map: kitmap.KitMap, teams: list[Team]):
        self.files = game_files
        self.kit_map = kit_map
        self.teams = teams
        self._by_id = {t.id: t for t in teams}

    def get(self, team_id: int) -> Team | None:
        return self._by_id.get(team_id)

    def _by_name(self) -> list[Team]:
        return sorted(self.teams, key=lambda t: _fold(t.name))

    def by_league(self) -> dict[str | None, list[Team]]:
        """leagues by name, teams without a league last; teams sorted by name"""
        groups: dict[str | None, list[Team]] = {}
        for t in self._by_name():
            groups.setdefault(t.league, []).append(t)
        return _sorted(groups)

    def by_federation(self) -> dict[str | None, dict[str | None, dict[str | None, list[Team]]]]:
        """federation -> country -> league -> teams; names sorted with None last, teams sorted by name"""
        groups: dict = {}
        for t in self._by_name():
            groups.setdefault(t.federation, {}).setdefault(t.country, {}).setdefault(t.league, []).append(t)
        return _sorted({f: _sorted({c: _sorted(leagues) for c, leagues in cs.items()}) for f, cs in groups.items()})

    def search(self, text: str) -> list[Team]:
        q = _fold(text.strip())
        return [t for t in self.teams if q in _fold(t.name) or q == str(t.id)] if q else self.teams

    def kits(self, team_id: int) -> list[kits.Kit]:
        return kits.team_kits(team_id, self.kit_map, self.files)


def _table(gf: GameFiles, name: str, reader) -> list:
    found = gf.find(PESDB + name)
    return reader(found.read()) if found else []


def load(game_dir: Path) -> Catalog:
    gf = GameFiles(game_dir)
    km = kitmap.load(gf.sider_folder / "content" / "kits" / "map.txt")
    base = _table(gf, "Team.bin", pesdb.teams)
    comps = {c.id: c for c in _table(gf, "Competition.bin", pesdb.competitions) if c.is_league}
    league_of: dict[int, pesdb.Competition] = {}
    for e in _table(gf, "CompetitionEntry.bin", pesdb.competition_entries):
        if e.competition_id in comps:
            league_of.setdefault(e.team_id, comps[e.competition_id])

    def map_league(team_id: int) -> str | None:
        entry = km.entries.get(team_id)
        return entry.league if entry else None

    votes: dict[int, Counter] = {}
    for team_id, comp in league_of.items():
        if name := map_league(team_id):
            votes.setdefault(comp.id, Counter())[name] += 1

    countries = {_fold(c.name): c for c in _table(gf, "Country.bin", pesdb.countries)}
    spelling = {key: pretty_country(c.name) for key, c in countries.items()}
    recipe_countries = recipe.league_countries(recipe.path(gf.sider.world))
    spelling.update({_fold(c): c for c in recipe_countries.values()})

    def comp_league(comp: pesdb.Competition) -> tuple[str, str | None]:
        """league name and country key of a domestic league"""
        if comp.country_code:
            key = _fold(_CODE_ALIASES.get(comp.country_code, comp.country_code))
            spelling.setdefault(key, pretty_country(comp.country_code))
            return f"{spelling[key]} D{comp.division}", key
        name = votes[comp.id].most_common(1)[0][0] if comp.id in votes else comp.name
        country = recipe_countries.get(name)
        return name, _fold(country) if country else None

    teams = []
    for t in base:
        if t.id in league_of:
            league, key = comp_league(league_of[t.id])
        else:
            league = map_league(t.id)
            country = recipe_countries.get(league) if league else None
            national = _fold(_NATIONAL_ALIASES.get(t.name, t.name))
            key = _fold(country) if country else (national if not league and national in countries else None)
        c = countries.get(key) if key else None
        teams.append(
            Team(t.id, t.name, t.abbr, league, spelling.get(key) if key else None, c.federation if c else None)
        )
    return Catalog(gf, km, teams)
