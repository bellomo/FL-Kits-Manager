"""The team catalog of the installed game: the teams of the active Team.bin with their league, country and federation.
Read only.

- League: the team's domestic league in CompetitionEntry.bin, named as the game shows it: a game league by
  CompetitionRegulation.bin (ITALY_D1_LEAGUE -> Serie A TIM), a league Mod Studio adds by the name Mod Studio gave it
  in the kitserver map (the most common one among its teams); else a name made from the code (ITALY_D1_LEAGUE ->
  Italy D1). A team in no league keeps the league of its map line, if any.
- Country: from the code of a game league, or from the Mod Studio recipe for the leagues Mod Studio adds; a team in no
  league whose name is a country's (a national team) gets that country, and "National team" as its league.
- Federation: the confederation of the country in Country.bin.

Competitions are named the same way; the cups and supercups Mod Studio adds (FL_363_CUP) by the recipe of their league,
its other competitions (FL_UECL) by the name Mod Studio writes in their regulation records.
"""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from flkm.game import kitmap, kits, pesdb, recipe
from flkm.game.files import GameFiles

PESDB = "common/etc/pesdb/"
NATIONAL_TEAM = "National team"  # the league shown for a national team (in no league, named after its country)
TEAM_BIN = PESDB + "Team.bin"
_CODE_ALIASES = {"US": "USA", "KSA": "SAUDI ARABIA"}  # game league codes that are not the country's name
# national teams whose name is not the country's name in Country.bin
_NATIONAL_ALIASES = {"United States": "USA", "South Korea": "REPUBLIC OF KOREA", "North Korea": "KOREA DPR"}
_MOD_STUDIO_CUP = re.compile(r"^FL_(\d+)_([A-Z]+)$")  # a competition of a Mod Studio league: cup, play-off...
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

    def word(w: str) -> str:
        if w in _LOWER:
            return w.lower()
        if w in _UPPER:
            return w
        return "-".join("d'" + p[2:].capitalize() if p.startswith("D'") else p.capitalize() for p in w.split("-"))

    return " ".join(word(w) for w in name.split())


def _sorted(groups: dict) -> dict:
    """by name, None last"""
    return dict(sorted(groups.items(), key=lambda kv: (kv[0] is None, _fold(kv[0] or ""))))


@dataclass(frozen=True)
class Competition:
    id: int
    code: str  # the game's code name, e.g. ITALY_D1_CUP
    name: str  # as the game shows it (a league as the team list names it), else the code
    country: str | None
    federation: str | None


class Catalog:
    def __init__(
        self,
        game_files: GameFiles,
        kit_map: kitmap.KitMap,
        teams: list[Team],
        competitions: list[Competition] | None = None,
    ):
        self.files = game_files
        self.kit_map = kit_map
        self.teams = teams
        self.competitions = competitions or []
        self._by_id = {t.id: t for t in teams}
        self._comps = {c.id: c for c in self.competitions}

    def competition(self, comp_id: int) -> Competition | None:
        return self._comps.get(comp_id)

    def competitions_by_federation(self) -> dict[str | None, dict[str | None, list[Competition]]]:
        """federation -> country -> competitions sorted by name; names sorted with None last"""
        groups: dict = {}
        for c in sorted(self.competitions, key=lambda c: _fold(c.name)):
            groups.setdefault(c.federation, {}).setdefault(c.country, []).append(c)
        return _sorted({f: _sorted(cs) for f, cs in groups.items()})

    def search_competitions(self, text: str) -> list[Competition]:
        q = _fold(text.strip())
        if not q:
            return self.competitions
        return [c for c in self.competitions if q in _fold(c.name) or q in _fold(c.code) or q == str(c.id)]

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

    def by_federation(
        self, teams: list[Team] | None = None
    ) -> dict[str | None, dict[str | None, dict[str | None, list[Team]]]]:
        """federation -> country -> league -> teams (all, or the given ones, e.g. found by search); names sorted with
        None last, teams sorted by name"""
        groups: dict = {}
        for t in sorted(self.teams if teams is None else teams, key=lambda t: _fold(t.name)):
            groups.setdefault(t.federation, {}).setdefault(t.country, {}).setdefault(t.league, []).append(t)
        return _sorted({f: _sorted({c: _sorted(leagues) for c, leagues in cs.items()}) for f, cs in groups.items()})

    def search(self, text: str) -> list[Team]:
        q = _fold(text.strip())
        return [t for t in self.teams if q in _fold(t.name) or q == str(t.id)] if q else self.teams

    def kits(self, team_id: int) -> list[kits.Kit]:
        return kits.team_kits(team_id, self.kit_map, self.files)


def _table(gf: GameFiles, name: str, reader):
    found = gf.find(PESDB + name)
    return reader(found.read()) if found else []


