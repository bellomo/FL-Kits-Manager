"""Deploy installs the staged kits into the game; Undo puts back what the last deploy changed.

- A team with a kitserver folder: its folder is copied to content/kits/FLKitsManager/<id> <name> (once; later deploys
  change the copy) with the new texture, and the app's block at the end of map.txt points the team there.
- A team whose kits come from the game files: the texture goes to livecpk/FLKitsManager/... and that root is put first
  in sider.ini.
- Nothing is written while the game runs; map.txt and sider.ini get a .bak-<date> copy before their first change;
  every file the deploy writes is recorded (with a copy of what was there) so that Undo can put it back.
- A Mod Studio Build that rewrites map.txt drops the app's block: the status says so and relink writes it again.
"""

import datetime

import pytest

from conftest import build_ftex, dxt5_block
from flkm import deploy
from flkm.game import kitmap, sider_ini
from flkm.staging import Staging

TEX = "Asset/model/character/uniform/texture/#windx11/"
TODAY = datetime.date(2026, 11, 22)
INI = '[sider]\r\ncpk.root = ".\\livecpk\\_World"\r\nlua.module = "kits.lua"\r\n'
MAP = '# teams map\n73947, "_World\\1. division\\Aalborg"   # FL26 Mod Studio: 1. division/1\n'


def ftex(colour):
    return build_ftex(4, 4, 4, [dxt5_block(colour)])


OLD, NEW, NEWER = ftex(0xF800), ftex(0x001F), ftex(0x07E0)


def make_game(game):
    sider = game / "SiderAddons"
    (sider / "sider.ini").write_bytes(INI.encode())
    kits = sider / "content" / "kits"
    aalborg = kits / "_World" / "1. division" / "Aalborg"
    for slot in ("p1", "p2", "g1"):
        (aalborg / slot).mkdir(parents=True)
        (aalborg / slot / "config.txt").write_text(f"KitFile=u73947{slot}\nShirtColor1=#ff0000\n", encoding="utf-8")
        (aalborg / slot / f"u73947{slot}.ftex").write_bytes(OLD)
    (aalborg / "order.ini").write_text("p1\np2\n", encoding="utf-8")
    (aalborg / "gk_order.ini").write_text("g1\n", encoding="utf-8")
    (kits / "map.txt").write_bytes(b"\xef\xbb\xbf" + MAP.encode())
    textures = sider / "livecpk" / "_World" / TEX
    textures.mkdir(parents=True)
    (textures / "u0186p1.ftex").write_bytes(OLD)
    (textures / "u0186g1.ftex").write_bytes(OLD)
    return game


def stage(home, tmp_path, *changes):
    s = Staging(home / "staging")
    for team_id, name, slot, data in changes:
        src = tmp_path / f"in_{team_id}{slot}.ftex"
        src.write_bytes(data)
        s.add(team_id, name, slot, src)
    return s


def run(game, home, staging, running=False, **kw):
    return deploy.deploy(game, staging, home, game_running=lambda: running, today=TODAY, **kw)


def sider(game):
    return game / "SiderAddons"


def app_texture(game, name):
    return sider(game) / "livecpk" / "FLKitsManager" / TEX / name


def app_kit(game, *parts):
    return sider(game) / "content" / "kits" / "FLKitsManager" / "73947 Aalborg Boldspilklub" / "/".join(parts)


def test_kit_from_the_game_files_goes_to_the_app_root_first_in_sider_ini(game, home, tmp_path):
    make_game(game)
    s = stage(home, tmp_path, (186, "Bologna FC", "p1", NEW))
    result = run(game, home, s)
    assert app_texture(game, "u0186p1.ftex").read_bytes() == NEW
    ini = (sider(game) / "sider.ini").read_bytes().decode("utf-8")
    assert sider_ini.parse(ini).cpk_roots == [".\\livecpk\\FLKitsManager", ".\\livecpk\\_World"]
    assert "\r\n" in ini  # line ends kept
    assert (sider(game) / "sider.ini.bak-20261122").read_bytes() == INI.encode()
    assert s.changes == [] and Staging(home / "staging").changes == []
    assert result.changes == 1 and (home / "deploys" / result.id / "manifest.json").is_file()


