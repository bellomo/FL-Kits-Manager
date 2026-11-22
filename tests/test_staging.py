"""The staging area (<app data>/staging): kits chosen to replace the game's, kept until Deploy. Each change is a team,
a slot and a copy of the texture; a second change for the same slot replaces the first. Only readable FTEX textures
are taken."""

import pytest
from PIL import Image

from conftest import build_ftex, dxt5_block
from flkm.game import ftex
from flkm.game.ftex import FtexError
from flkm.staging import Staging


def texture(tmp_path, name="new.ftex", colour=0xF800):
    p = tmp_path / name
    p.write_bytes(build_ftex(4, 4, 4, [dxt5_block(colour)]))
    return p


def test_empty_staging(home):
    s = Staging(home / "staging")
    assert s.changes == [] and s.for_team(186) == {}


def test_a_change_is_kept_with_a_copy_of_the_texture(home, tmp_path):
    src = texture(tmp_path)
    s = Staging(home / "staging")
    c = s.add(186, "Bologna FC", "p1", src)
    assert (c.team_id, c.team_name, c.slot, c.source) == (186, "Bologna FC", "p1", str(src))
    src.unlink()  # the copy does not depend on the original
    again = Staging(home / "staging")  # read back from disk
    assert again.changes == [c]
    assert again.path(c).read_bytes()[:4] == b"FTEX"


def test_same_slot_again_replaces_the_change(home, tmp_path):
    s = Staging(home / "staging")
    s.add(186, "Bologna FC", "p1", texture(tmp_path, "a.ftex"))
    c = s.add(186, "Bologna FC", "p1", texture(tmp_path, "b.ftex", 0x001F))
    assert s.changes == [c] and c.source.endswith("b.ftex")
    assert s.path(c).read_bytes() == (tmp_path / "b.ftex").read_bytes()


def test_changes_of_a_team_by_slot(home, tmp_path):
    s = Staging(home / "staging")
    p1 = s.add(186, "Bologna FC", "p1", texture(tmp_path))
    g1 = s.add(186, "Bologna FC", "g1", texture(tmp_path))
    s.add(98, "Inter", "p1", texture(tmp_path))
    assert s.for_team(186) == {"p1": p1, "g1": g1}


def test_a_file_that_is_not_a_texture_is_refused(home, tmp_path):
    bad = tmp_path / "bad.ftex"
    bad.write_bytes(b"not a texture")
    s = Staging(home / "staging")
    with pytest.raises(FtexError):
        s.add(186, "Bologna FC", "p1", bad)
    assert s.changes == []


def test_a_png_is_staged_as_an_ftex_with_the_header_of_the_kit_it_replaces(home, tmp_path):
    src = tmp_path / "home.png"
    Image.new("RGBA", (256, 256), (0, 0, 255, 255)).save(src)
    header = bytearray(build_ftex(4, 4, 4, [dxt5_block(0)])[:0x40])
    header[0x30:0x34] = b"\xcd" * 4
    s = Staging(home / "staging")
    c = s.add(186, "Bologna FC", "p1", src, header=bytes(header))
    assert c.file == "u186p1.ftex" and c.source == str(src)
    data = s.path(c).read_bytes()
    assert ftex.parse(data).width == 256 and data[0x30:0x34] == b"\xcd" * 4


def test_remove_a_change(home, tmp_path):
    s = Staging(home / "staging")
    c = s.add(186, "Bologna FC", "p1", texture(tmp_path))
    s.remove(186, "p1")
    assert s.changes == [] and not s.path(c).exists()
    s.remove(186, "p1")  # nothing to remove


def test_clear(home, tmp_path):
    s = Staging(home / "staging")
    c = s.add(186, "Bologna FC", "p1", texture(tmp_path))
    s.add(98, "Inter", "p1", texture(tmp_path))
    s.clear()
    assert s.changes == [] and not s.path(c).exists() and Staging(home / "staging").changes == []


def kit_files(colour=0x001F):
    return {
        "config.txt": b"KitFile=u186p1\nShirtColor1=#ff0000\n",
        "u186p1.ftex": build_ftex(4, 4, 4, [dxt5_block(colour)]),
        "u186p1_back.ftex": build_ftex(4, 4, 4, [dxt5_block(0)]),
    }


def test_a_whole_kit_from_a_pack(home):
    s = Staging(home / "staging")
    c = s.add_kit(186, "Bologna FC", "p1", kit_files(), "u186p1.ftex", "Serie A Kitpack.zip: Serie A Enilive/Bologna")
    assert (c.kind, c.texture, c.source) == ("kit", "u186p1.ftex", "Serie A Kitpack.zip: Serie A Enilive/Bologna")
    folder = s.path(c)
    assert sorted(p.name for p in folder.iterdir()) == ["config.txt", "u186p1.ftex", "u186p1_back.ftex"]
    assert s.texture_path(c) == folder / "u186p1.ftex"
    assert Staging(home / "staging").changes == [c]


