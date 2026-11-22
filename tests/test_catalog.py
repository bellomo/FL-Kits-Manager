"""The team catalog of the installed game: every team of the active Team.bin with its id, name, abbreviation and the
league Mod Studio wrote in map.txt (None for the others until the competition tables are read), grouped by league."""

from conftest import team_record, wesys
from flkm import catalog
from flkm.game import files


def make_game(game, teams, map_lines=""):
    sider = game / "SiderAddons"
    (sider / "sider.ini").write_text('cpk.root = ".\\livecpk\\_World"\n', encoding="utf-8")
    pesdb = sider / "livecpk" / "_World" / "common" / "etc" / "pesdb"
    pesdb.mkdir(parents=True)
    (pesdb / "Team.bin").write_bytes(wesys(b"".join(team_record(*t) for t in teams)))
    kits_dir = sider / "content" / "kits"
    kits_dir.mkdir(parents=True)
    (kits_dir / "map.txt").write_text(map_lines, encoding="utf-8")
    return game


TEAMS = [(186, "Bologna FC", "BOL"), (73947, "Aalborg Boldspilklub", "AAL"), (73930, "Arsenal Česká Lípa", "ARS")]
MAP = (
    '73947, "_World\\1. division\\Aalborg"   # FL26 Mod Studio: 1. division/1 made\n'
    '73930, "_World\\3. liga\\Arsenal"   # FL26 Mod Studio: Czech 3. liga/4\n'
)


def test_every_team_of_team_bin_with_its_league(game):
    cat = catalog.load(make_game(game, TEAMS, MAP))
    assert [(t.id, t.name, t.abbr, t.league) for t in cat.teams] == [
        (186, "Bologna FC", "BOL", None),
        (73947, "Aalborg Boldspilklub", "AAL", "1. division"),
        (73930, "Arsenal Česká Lípa", "ARS", "Czech 3. liga"),
    ]


def test_teams_grouped_by_league_sorted_by_name(game):
    cat = catalog.load(
        make_game(game, TEAMS + [(73900, "Aarhus", "AGF")], MAP + '73900, "x"  # FL26 Mod Studio: 1. division/0\n')
    )
    groups = cat.by_league()
    assert list(groups) == ["1. division", "Czech 3. liga", None]
    assert [t.name for t in groups["1. division"]] == ["Aalborg Boldspilklub", "Aarhus"]


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
