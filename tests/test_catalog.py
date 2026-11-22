"""The team catalog of the installed game: every team of the active Team.bin with its id, name, abbreviation, league,
country and federation, grouped by federation, country and league.

The league is the team's domestic league in CompetitionEntry.bin, named as the game shows it: a game league by
CompetitionRegulation.bin (ITALY_D1_LEAGUE -> Serie A TIM), a league Mod Studio adds as Mod Studio named it in map.txt;
without a name, after the code (ITALY_D1_LEAGUE -> Italy D1). The country comes from the code name or, for the leagues
Mod Studio adds, from its recipe; national teams are matched to a country by name; the federation is the country's in
Country.bin."""

import json

from conftest import competition_record, country_record, entry_record, regulation_record, team_record, wesys
from flkm import catalog
from flkm.game import files


def make_game(game, teams, map_lines="", comps=(), entries=(), countries=(), recipe=None, regulations=()):
    sider = game / "SiderAddons"
    (sider / "sider.ini").write_text('cpk.root = ".\\livecpk\\_World"\n', encoding="utf-8")
    pesdb = sider / "livecpk" / "_World" / "common" / "etc" / "pesdb"
    pesdb.mkdir(parents=True)
    (pesdb / "Team.bin").write_bytes(wesys(b"".join(team_record(*t) for t in teams)))
    if comps:
        (pesdb / "Competition.bin").write_bytes(wesys(b"".join(competition_record(*c) for c in comps)))
        (pesdb / "CompetitionEntry.bin").write_bytes(wesys(b"".join(entry_record(*e) for e in entries)))
    if countries:
        (pesdb / "Country.bin").write_bytes(wesys(b"".join(country_record(*c) for c in countries)))
    if regulations:
        (pesdb / "CompetitionRegulation.bin").write_bytes(wesys(b"".join(regulation_record(*r) for r in regulations)))
    kits_dir = sider / "content" / "kits"
    kits_dir.mkdir(parents=True)
    (kits_dir / "map.txt").write_text(map_lines, encoding="utf-8")
    if recipe is not None:
        r = game.parent / "appdata" / "FL26ModStudio" / "recipes"  # APPDATA of the autouse home fixture
        r.mkdir(parents=True)
        (r / "_World.json").write_text(json.dumps({"leagues": recipe}), encoding="utf-8")
    return game


TEAMS = [(186, "Bologna FC", "BOL"), (73947, "Aalborg Boldspilklub", "AAL"), (73930, "Arsenal Česká Lípa", "ARS")]
MAP = (
    '73947, "_World\\1. division\\Aalborg"   # FL26 Mod Studio: 1. division/1 made\n'
    '73930, "_World\\3. liga\\Arsenal"   # FL26 Mod Studio: Czech 3. liga/4\n'
)
COUNTRIES = [
    (50, "ITALY", 2, 2),
    (23, "DENMARK", 2, 2),
    (30, "CZECH REPUBLIC", 2, 2),
    (90, "USA", 4, 6),
    (120, "SAUDI ARABIA", 1, 3),
    (130, "TURKS AND CAICOS IS.", 4, 6),
    (140, "COTE D'IVOIRE", 3, 5),
    (150, "REPUBLIC OF KOREA", 1, 3),
    (151, "KOREA DPR", 1, 3),
]
COMPS = [
    (10, "ITALY_D1_LEAGUE"),
    (16, "ITALY_D1_CUP"),
    (251, "FL_363_LEAGUE"),
    (300, "FL_400_LEAGUE"),
    (40, "US_D1_LEAGUE"),
    (139, "KSA_D1_LEAGUE"),
    (2, "UEFA_CHAMPIONS_LEAGUE"),
    (33, "EURO"),
]
RECIPE = [{"name": "1. division", "country": "Denmark"}, {"name": "Czech 3. liga", "country": "Czech Republic"}]


def full_game(game, teams=(), entries=(), recipe=RECIPE):
    return make_game(
        game,
        TEAMS + list(teams),
        MAP,
        COMPS,
        [(186, 16), (186, 10, 4), (186, 2), (73947, 251)] + list(entries),
        COUNTRIES,
        recipe,
    )


def row(t):
    return (t.id, t.league, t.country, t.federation)