def test_kit_from_a_kitserver_folder_is_copied_and_the_app_block_points_there(game, home, tmp_path):
    make_game(game)
    s = stage(home, tmp_path, (73947, "Aalborg Boldspilklub", "p2", NEW))
    run(game, home, s)
    assert app_kit(game, "p2", "u73947p2.ftex").read_bytes() == NEW
    assert app_kit(game, "p1", "u73947p1.ftex").read_bytes() == OLD  # the rest of the folder is copied
    assert app_kit(game, "order.ini").read_text(encoding="utf-8") == "p1\np2\n"
    original = sider(game) / "content" / "kits" / "_World" / "1. division" / "Aalborg" / "p2" / "u73947p2.ftex"
    assert original.read_bytes() == OLD  # Mod Studio's folder is not touched
    raw = (sider(game) / "content" / "kits" / "map.txt").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf" + MAP.encode())  # BOM and Mod Studio's lines kept
    text = raw.decode("utf-8-sig")
    assert kitmap.app_block(text) == [(73947, "73947 Aalborg Boldspilklub")]
    assert kitmap.parse(text).entries[73947].folder == "FLKitsManager\\73947 Aalborg Boldspilklub"
    assert (sider(game) / "content" / "kits" / "map.txt.bak-20261122").read_bytes().startswith(b"\xef\xbb\xbf# teams")
    assert not (sider(game) / "livecpk" / "FLKitsManager").exists()
    assert sider_ini.parse((sider(game) / "sider.ini").read_text(encoding="utf-8")).cpk_roots == [".\\livecpk\\_World"]


def test_a_later_deploy_changes_the_app_copy(game, home, tmp_path):
    make_game(game)
    run(game, home, stage(home, tmp_path, (73947, "Aalborg Boldspilklub", "p2", NEW)))
    stray = sider(game) / "content" / "kits" / "FLKitsManager"
    (stray / "notes.txt").write_text("not a team folder", encoding="utf-8")  # ignored, like folders without an id
    (stray / "old stuff").mkdir()
    run(game, home, stage(home, tmp_path, (73947, "Aalborg Boldspilklub", "p1", NEWER)))
    assert app_kit(game, "p1", "u73947p1.ftex").read_bytes() == NEWER
    assert kitmap.app_block((sider(game) / "content" / "kits" / "map.txt").read_text(encoding="utf-8-sig")) == [
        (73947, "73947 Aalborg Boldspilklub")
    ]
    assert app_kit(game, "p2", "u73947p2.ftex").read_bytes() == NEW  # the first change is kept


def test_nothing_is_written_while_the_game_runs(game, home, tmp_path):
    make_game(game)
    s = stage(home, tmp_path, (186, "Bologna FC", "p1", NEW))
    with pytest.raises(deploy.GameRunning):
        run(game, home, s, running=True)
    assert not (sider(game) / "livecpk" / "FLKitsManager").exists() and len(s.changes) == 1


def test_unknown_game_state_needs_the_users_word(game, home, tmp_path):
    make_game(game)
    s = stage(home, tmp_path, (186, "Bologna FC", "p1", NEW))
    with pytest.raises(deploy.GameStateUnknown):
        run(game, home, s, running=None)
    run(game, home, s, running=None, unknown_ok=True)
    assert app_texture(game, "u0186p1.ftex").read_bytes() == NEW


def test_slot_the_kitserver_folder_does_not_have_is_refused(game, home, tmp_path):
    make_game(game)
    s = stage(home, tmp_path, (73947, "Aalborg Boldspilklub", "p3", NEW))
    with pytest.raises(deploy.DeployError, match="Aalborg Boldspilklub: the new Third texture needs a kit"):
        run(game, home, s)
    assert not (sider(game) / "content" / "kits" / "FLKitsManager").exists()


def test_team_without_kits_gets_the_texture_in_the_app_root(game, home, tmp_path):
    make_game(game)
    run(game, home, stage(home, tmp_path, (5, "New Club", "p1", NEW)))
    assert app_texture(game, "u0005p1.ftex").read_bytes() == NEW


def test_folder_names_are_safe(game, home, tmp_path):
    make_game(game)
    s = stage(home, tmp_path, (73947, 'Aal/borg: "B"?', "p1", NEW))
    run(game, home, s)
    assert (sider(game) / "content" / "kits" / "FLKitsManager" / "73947 Aal_borg_ _B__").is_dir()


def test_nothing_staged_nothing_to_deploy(game, home):
    make_game(game)
    with pytest.raises(deploy.DeployError, match="Nothing to deploy"):
        run(game, home, Staging(home / "staging"))


def test_undo_puts_back_everything_the_last_deploy_changed(game, home, tmp_path):
    make_game(game)
    run(game, home, stage(home, tmp_path, (186, "Bologna FC", "p1", NEW), (73947, "Aalborg Boldspilklub", "p2", NEW)))
    deploy.undo(game, home, game_running=lambda: False)
    assert (sider(game) / "sider.ini").read_bytes() == INI.encode()
    assert (sider(game) / "content" / "kits" / "map.txt").read_bytes() == b"\xef\xbb\xbf" + MAP.encode()
    assert not (sider(game) / "livecpk" / "FLKitsManager").exists()
    assert not (sider(game) / "content" / "kits" / "FLKitsManager").exists()
    assert list((home / "deploys").iterdir()) == []


