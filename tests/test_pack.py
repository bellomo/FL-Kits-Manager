"""Kit packs as fans distribute them: a folder or a zip with kitserver team folders (one sub folder per kit with
config.txt and its textures), often with the map lines to copy (`186, "Serie A Enilive\\Bologna"`) in a .txt file.
The ids of a pack can be another patch's, so each team is matched by id and checked by name."""

import zipfile

import pytest

from conftest import build_ftex, dxt5_block
from flkm import pack
from flkm.catalog import Team

TEX = build_ftex(4, 4, 4, [dxt5_block(0x001F)])


def config(kit_file):
    return f"ShirtModel=144\nKitFile={kit_file}\nBackNumbersFile={kit_file}_back\nShirtColor1=#ffffff\n"


def team_folder(root, rel, team_id, slots=("p1", "p2", "g1"), order=True):
    folder = root / rel
    for slot in slots:
        (folder / slot).mkdir(parents=True)
        (folder / slot / "config.txt").write_text(config(f"u{team_id}{slot}"), encoding="utf-8")
        (folder / slot / f"u{team_id}{slot}.ftex").write_bytes(TEX)
        (folder / slot / f"u{team_id}{slot}_back.ftex").write_bytes(TEX)
    if order:
        (folder / "order.ini").write_text("\n".join(s for s in slots if s[0] == "p") + "\n", encoding="utf-8")
        (folder / "gk_order.ini").write_text("\n".join(s for s in slots if s[0] == "g") + "\n", encoding="utf-8")
    return folder


def serie_a(root):
    """a pack like the ones on the modding sites"""
    base = root / "Serie A Kitpack"
    team_folder(base, "Serie A Enilive/Bologna", 186)
    team_folder(base, "Serie A Enilive/Internazionale", 119, slots=("p1",), order=False)
    team_folder(base, "Serie A Enilive/Como", 4219, slots=("p1", "p2"))
    (base / "README map.txt").write_text(
        '# Serie A Enilive\n186, "Serie A Enilive\\Bologna"\n119, "Serie A Enilive\\Internazionale"\n'
        '4219, "Serie A Enilive\\Como"\n',
        encoding="utf-8",
    )
    return base


def zipped(folder, target):
    with zipfile.ZipFile(target, "w") as z:
        for p in sorted(folder.rglob("*")):
            z.write(p, p.relative_to(folder.parent).as_posix())
    return target


GAME = [
    Team(186, "Bologna FC", "BOL", "Serie A TIM", "Italy", "UEFA"),
    Team(119, "Inter Milan", "INT", "Serie A TIM", "Italy", "UEFA"),
    Team(4300, "Como 1907", "COM", "Serie A TIM", "Italy", "UEFA"),
    Team(4219, "Pisa SC", "PIS", "Serie A TIM", "Italy", "UEFA"),
    Team(500, "Real Madrid CF", "RMA", "LaLiga", "Spain", "UEFA"),
    Team(501, "Real Madrid Castilla", "RMC", None, "Spain", "UEFA"),
]


# --- reading a pack --------------------------------------------------------------------------------------------------


def test_team_folders_and_their_kits(tmp_path):
    p = pack.open_pack(serie_a(tmp_path))
    assert [(t.path, t.name, t.slots, t.map_id) for t in p.teams] == [
        ("Serie A Kitpack/Serie A Enilive/Bologna", "Bologna", ("p1", "p2", "g1"), 186),
        ("Serie A Kitpack/Serie A Enilive/Como", "Como", ("p1", "p2"), 4219),
        ("Serie A Kitpack/Serie A Enilive/Internazionale", "Internazionale", ("p1",), 119),
    ]


def test_files_of_a_kit(tmp_path):
    p = pack.open_pack(serie_a(tmp_path))
    files = p.kit_files(p.teams[0], "p2")
    assert sorted(files) == ["config.txt", "u186p2.ftex", "u186p2_back.ftex"]
    assert files["u186p2.ftex"] == TEX and b"KitFile=u186p2" in files["config.txt"]
    assert p.texture_name(p.teams[0], "p2") == "u186p2.ftex"