def test_every_team_of_team_bin_with_the_league_of_map_txt(game):
    cat = catalog.load(make_game(game, TEAMS, MAP))
    assert [(t.id, t.name, t.abbr, t.league, t.country, t.federation) for t in cat.teams] == [
        (186, "Bologna FC", "BOL", None, None, None),
        (73947, "Aalborg Boldspilklub", "AAL", "1. division", None, None),
        (73930, "Arsenal Česká Lípa", "ARS", "Czech 3. liga", None, None),
    ]


def test_league_country_and_federation_of_every_team(game):
    cat = catalog.load(full_game(game))
    assert [row(t) for t in cat.teams] == [
        (186, "Italy D1", "Italy", "UEFA"),  # game league, named after its code
        (73947, "1. division", "Denmark", "UEFA"),  # Mod Studio league, country from the recipe
        (73930, "Czech 3. liga", "Czech Republic", "UEFA"),  # in map.txt only
    ]


def test_team_without_map_line_takes_the_name_its_league_has_in_map_txt(game):
    cat = catalog.load(full_game(game, [(73999, "Vejle BK", "VEJ")], [(73999, 251)]))
    assert row(cat.get(73999)) == (73999, "1. division", "Denmark", "UEFA")


def test_mod_studio_league_without_map_lines_keeps_its_code_name(game):
    cat = catalog.load(full_game(game, [(80000, "New Club", "NEW")], [(80000, 300)]))
    assert row(cat.get(80000)) == (80000, "FL_400_LEAGUE", None, None)


def test_game_league_codes_that_differ_from_the_country_name(game):
    cat = catalog.load(full_game(game, [(101, "Austin FC", "AUS"), (102, "Al Hilal", "HIL")], [(101, 40), (102, 139)]))
    assert row(cat.get(101)) == (101, "USA D1", "USA", "CONCACAF")
    assert row(cat.get(102)) == (102, "Saudi Arabia D1", "Saudi Arabia", "AFC")


REGULATIONS = [
    ("ITALY_D1_CUP_KNOCKOUT", "Coppa Italia"),
    ("ITALY_D1_LEAGUE", "Serie A TIM"),
    ("US_D1_LEAGUE_SPLIT_TOTAL", "Major League Soccer"),
    ("US_D1_LEAGUE_EAST", "MLS First Round"),
    ("FL_363_LEAGUE_X", "Not this one"),  # a Mod Studio league keeps its map.txt name
]


def test_game_leagues_are_named_as_the_game_shows_them(game):
    teams, entries = [(101, "Austin FC", "AUS"), (102, "Al Hilal", "HIL")], [(101, 40), (102, 139)]
    g = make_game(game, TEAMS + teams, MAP, COMPS, [(186, 10), (73947, 251)] + entries, COUNTRIES, RECIPE, REGULATIONS)
    cat = catalog.load(g)
    assert row(cat.get(186)) == (186, "Serie A TIM", "Italy", "UEFA")
    assert row(cat.get(101)) == (101, "Major League Soccer", "USA", "CONCACAF")  # league played in phases
    assert row(cat.get(102)) == (102, "Saudi Arabia D1", "Saudi Arabia", "AFC")  # no regulation: named after the code
    assert row(cat.get(73947)) == (73947, "1. division", "Denmark", "UEFA")


def test_national_teams_by_country_name(game):
    cat = catalog.load(full_game(game, [(12, "Italy", "ITA"), (99, "Atlantis", "ATL")], [(12, 33), (99, 33)]))
    assert row(cat.get(12)) == (12, None, "Italy", "UEFA")
    assert row(cat.get(99)) == (99, None, None, None)


def test_national_teams_named_unlike_their_country(game):
    teams = [(39, "United States", "USA"), (53, "South Korea", "KOR"), (1012, "North Korea", "PRK")]
    cat = catalog.load(full_game(game, teams))
    assert [row(cat.get(i)) for i in (39, 53, 1012)] == [
        (39, None, "USA", "CONCACAF"),
        (53, None, "Republic of Korea", "AFC"),
        (1012, None, "Korea DPR", "AFC"),
    ]


def test_without_the_recipe_mod_studio_leagues_have_no_country(game):
    cat = catalog.load(full_game(game, recipe=None))
    assert row(cat.get(73947)) == (73947, "1. division", None, None)
    assert row(cat.get(186)) == (186, "Italy D1", "Italy", "UEFA")


