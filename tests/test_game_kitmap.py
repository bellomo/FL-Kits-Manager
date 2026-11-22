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


def test_a_later_line_without_league_keeps_the_league_of_mod_studio():
    m = kitmap.parse(SAMPLE + '73947, "FLKitsManager\\73947 Aalborg"\n')
    assert m.entries[73947].folder == "FLKitsManager\\73947 Aalborg"
    assert m.entries[73947].league == "1. division"


APP_BLOCK = (
    "# >>> FL Kits Manager: the lines below are written by the app, do not edit them >>>\n"
    '186, "FLKitsManager\\186 Bologna FC"\n'
    '73947, "FLKitsManager\\73947 Aalborg"\n'
    "# <<< FL Kits Manager <<<\n"
)


def test_app_block_goes_at_the_end_so_that_it_wins():
    text = kitmap.with_app_block(SAMPLE, [(186, "186 Bologna FC"), (73947, "73947 Aalborg")])
    assert text == SAMPLE + APP_BLOCK
    m = kitmap.parse(text)
    assert m.entries[73947].folder == "FLKitsManager\\73947 Aalborg"
    assert m.entries[71581].folder.startswith("_FL26Megapack")  # the other lines are untouched


def test_app_block_is_replaced_not_repeated():
    text = kitmap.with_app_block(SAMPLE + APP_BLOCK + "# a line added later\n", [(5, "5 Club")])
    assert text == SAMPLE + "# a line added later\n" + (
        "# >>> FL Kits Manager: the lines below are written by the app, do not edit them >>>\n"
        '5, "FLKitsManager\\5 Club"\n'
        "# <<< FL Kits Manager <<<\n"
    )


def test_no_entries_removes_the_block():
    assert kitmap.with_app_block(SAMPLE + APP_BLOCK, []) == SAMPLE
    assert kitmap.with_app_block(SAMPLE, []) == SAMPLE


def test_app_block_keeps_windows_line_ends_and_a_missing_last_line_end():
    crlf = SAMPLE.replace("\n", "\r\n")
    assert kitmap.with_app_block(crlf, [(5, "5 Club")]).endswith(
        '5, "FLKitsManager\\5 Club"\r\n# <<< FL Kits Manager <<<\r\n'
    )
    assert kitmap.with_app_block('1, "A"', [(5, "5 Club")]).startswith('1, "A"\n# >>> FL Kits Manager')


def test_block_without_its_end_line_runs_to_the_end_of_the_file():
    broken = SAMPLE + APP_BLOCK.replace("# <<< FL Kits Manager <<<\n", "")
    assert kitmap.app_block(broken) == [(186, "186 Bologna FC"), (73947, "73947 Aalborg")]
    assert kitmap.with_app_block(broken, []) == SAMPLE


def test_map_with_only_the_block_becomes_empty():
    assert kitmap.with_app_block(APP_BLOCK, []) == ""


def test_app_block_entries_are_read_back():
    assert kitmap.app_block(SAMPLE + APP_BLOCK) == [(186, "186 Bologna FC"), (73947, "73947 Aalborg")]
    assert kitmap.app_block(SAMPLE) is None  # no block (e.g. lost after a Mod Studio Build)