def test_undo_goes_back_one_deploy_at_a_time(game, home, tmp_path):
    make_game(game)
    run(game, home, stage(home, tmp_path, (73947, "Aalborg Boldspilklub", "p2", NEW)))
    run(game, home, stage(home, tmp_path, (73947, "Aalborg Boldspilklub", "p2", NEWER)))
    deploy.undo(game, home, game_running=lambda: False)
    assert app_kit(game, "p2", "u73947p2.ftex").read_bytes() == NEW
    assert deploy.history(home)[0].changes == 1


def test_undo_with_nothing_deployed(game, home):
    make_game(game)
    with pytest.raises(deploy.NothingToUndo):
        deploy.undo(game, home, game_running=lambda: False)


def test_undo_waits_for_the_game_to_be_closed(game, home, tmp_path):
    make_game(game)
    run(game, home, stage(home, tmp_path, (186, "Bologna FC", "p1", NEW)))
    with pytest.raises(deploy.GameRunning):
        deploy.undo(game, home, game_running=lambda: True)
    assert app_texture(game, "u0186p1.ftex").is_file()


def test_status_finds_the_block_lost_after_a_mod_studio_build_and_relink_writes_it_again(game, home, tmp_path):
    make_game(game)
    assert deploy.status(game).ok
    run(game, home, stage(home, tmp_path, (186, "Bologna FC", "p1", NEW), (73947, "Aalborg Boldspilklub", "p2", NEW)))
    assert deploy.status(game).ok
    (sider(game) / "content" / "kits" / "map.txt").write_bytes(MAP.encode())  # Mod Studio rewrote it
    (sider(game) / "sider.ini").write_bytes(INI.encode())
    st = deploy.status(game)
    assert (st.block_lost, st.root_lost, st.ok) == (True, True, False)
    deploy.relink(game, home, game_running=lambda: False, today=TODAY)
    assert deploy.status(game).ok
    deploy.undo(game, home, game_running=lambda: False)  # the relink can be undone too
    assert deploy.status(game).block_lost


# --- whole kits from packs -------------------------------------------------------------------------------------------


def pack_kit(kit_file, colour=NEW):
    return {
        "config.txt": f"KitFile={kit_file}\nShirtColor1=#00ff00\n".encode(),
        f"{kit_file}.ftex": colour,
        f"{kit_file}_name.ftex": OLD,
    }


def stage_kits(home, *kits):
    s = Staging(home / "staging")
    for team_id, name, slot, kit_file in kits:
        s.add_kit(team_id, name, slot, pack_kit(kit_file), f"{kit_file}.ftex", "pack.zip: Team")
    return s


def files_in(folder):
    return sorted(p.name for p in folder.iterdir())


def test_a_whole_kit_replaces_the_kit_folder_of_a_kitserver_team(game, home):
    make_game(game)
    run(game, home, stage_kits(home, (73947, "Aalborg Boldspilklub", "p2", "aab_away")))
    assert files_in(app_kit(game, "p2")) == ["aab_away.ftex", "aab_away_name.ftex", "config.txt"]
    assert app_kit(game, "p2", "aab_away.ftex").read_bytes() == NEW
    assert b"#00ff00" in app_kit(game, "p2", "config.txt").read_bytes()
    assert files_in(app_kit(game, "p1")) == ["config.txt", "u73947p1.ftex"]  # the other kits are kept
    text = (sider(game) / "content" / "kits" / "map.txt").read_text(encoding="utf-8-sig")
    assert kitmap.app_block(text) == [(73947, "73947 Aalborg Boldspilklub")]


def test_a_kit_the_team_did_not_have_is_added_to_its_list(game, home):
    make_game(game)
    run(game, home, stage_kits(home, (73947, "Aalborg Boldspilklub", "p3", "aab_third")))
    assert app_kit(game, "order.ini").read_text(encoding="utf-8") == "p1\np2\np3\n"
    assert app_kit(game, "gk_order.ini").read_text(encoding="utf-8") == "g1\n"
    run(game, home, stage_kits(home, (73947, "Aalborg Boldspilklub", "g2", "aab_gk2")))
    assert app_kit(game, "gk_order.ini").read_text(encoding="utf-8") == "g1\ng2\n"


def test_a_kitserver_folder_without_kit_lists_gets_none(game, home):
    make_game(game)
    aalborg = sider(game) / "content" / "kits" / "_World" / "1. division" / "Aalborg"
    (aalborg / "order.ini").unlink()
    (aalborg / "gk_order.ini").unlink()  # the kitserver takes the kit folders
    run(game, home, stage_kits(home, (73947, "Aalborg Boldspilklub", "p3", "aab_third")))
    assert files_in(app_kit(game)) == ["g1", "p1", "p2", "p3"]


