"""The staging area (<app data>/staging): kits chosen to replace the game's, kept until Deploy. Each change is a team,
a slot and a copy of the texture; a second change for the same slot replaces the first. Only readable FTEX textures
are taken."""

import pytest

from conftest import build_ftex, dxt5_block
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


def test_damaged_staging_file_reads_as_empty(home):
    (home / "staging").mkdir(parents=True)
    (home / "staging" / "staging.json").write_text("{oops", encoding="utf-8")
    assert Staging(home / "staging").changes == []
    (home / "staging" / "staging.json").write_text('{"changes": [{"team_id": 1}]}', encoding="utf-8")
    assert Staging(home / "staging").changes == []
