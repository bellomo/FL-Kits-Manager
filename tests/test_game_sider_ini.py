"""sider.ini: the active livecpk roots in priority order (first wins), the Lua modules, and the Mod Studio world
(the root whose folder starts with "_")."""

from flkm.game import sider_ini

SAMPLE = """\
[sider]
\tlivecpk.enabled = 1
\texe.name = "\\FL_2027.exe"
cpk.root = ".\\livecpk\\_FL26Megapack"
cpk.root = ".\\livecpk\\My_competition_logos"
#cpk.root = ".\\livecpk\\_FL26MyWorld"
;cpk.root = ".\\livecpk\\Old"
\tcpk.root = ".\\livecpk\\Match Cursors"
cpk.root=".\\livecpk\\root"
lua.module = "fl26caps.lua"
;lua.module = "newblood.lua"
\tlua.module = "kserv.lua"
"""


def test_active_roots_in_order_without_commented_lines():
    ini = sider_ini.parse(SAMPLE)
    assert ini.cpk_roots == [
        ".\\livecpk\\_FL26Megapack",
        ".\\livecpk\\My_competition_logos",
        ".\\livecpk\\Match Cursors",
        ".\\livecpk\\root",
    ]


def test_active_lua_modules():
    assert sider_ini.parse(SAMPLE).lua_modules == ["fl26caps.lua", "kserv.lua"]


def test_world_is_the_first_root_starting_with_underscore():
    assert sider_ini.parse(SAMPLE).world == "_FL26Megapack"


def test_no_world_when_no_root_starts_with_underscore():
    ini = sider_ini.parse('cpk.root = ".\\livecpk\\root"\n')
    assert ini.world is None


def test_root_paths_resolved_against_the_sider_folder(game):
    sider = game / "SiderAddons"
    (sider / "sider.ini").write_text(SAMPLE, encoding="utf-8")
    ini = sider_ini.load(sider / "sider.ini")
    assert ini.root_paths()[0] == sider / "livecpk" / "_FL26Megapack"
    assert ini.root_paths()[2] == sider / "livecpk" / "Match Cursors"


def test_absolute_root_paths_kept(game, tmp_path):
    sider = game / "SiderAddons"
    other = tmp_path / "elsewhere"
    (sider / "sider.ini").write_text(f'cpk.root = "{other}"\n', encoding="utf-8")
    assert sider_ini.load(sider / "sider.ini").root_paths() == [other]


APP = ".\\livecpk\\FLKitsManager"


def test_app_root_goes_before_the_first_active_root_so_that_it_wins():
    text = sider_ini.with_root(SAMPLE, APP)
    assert sider_ini.parse(text).cpk_roots[0] == APP
    assert text.splitlines()[3] == 'cpk.root = ".\\livecpk\\FLKitsManager"'
    assert text.replace('cpk.root = ".\\livecpk\\FLKitsManager"\n', "") == SAMPLE  # nothing else changes
    assert sider_ini.parse(text).world == "_FL26Megapack"


def test_app_root_already_there_is_not_added_again():
    once = sider_ini.with_root(SAMPLE, APP)
    assert sider_ini.with_root(once, APP) == once


def test_app_root_without_other_roots_goes_at_the_end_with_the_same_line_ends():
    assert (
        sider_ini.with_root("[sider]\r\nx = 1", APP) == '[sider]\r\nx = 1\r\ncpk.root = ".\\livecpk\\FLKitsManager"\r\n'
    )


def test_app_root_is_removed():
    assert sider_ini.without_root(sider_ini.with_root(SAMPLE, APP), APP) == SAMPLE
    assert sider_ini.without_root(SAMPLE, APP) == SAMPLE


def test_reads_files_with_a_bom_and_crlf(game):
    p = game / "SiderAddons" / "sider.ini"
    p.write_bytes(b'\xef\xbb\xbfcpk.root = ".\\livecpk\\_W"\r\nlua.module = "a.lua"\r\n')
    ini = sider_ini.load(p)
    assert ini.cpk_roots == [".\\livecpk\\_W"] and ini.lua_modules == ["a.lua"]