def load(game_dir: Path) -> Catalog:
    gf = GameFiles(game_dir)
    km = kitmap.load(gf.sider_folder / "content" / "kits" / "map.txt")
    base = _table(gf, "Team.bin", pesdb.teams)
    all_comps = _table(gf, "Competition.bin", pesdb.competitions)
    comps = {c.id: c for c in all_comps if c.is_league}
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
    recipe_leagues = {lg.name: lg for lg in recipe.leagues(recipe.path(gf.sider.world))}
    recipe_countries = {name: lg.country for name, lg in recipe_leagues.items()}
    for c in recipe_countries.values():  # the game's spelling wins (the recipe writes Usa, Guinea-bissau)
        spelling.setdefault(_fold(c), c)

    records = _table(gf, "CompetitionRegulation.bin", pesdb.regulation_records)
    shown: dict[str, str] = {}
    for _, code, name in records:
        shown.setdefault(code, name)

    def game_name(code: str) -> str | None:
        """the name the game shows: the record of the code, else its first stage (ITALY_D1_LEAGUE_SPLIT_TOTAL...)"""
        return shown.get(code) or next((n for c, n in shown.items() if c.startswith(code + "_")), None)

    def comp_league(comp: pesdb.Competition) -> tuple[str, str | None]:
        """league name and country key of a domestic league"""
        if comp.country_code:
            key = _fold(_CODE_ALIASES.get(comp.country_code, comp.country_code))
            spelling.setdefault(key, pretty_country(comp.country_code))
            return game_name(comp.name) or f"{spelling[key]} D{comp.division}", key
        name = votes[comp.id].most_common(1)[0][0] if comp.id in votes else comp.name
        country = recipe_countries.get(name)
        return name, _fold(country) if country else None

    def code_country(code: str) -> str | None:
        """the country key at the start of a code (ITALY_D1_CUP -> italy, US_D1_CUP -> usa), if the game has it"""
        words = code.split("_")
        for n in range(len(words) - 1, 0, -1):
            key = _fold(_CODE_ALIASES.get(" ".join(words[:n]), " ".join(words[:n])))
            if key in spelling:
                return key
        return None

    by_code = {c.name: c for c in all_comps}

    def mod_studio_cup(code: str) -> tuple[str | None, str | None]:
        """name and country key of a competition Mod Studio adds to its league (FL_363_CUP, FL_363_LCUP, FL_363_RPO):
        the country of the league; the name of a cup or supercup from the recipe"""
        m = _MOD_STUDIO_CUP.match(code)
        league = by_code.get(f"FL_{m.group(1)}_LEAGUE") if m else None
        if league is None:
            return None, None
        league_name, key = comp_league(league)
        lg = recipe_leagues.get(league_name)
        names = {"CUP": lg.cup, "SUPER": lg.supercup} if lg else {}
        return names.get(m.group(2)), key

    named = []
    for comp in all_comps:
        if comp.is_league:
            name, key = comp_league(comp)
        else:
            cup, cup_key = mod_studio_cup(comp.name)
            name, key = game_name(comp.name) or cup or comp.name, code_country(comp.name) or cup_key
        named.append([comp, name, key])

    # Mod Studio writes the name of its other competitions (FL_UECL...) as the code of their regulation records, which
    # hold only the low byte of the competition id: a name goes to a competition when no other one left can have it
    codes = set(by_code)
    free = [(low, name) for low, code, name in records if not any(code == k or code.startswith(k + "_") for k in codes)]
    used = {name for comp, name, _ in named if name != comp.name}
    candidates = {
        comp.id: {n for low, n in free if low == comp.id & 0xFF} for comp, name, _ in named if name == comp.name
    }
    while True:
        for cands in candidates.values():
            cands -= {n for n in cands if n in used or any(n.startswith(u + " ") for u in used)}
        sure = {
            cid: next(iter(cands))
            for cid, cands in candidates.items()
            if len(cands) == 1 and sum(cands <= other for other in candidates.values()) == 1
        }
        if not sure:
            break
        for row in named:
            if row[0].id in sure:
                row[1] = sure[row[0].id]
                del candidates[row[0].id]
        used |= set(sure.values())

    competitions = []
    for comp, name, key in named:
        c = countries.get(key) if key else None
        competitions.append(
            Competition(comp.id, comp.name, name, spelling.get(key) if key else None, c.federation if c else None)
        )

    teams = []
    for t in base:
        if t.id in league_of:
            league, key = comp_league(league_of[t.id])
        else:
            league = map_league(t.id)
            country = recipe_countries.get(league) if league else None
            national = _fold(_NATIONAL_ALIASES.get(t.name, t.name))
            key = _fold(country) if country else (national if not league and national in countries else None)
            if key == national:
                league = NATIONAL_TEAM
        c = countries.get(key) if key else None
        teams.append(
            Team(t.id, t.name, t.abbr, league, spelling.get(key) if key else None, c.federation if c else None)
        )
    return Catalog(gf, km, teams, competitions)
