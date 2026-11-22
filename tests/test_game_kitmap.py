"""The kitserver map (SiderAddons/content/kits/map.txt): team id -> kit folder, plus the league that Mod Studio writes
in its comment. Commented lines are not active."""

from flkm.game import kitmap

SAMPLE = """\
# SP Football life
# teams map
73947, "_FL26Megapack\\1. division\\Aalborg Boldspilklub"   # FL26 Mod Studio: 1. division/1 made
71581,"_FL26Megapack\\Bangladesh Premier League\\Abahani Limited Dhaka"   # FL26 Mod Studio: Bangladesh Premier League/0
74428, "FotoKits\\Crotone"
#71602, "FotoKits\\Hannover 96"  # disabled 21/11

# end of map
"""


def test_active_entries_by_team_id():
    m = kitmap.parse(SAMPLE)
    assert set(m.entries) == {73947, 71581, 74428}
    assert m.entries[74428].folder == "FotoKits\\Crotone"


def test_league_from_the_mod_studio_comment():
    m = kitmap.parse(SAMPLE)
    assert m.entries[73947].league == "1. division"
    assert m.entries[71581].league == "Bangladesh Premier League"
    assert m.entries[74428].league is None


def test_a_later_line_for_the_same_team_wins_and_is_reported():
    m = kitmap.parse('10, "A"\n10, "B"\n')
    assert m.entries[10].folder == "B"
    assert m.duplicates == [10]


def test_lines_that_are_not_entries_are_ignored():
    m = kitmap.parse('x, "A"\n12 "B"\n\n13, "C"\n')
    assert list(m.entries) == [13]


def test_folder_path_under_the_kits_folder(game):
    kits = game / "SiderAddons" / "content" / "kits"
    kits.mkdir(parents=True)
    (kits / "map.txt").write_text(SAMPLE, encoding="utf-8")
    m = kitmap.load(kits / "map.txt")
    assert m.path_of(74428) == kits / "FotoKits" / "Crotone"
    assert m.path_of(1) is None


def test_missing_map_is_empty(game):
    m = kitmap.load(game / "nope" / "map.txt")
    assert m.entries == {}