def test_country_names_read_well(game):
    teams = [(1, "Turks and Caicos Islands", "TCI"), (2, "Côte d'Ivoire", "CIV")]
    cat = catalog.load(full_game(game, teams, recipe=RECIPE + [{"name": "Ligue 1 CI", "country": "Côte d'Ivoire"}]))
    assert cat.get(2).country == "Cote d'Ivoire" and cat.get(2).federation == "CAF"  # accents do not matter
    assert cat.get(1).country is None  # the game abbreviates the name: no match
    assert catalog.pretty_country("TURKS AND CAICOS IS.") == "Turks and Caicos Is."
    assert catalog.pretty_country("GUINEA-BISSAU") == "Guinea-Bissau"
    assert catalog.pretty_country("TIMOR-LESTE") == "Timor-Leste"
    assert catalog.pretty_country("KOREA DPR") == "Korea DPR"
    assert catalog.pretty_country("COTE D'IVOIRE") == "Cote d'Ivoire"


def test_game_spelling_of_a_country_wins_over_the_recipe(game):
    recipe = RECIPE + [{"name": "FL_400_LEAGUE", "country": "Cote D'ivoire"}, {"name": "X", "country": "Usa"}]
    cat = catalog.load(
        full_game(game, [(5, "Abidjan FC", "ABI"), (6, "Austin FC", "AUS")], [(5, 300), (6, 40)], recipe)
    )
    assert row(cat.get(5)) == (5, "FL_400_LEAGUE", "Cote d'Ivoire", "CAF")
    assert row(cat.get(6)) == (6, "USA D1", "USA", "CONCACAF")


def test_recipe_spelling_of_a_country_the_game_does_not_have(game):
    recipe = RECIPE + [{"name": "FL_400_LEAGUE", "country": "Atlantis"}]
    cat = catalog.load(full_game(game, [(5, "Abidjan FC", "ABI")], [(5, 300)], recipe))
    assert row(cat.get(5)) == (5, "FL_400_LEAGUE", "Atlantis", None)


def test_teams_grouped_by_league_sorted_by_name(game):
    cat = catalog.load(
        make_game(game, TEAMS + [(73900, "Aarhus", "AGF")], MAP + '73900, "x"  # FL26 Mod Studio: 1. division/0\n')
    )
    groups = cat.by_league()
    assert list(groups) == ["1. division", "Czech 3. liga", None]
    assert [t.name for t in groups["1. division"]] == ["Aalborg Boldspilklub", "Aarhus"]


def test_teams_grouped_by_federation_country_and_league(game):
    teams = [(12, "Italy", "ITA"), (101, "Austin FC", "AUS"), (99, "Atlantis", "ATL"), (98, "Inter", "INT")]
    cat = catalog.load(full_game(game, teams, [(101, 40), (98, 10)]))
    groups = cat.by_federation()
    assert list(groups) == ["CONCACAF", "UEFA", None]
    assert list(groups["UEFA"]) == ["Czech Republic", "Denmark", "Italy"]
    assert list(groups["UEFA"]["Italy"]) == ["Italy D1", None]
    assert [t.name for t in groups["UEFA"]["Italy"]["Italy D1"]] == ["Bologna FC", "Inter"]
    assert groups[None] == {None: {None: [cat.get(99)]}}


def test_some_teams_grouped_by_federation(game):
    cat = catalog.load(full_game(game))
    assert cat.by_federation(cat.search("aalborg")) == {"UEFA": {"Denmark": {"1. division": [cat.get(73947)]}}}


def test_search_by_name_or_id(game):
    cat = catalog.load(make_game(game, TEAMS, MAP))
    assert [t.id for t in cat.search("bolog")] == [186]
    assert [t.id for t in cat.search("73947")] == [73947]
    assert [t.id for t in cat.search("ceska")] == [73930]  # accents do not matter
    assert cat.search("") == cat.teams


def test_team_by_id(game):
    cat = catalog.load(make_game(game, TEAMS, MAP))
    assert cat.get(186).name == "Bologna FC" and cat.get(1) is None


def test_kits_of_a_team(game):
    cat = catalog.load(make_game(game, TEAMS, MAP))
    assert cat.kits(186) == []  # no texture anywhere in this fake game


def test_game_without_team_bin_has_no_teams(game):
    (game / "SiderAddons" / "sider.ini").write_text("", encoding="utf-8")
    cat = catalog.load(game)
    assert cat.teams == [] and isinstance(cat.files, files.GameFiles)
