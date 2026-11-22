"""Which kits a team wears and where each texture comes from: the kitserver folder of map.txt when the team has one
(slots from order.ini and gk_order.ini, texture from each slot's config.txt), else the game's own files
(u<id>p1.ftex ... in the livecpk roots or the CPKs)."""

from conftest import build_ftex, dxt5_block
from flkm.game import files, kitmap, kits

TEX = "Asset/model/character/uniform/texture/#windx11/"
RED, BLUE = 0xF800, 0x001F


def ftex(colour=RED):
    return build_ftex(4, 4, 4, [dxt5_block(colour)])


def make_game(game, make_cpk, cpk_files=None, map_lines=""):
    sider = game / "SiderAddons"
    (sider / "sider.ini").write_text('cpk.root = ".\\livecpk\\_World"\n', encoding="utf-8")
    kits_dir = sider / "content" / "kits"
    kits_dir.mkdir(parents=True)
    (kits_dir / "map.txt").write_text(map_lines, encoding="utf-8")
    (game / "Data").mkdir()
    if cpk_files:
        (game / "Data" / "dt34_g4.cpk").write_bytes(make_cpk("dt.cpk", cpk_files).read_bytes())
    return files.GameFiles(game), kitmap.load(kits_dir / "map.txt"), kits_dir


def kit_folder(kits_dir, rel, team_id, slots, gk_slots=("g1",), kit_file=None):
    folder = kits_dir / rel
    folder.mkdir(parents=True)
    (folder / "order.ini").write_text("\n".join(slots) + "\n", encoding="utf-8")
    (folder / "gk_order.ini").write_text("\n".join(gk_slots) + "\n", encoding="utf-8")
    for slot in (*slots, *gk_slots):
        (folder / slot).mkdir()
        name = kit_file or f"u{team_id}{slot}"
        (folder / slot / "config.txt").write_text(f"; texture files\nKitFile={name}\nShirtColor1=#ff0000\n")
        (folder / slot / f"{name}.ftex").write_bytes(ftex())
    return folder


def test_team_with_a_kitserver_folder_uses_its_slots(game, make_cpk):
    gf, km, kits_dir = make_game(game, make_cpk, map_lines='73947, "_World\\1. division\\Aalborg"\n')
    kit_folder(kits_dir, "_World\\1. division\\Aalborg", 73947, ["p1", "p2", "p3"])
    found = kits.team_kits(73947, km, gf)
    assert [k.slot for k in found] == ["p1", "p2", "p3", "g1"]
    assert found[0].source == "kitserver: _World\\1. division\\Aalborg"
    assert found[0].texture().width == 4


def test_kit_file_name_comes_from_config_txt(game, make_cpk):
    gf, km, kits_dir = make_game(game, make_cpk, map_lines='10, "FotoKits\\Club"\n')
    kit_folder(kits_dir, "FotoKits\\Club", 10, ["p1"], gk_slots=(), kit_file="custom_name")
    found = kits.team_kits(10, km, gf)
    assert [k.slot for k in found] == ["p1"]
    assert found[0].file.name == "custom_name.ftex"


def test_slot_without_config_uses_the_standard_name(game, make_cpk):
    gf, km, kits_dir = make_game(game, make_cpk, map_lines='10, "FotoKits\\Club"\n')
    folder = kit_folder(kits_dir, "FotoKits\\Club", 10, ["p1"], gk_slots=())
    (folder / "p1" / "config.txt").unlink()
    assert kits.team_kits(10, km, gf)[0].file.name == "u10p1.ftex"


def test_slot_whose_texture_is_missing_is_left_out(game, make_cpk):
    gf, km, kits_dir = make_game(game, make_cpk, map_lines='10, "FotoKits\\Club"\n')
    folder = kit_folder(kits_dir, "FotoKits\\Club", 10, ["p1", "p2"], gk_slots=())
    (folder / "p2" / "u10p2.ftex").unlink()
    assert [k.slot for k in kits.team_kits(10, km, gf)] == ["p1"]


def test_folder_without_order_files_uses_its_slot_folders(game, make_cpk):
    gf, km, kits_dir = make_game(game, make_cpk, map_lines='10, "FotoKits\\Club"\n')
    folder = kit_folder(kits_dir, "FotoKits\\Club", 10, ["p2", "p1"])
    (folder / "order.ini").unlink()
    (folder / "gk_order.ini").unlink()
    (folder / "notes").mkdir()
    assert [k.slot for k in kits.team_kits(10, km, gf)] == ["p1", "p2", "g1"]


def test_map_entry_whose_folder_is_missing_falls_back_to_the_game(game, make_cpk):
    gf, km, _ = make_game(game, make_cpk, {TEX + "u0186p1.ftex": ftex()}, map_lines='186, "Gone\\Bologna"\n')
    found = kits.team_kits(186, km, gf)
    assert [(k.slot, k.source) for k in found] == [("p1", "Data\\dt34_g4.cpk")]


def test_team_without_kitserver_folder_uses_the_game_files(game, make_cpk):
    cpk_files = {TEX + f"u0186{s}.ftex": ftex() for s in ("p1", "p2", "p3", "g1")}
    cpk_files[TEX + "u0186p1_back.ftex"] = ftex()  # numbers, not a kit
    gf, km, _ = make_game(game, make_cpk, cpk_files)
    found = kits.team_kits(186, km, gf)
    assert [k.slot for k in found] == ["p1", "p2", "p3", "g1"]
    assert all(k.source == "Data\\dt34_g4.cpk" for k in found)
    assert found[3].texture().width == 4


def test_game_kit_in_a_livecpk_root_wins(game, make_cpk):
    gf, km, _ = make_game(game, make_cpk, {TEX + "u0186p1.ftex": ftex(RED)})
    loose = game / "SiderAddons" / "livecpk" / "_World" / "Asset/model/character/uniform/texture/#windx11"
    loose.mkdir(parents=True)
    (loose / "u0186p1.ftex").write_bytes(ftex(BLUE))
    found = kits.team_kits(186, km, gf)
    assert found[0].source == "livecpk\\_World"
    assert found[0].preview().getpixel((0, 0)) == (0, 0, 255, 255)


def test_team_ids_of_five_digits_keep_all_digits(game, make_cpk):
    gf, km, _ = make_game(game, make_cpk, {TEX + "u73947p1.ftex": ftex()})
    assert [k.slot for k in kits.team_kits(73947, km, gf)] == ["p1"]


def test_team_with_no_kits(game, make_cpk):
    gf, km, _ = make_game(game, make_cpk)
    assert kits.team_kits(999, km, gf) == []