def test_a_zip_is_read_like_a_folder(tmp_path):
    z = zipped(serie_a(tmp_path / "src"), tmp_path / "pack.zip")
    p = pack.open_pack(z)
    assert [(t.name, t.slots, t.map_id) for t in p.teams] == [
        ("Bologna", ("p1", "p2", "g1"), 186),
        ("Como", ("p1", "p2"), 4219),
        ("Internazionale", ("p1",), 119),
    ]
    assert p.kit_files(p.teams[0], "g1")["u186g1.ftex"] == TEX


def test_a_pack_that_is_a_single_team_folder(tmp_path):
    folder = team_folder(tmp_path, "Zalgiris Vilnius", 199, slots=("p1",))
    p = pack.open_pack(folder)
    assert [(t.path, t.name, t.slots, t.map_id) for t in p.teams] == [
        ("Zalgiris Vilnius", "Zalgiris Vilnius", ("p1",), None)
    ]


def test_kits_without_a_texture_or_config_are_left_out(tmp_path):
    folder = team_folder(tmp_path, "Club", 7, slots=("p1", "p2", "p3"), order=False)
    (folder / "p2" / "u7p2.ftex").unlink()  # config names a texture that is missing
    (folder / "p3" / "config.txt").unlink()
    (folder / "notes").mkdir()
    (folder / "p9").mkdir()  # empty kit folder
    assert pack.open_pack(folder).teams[0].slots == ("p1",)


def test_texture_without_kit_file_line_is_the_one_named_like_the_kit(tmp_path):
    folder = team_folder(tmp_path, "Club", 7, slots=("p1", "p2"))
    (folder / "p1" / "config.txt").write_text("ShirtModel=144\n", encoding="utf-8")  # the kitserver's default name
    (folder / "p2" / "config.txt").write_text("ShirtModel=144\n", encoding="utf-8")
    (folder / "p2" / "u7p2.ftex").unlink()  # only u7p2_back.ftex left: no kit texture
    p = pack.open_pack(folder)
    assert p.teams[0].slots == ("p1",) and p.texture_name(p.teams[0], "p1") == "u7p1.ftex"


def test_map_lines_with_a_different_root_still_find_the_folder(tmp_path):
    base = team_folder(tmp_path / "pack", "kit-server/Other Europe/Zalgiris Vilnius", 199, slots=("p1",)).parents[2]
    (base / "map.txt").write_text('199, "Other Europe\\Zalgiris Vilnius"  # Zalgiris\n', encoding="utf-8")
    (base / "notes.txt").write_text("thanks to the kit makers\n", encoding="utf-8")
    assert [t.map_id for t in pack.open_pack(base).teams] == [199]


def test_a_zip_with_the_kits_at_its_root(tmp_path):
    z = tmp_path / "club.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("p1/config.txt", config("u7p1"))
        f.writestr("p1/u7p1.ftex", TEX)
    p = pack.open_pack(z)
    assert [(t.path, t.name, t.slots) for t in p.teams] == [("", "", ("p1",))]
    assert p.kit_files(p.teams[0], "p1") == {"config.txt": config("u7p1").encode(), "u7p1.ftex": TEX}


def test_not_a_pack(tmp_path):
    (tmp_path / "empty").mkdir()
    assert pack.open_pack(tmp_path / "empty").teams == []
    team_folder(tmp_path, "Club", 7, slots=("p1",))
    (tmp_path / "Club" / "p1" / "u7p1.ftex").unlink()  # its only kit has no texture
    assert pack.open_pack(tmp_path / "Club").teams == []
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    with pytest.raises(pack.PackError, match="cannot be read"):
        pack.open_pack(bad)
    with pytest.raises(pack.PackError, match="not found"):
        pack.open_pack(tmp_path / "gone")