def test_a_texture_change_has_its_texture_as_file(home, tmp_path):
    s = Staging(home / "staging")
    c = s.add(186, "Bologna FC", "p1", texture(tmp_path))
    assert c.kind == "texture" and s.texture_path(c) == s.path(c)


def test_a_kit_and_a_texture_for_the_same_kit_replace_each_other(home, tmp_path):
    s = Staging(home / "staging")
    kit = s.add_kit(186, "Bologna FC", "p1", kit_files(), "u186p1.ftex", "pack")
    tex = s.add(186, "Bologna FC", "p1", texture(tmp_path))
    assert s.changes == [tex] and not s.path(kit).exists()
    kit = s.add_kit(186, "Bologna FC", "p1", kit_files(), "u186p1.ftex", "pack")
    assert s.changes == [kit] and not s.path(tex).exists()
    s.remove(186, "p1")
    assert s.changes == [] and not s.path(kit).exists()


def test_a_kit_whose_texture_is_not_readable_is_refused(home):
    s = Staging(home / "staging")
    files = kit_files()
    files["u186p1.ftex"] = b"oops"
    with pytest.raises(FtexError):
        s.add_kit(186, "Bologna FC", "p1", files, "u186p1.ftex", "pack")
    with pytest.raises(ValueError, match="no u186p9.ftex"):
        s.add_kit(186, "Bologna FC", "p1", kit_files(), "u186p9.ftex", "pack")
    assert s.changes == []


def test_kit_file_names_must_stay_in_the_kit_folder(home):
    s = Staging(home / "staging")
    for bad in ("../x.txt", "a/b.txt", "a\\b.txt", "", ".."):
        files = kit_files() | {bad: b"x"}
        with pytest.raises(ValueError, match="file name"):
            s.add_kit(186, "Bologna FC", "p1", files, "u186p1.ftex", "pack")
    assert s.changes == []


def test_old_staging_files_without_a_kind_are_texture_changes(home):
    (home / "staging").mkdir(parents=True)
    old = (
        '{"changes": [{"team_id": 186, "team_name": "Bologna FC", "slot": "p1", "file": "u186p1.ftex", "source": "x"}]}'
    )
    (home / "staging" / "staging.json").write_text(old, encoding="utf-8")
    [c] = Staging(home / "staging").changes
    assert (c.kind, c.texture) == ("texture", "")


def test_damaged_staging_file_reads_as_empty(home):
    (home / "staging").mkdir(parents=True)
    (home / "staging" / "staging.json").write_text("{oops", encoding="utf-8")
    assert Staging(home / "staging").changes == []
    (home / "staging" / "staging.json").write_text('{"changes": [{"team_id": 1}]}', encoding="utf-8")
    assert Staging(home / "staging").changes == []


# --- logos -----------------------------------------------------------------------------------------------------------

FLAG = "common/render/symbol/flag/"
EMB = "common/render/symbol/emblemLc/"


def test_a_crest_is_kept_with_its_files_apart_from_the_kits(home, tmp_path):
    s = Staging(home / "staging")
    kit = s.add(186, "Bologna FC", "p1", texture(tmp_path))
    c = s.add_logo(
        186, "Bologna FC", "crest", {FLAG + "e_000186_r.png": b"a", FLAG + "e_000186_r_l.png": b"b"}, "x.png"
    )
    assert (c.kind, c.slot, c.source) == ("logo", "crest", "x.png")
    assert s.for_team(186) == {"p1": kit}  # the team's kits only
    assert s.logo("crest", 186) == c and s.logo("crest", 98) is None
    assert Staging(home / "staging").logo_files(c) == {FLAG + "e_000186_r.png": b"a", FLAG + "e_000186_r_l.png": b"b"}


def test_a_new_logo_keeps_the_staged_files_it_does_not_replace(home):
    s = Staging(home / "staging")
    s.add_logo(17, "Serie A", "emblem", {EMB + "emb_0017_l.png": b"normal", EMB + "emb_0017_w_l.png": b"white"}, "a")
    c = s.add_logo(17, "Serie A", "emblem", {EMB + "emb_0017_w_l.png": b"new white"}, "b")
    assert s.changes == [c] and c.source == "b"
    assert s.logo_files(c) == {EMB + "emb_0017_l.png": b"normal", EMB + "emb_0017_w_l.png": b"new white"}
    s.remove(17, "emblem")
    assert s.changes == [] and not s.path(c).exists()


def test_logo_files_stay_in_the_game_folders_of_logos(home):
    s = Staging(home / "staging")
    for bad in ("../x.png", "common/render/symbol/../../x.png", "C:/x.png", "common/etc/x.png"):
        with pytest.raises(ValueError, match="Not a logo file"):
            s.add_logo(186, "Bologna FC", "crest", {bad: b"x"}, "x.png")
    assert s.changes == []
