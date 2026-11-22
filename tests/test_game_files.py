"""Where the game takes a file from: the livecpk roots of sider.ini (in their order), then the update CPKs in
download/ (newest name first), then the CPKs in Data/ (same order). The first that has the file wins."""

from flkm.game import files

TEAM = "common/etc/pesdb/Team.bin"
KIT = "Asset/model/character/uniform/texture/#windx11/u0186p1.ftex"


def setup(game, make_cpk, roots=("_World", "Other")):
    sider = game / "SiderAddons"
    (sider / "sider.ini").write_text("".join(f'cpk.root = ".\\livecpk\\{r}"\n' for r in roots), encoding="utf-8")
    for d in ("download", "Data"):
        (game / d).mkdir()
    return sider


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_livecpk_root_wins_over_the_cpks(game, make_cpk):
    sider = setup(game, make_cpk)
    put(sider / "livecpk" / "_World" / TEAM, b"world")
    (game / "Data" / "dt.cpk").write_bytes(make_cpk("dt.cpk", {TEAM: b"base"}).read_bytes())
    found = files.GameFiles(game).find(TEAM)
    assert found.read() == b"world"
    assert found.source == "livecpk\\_World"


def test_earlier_root_wins(game, make_cpk):
    sider = setup(game, make_cpk)
    put(sider / "livecpk" / "_World" / KIT, b"first")
    put(sider / "livecpk" / "Other" / KIT, b"second")
    assert files.GameFiles(game).find(KIT).read() == b"first"


def test_download_cpk_wins_over_data_and_newest_name_first(game, make_cpk):
    setup(game, make_cpk)
    (game / "Data" / "dt34_g4.cpk").write_bytes(make_cpk("a.cpk", {KIT: b"base", TEAM: b"base"}).read_bytes())
    (game / "download" / "data_s2627.cpk").write_bytes(make_cpk("b.cpk", {KIT: b"update1"}).read_bytes())
    (game / "download" / "data_s26271.cpk").write_bytes(make_cpk("c.cpk", {KIT: b"update2"}).read_bytes())
    gf = files.GameFiles(game)
    assert gf.find(KIT).read() == b"update2" and gf.find(KIT).source == "download\\data_s26271.cpk"
    assert gf.find(TEAM).read() == b"base" and gf.find(TEAM).source == "Data\\dt34_g4.cpk"


def test_root_outside_the_sider_folder_is_named_by_its_full_path(game, tmp_path):
    other = tmp_path / "shared roots" / "Kits"
    put(other / KIT, b"shared")
    (game / "SiderAddons" / "sider.ini").write_text(f'cpk.root = "{other}"\n', encoding="utf-8")
    found = files.GameFiles(game).find(KIT)
    assert found.read() == b"shared" and found.source == str(other)


def test_missing_file_is_none(game, make_cpk):
    setup(game, make_cpk)
    assert files.GameFiles(game).find("nope.bin") is None


def test_unreadable_cpk_is_skipped_and_reported(game, make_cpk):
    setup(game, make_cpk)
    (game / "Data" / "broken.cpk").write_bytes(b"not a cpk")
    (game / "Data" / "dt.cpk").write_bytes(make_cpk("a.cpk", {KIT: b"base"}).read_bytes())
    gf = files.GameFiles(game)
    assert gf.find(KIT).read() == b"base"
    assert [p.name for p in gf.skipped] == ["broken.cpk"]


def test_game_without_sider_reads_the_cpks_only(tmp_path, make_cpk):
    g = tmp_path / "plain"
    (g / "Data").mkdir(parents=True)
    (g / "Data" / "dt.cpk").write_bytes(make_cpk("a.cpk", {KIT: b"base"}).read_bytes())
    assert files.GameFiles(g).find(KIT).read() == b"base"


def test_sider_settings_are_exposed(game, make_cpk):
    setup(game, make_cpk)
    gf = files.GameFiles(game)
    assert gf.sider.world == "_World"
    assert gf.sider_folder == game / "SiderAddons"