def test_a_password_protected_zip_says_so(tmp_path, monkeypatch):
    z = zipped(serie_a(tmp_path / "src"), tmp_path / "pack.zip")
    p = pack.open_pack(z)

    def locked(*a, **k):
        raise RuntimeError("File 'x' is encrypted, password required for extraction")

    monkeypatch.setattr(zipfile.ZipFile, "read", locked)
    with pytest.raises(pack.PackError, match="password"):
        p.kit_files(p.teams[0], "p1")


def test_names_in_a_zip_that_try_to_leave_the_pack_are_ignored(tmp_path):
    z = tmp_path / "evil.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("../escape/p1/config.txt", config("u1p1"))
        f.writestr("../escape/p1/u1p1.ftex", TEX)
        f.writestr("/abs/p1/config.txt", config("u1p1"))
        f.writestr("/abs/p1/u1p1.ftex", TEX)
    assert pack.open_pack(z).teams == []


# --- matching the pack's teams with the game's ------------------------------------------------------------------------


def test_same_name():
    assert pack.same_name("Bologna", "Bologna FC")
    assert pack.same_name("AC Milan", "Milan")
    assert pack.same_name("Atlético Madrid", "Atletico Madrid")
    assert pack.same_name("Brighton & Hove Albion", "Brighton and Hove Albion FC")
    assert not pack.same_name("Internazionale", "Inter Milan")
    assert not pack.same_name("Real Madrid", "Real Sociedad")
    assert not pack.same_name("FC", "AC")  # nothing left to compare


def test_matching_by_id_and_name(tmp_path):
    matches = {m.pack_team.name: m for m in pack.match(pack.open_pack(serie_a(tmp_path)).teams, GAME)}
    bologna = matches["Bologna"]
    assert (bologna.team.id, bologna.how, bologna.sure) == (186, "id and name", True)


def test_id_of_another_team_is_corrected_by_the_name(tmp_path):
    como = {m.pack_team.name: m for m in pack.match(pack.open_pack(serie_a(tmp_path)).teams, GAME)}["Como"]
    assert (como.team.id, como.how, como.sure) == (4300, "name", False)
    assert como.note == "the pack's id 4219 is Pisa SC in this game"


def test_id_whose_name_differs_is_kept_but_not_sure(tmp_path):
    inter = {m.pack_team.name: m for m in pack.match(pack.open_pack(serie_a(tmp_path)).teams, GAME)}["Internazionale"]
    assert (inter.team.id, inter.how, inter.sure) == (119, "id", False)
    assert inter.note == "named Inter Milan in this game"


def test_matching_by_name_only(tmp_path):
    folder = team_folder(tmp_path, "Bologna", 186, slots=("p1",))
    [m] = pack.match(pack.open_pack(folder).teams, GAME)
    assert (m.team.id, m.how, m.sure, m.note) == (186, "name", True, "")


def test_several_teams_with_the_name(tmp_path):
    [m] = pack.match(pack.open_pack(team_folder(tmp_path, "Real Madrid", 9, slots=("p1",))).teams, GAME)
    assert (m.team.id, m.how, m.sure) == (500, "name", False)
    assert m.note == "also Real Madrid Castilla"


def test_no_team_found(tmp_path):
    [m] = pack.match(pack.open_pack(team_folder(tmp_path, "Zalgiris Vilnius", 199, slots=("p1",))).teams, GAME)
    assert (m.team, m.how, m.sure, m.note) == (None, "none", False, "no team with this id or name")


def test_unknown_id_and_no_name(tmp_path):
    folder = team_folder(tmp_path, "Zalgiris Vilnius", 199, slots=("p1",))
    (folder / "map.txt").write_text('199, "Zalgiris Vilnius"\n', encoding="utf-8")
    [m] = pack.match(pack.open_pack(folder).teams, GAME)
    assert (m.team, m.how) == (None, "none")