def test_kits_for_a_team_without_a_kitserver_folder_make_one(game, home):
    make_game(game)
    run(game, home, stage_kits(home, (186, "Bologna FC", "g1", "bfc_gk"), (186, "Bologna FC", "p1", "bfc_home")))
    folder = sider(game) / "content" / "kits" / "FLKitsManager" / "186 Bologna FC"
    assert files_in(folder) == ["g1", "gk_order.ini", "order.ini", "p1"]
    assert (folder / "order.ini").read_text(encoding="utf-8") == "p1\n"
    assert (folder / "gk_order.ini").read_text(encoding="utf-8") == "g1\n"
    assert (folder / "p1" / "bfc_home.ftex").read_bytes() == NEW
    text = (sider(game) / "content" / "kits" / "map.txt").read_text(encoding="utf-8-sig")
    assert kitmap.app_block(text) == [(186, "186 Bologna FC")]
    assert not (sider(game) / "livecpk" / "FLKitsManager").exists()


def test_a_texture_goes_into_the_kit_folder_made_in_the_same_deploy(game, home, tmp_path):
    make_game(game)
    s = stage_kits(home, (186, "Bologna FC", "p1", "bfc_home"))
    src = tmp_path / "gk.ftex"
    src.write_bytes(NEWER)
    s.add(186, "Bologna FC", "g1", src)  # the team's game goalkeeper kit is not in the new folder
    with pytest.raises(deploy.DeployError, match="Bologna FC: the new Goalkeeper texture needs a kit"):
        run(game, home, s)
    assert not (sider(game) / "content" / "kits" / "FLKitsManager").exists()
    s.remove(186, "g1")
    s.add_kit(186, "Bologna FC", "g1", pack_kit("bfc_gk"), "bfc_gk.ftex", "pack.zip: Team")
    s.add(186, "Bologna FC", "p1", src)  # replaces the staged p1 kit with a texture: needs the kit folder's p1
    with pytest.raises(deploy.DeployError, match="Bologna FC: the new Home texture needs a kit"):
        run(game, home, s)


def test_undo_of_whole_kits_puts_everything_back(game, home):
    make_game(game)
    run(
        game,
        home,
        stage_kits(home, (73947, "Aalborg Boldspilklub", "p2", "aab_away"), (186, "Bologna FC", "p1", "bfc_home")),
    )
    run(game, home, stage_kits(home, (73947, "Aalborg Boldspilklub", "p2", "aab_away2")))
    deploy.undo(game, home, game_running=lambda: False)
    assert files_in(app_kit(game, "p2")) == ["aab_away.ftex", "aab_away_name.ftex", "config.txt"]
    deploy.undo(game, home, game_running=lambda: False)
    assert not (sider(game) / "content" / "kits" / "FLKitsManager").exists()
    assert (sider(game) / "content" / "kits" / "map.txt").read_bytes() == b"\xef\xbb\xbf" + MAP.encode()


def test_history_lists_deploys_newest_first(game, home, tmp_path):
    make_game(game)
    assert deploy.history(home) == []
    first = run(game, home, stage(home, tmp_path, (186, "Bologna FC", "p1", NEW)))
    second = run(game, home, stage(home, tmp_path, (186, "Bologna FC", "g1", NEW), (5, "New Club", "p1", NEW)))
    assert [(h.id, h.changes) for h in deploy.history(home)] == [(second.id, 2), (first.id, 1)]


# --- logos -----------------------------------------------------------------------------------------------------------

CREST = {f"common/render/symbol/flag/e_000186_r{s}.png": bytes([n]) * 10 for n, s in enumerate(("", "_l", "_ll"))}


def test_a_crest_goes_to_the_app_root_and_undo_removes_it(game, home):
    make_game(game)
    s = Staging(home / "staging")
    s.add_logo(186, "Bologna FC", "crest", CREST, "C:\\logos\\bologna.png")
    s.add(73947, "Aalborg Boldspilklub", "p2", _texture(home))  # a kit in the same deploy
    result = run(game, home, s)
    root = sider(game) / "livecpk" / "FLKitsManager"
    assert {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*.png")} == CREST
    assert sider_ini.parse((sider(game) / "sider.ini").read_text()).cpk_roots[0] == ".\\livecpk\\FLKitsManager"
    assert result.changes == 2 and app_kit(game, "p2", "u73947p2.ftex").read_bytes() == NEW
    deploy.undo(game, home, game_running=lambda: False)
    assert not root.exists()


def test_a_logo_is_installed_without_a_kit_slot_check(game, home):
    make_game(game)
    s = Staging(home / "staging")
    s.add_logo(73947, "Aalborg Boldspilklub", "crest", CREST, "x.png")  # a kitserver team: no kit needed
    run(game, home, s)
    assert (sider(game) / "livecpk" / "FLKitsManager" / "common/render/symbol/flag/e_000186_r.png").is_file()


def _texture(home):
    p = home / "in.ftex"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(NEW)
    return p
