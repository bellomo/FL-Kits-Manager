"""CRI CPK archives (the game's Data/*.cpk and download/*.cpk), read only: list the files and read one."""

import struct

import pytest

from conftest import utf_table
from flkm.game import cpk

FILES = {
    "Asset/model/character/uniform/texture/#windx11/u0186p1.ftex": b"FTEX-bologna-home",
    "Asset/model/character/uniform/texture/#windx11/u0186g1.ftex": b"FTEX-bologna-gk",
    "common/etc/pesdb/Team.bin": b"team-table",
}


def test_lists_every_file_with_its_path(make_cpk):
    archive = cpk.Cpk(make_cpk("dt34_g4.cpk", FILES))
    assert sorted(e.path for e in archive.entries) == sorted(FILES)


def test_reads_a_file_by_path(make_cpk):
    archive = cpk.Cpk(make_cpk("dt34_g4.cpk", FILES))
    assert archive.read("common/etc/pesdb/Team.bin") == b"team-table"
    assert archive.read("Asset/model/character/uniform/texture/#windx11/u0186g1.ftex") == b"FTEX-bologna-gk"


def test_unknown_path_is_none(make_cpk):
    archive = cpk.Cpk(make_cpk("a.cpk", FILES))
    assert archive.get("nope.bin") is None
    with pytest.raises(KeyError):
        archive.read("nope.bin")


def test_files_in_the_root_have_no_folder(make_cpk):
    archive = cpk.Cpk(make_cpk("a.cpk", {"readme.txt": b"x"}))
    assert [e.path for e in archive.entries] == ["readme.txt"]


def test_archive_without_toc_has_no_files(make_cpk):
    assert cpk.Cpk(make_cpk("empty.cpk", {}, toc=False)).entries == []


def test_not_a_cpk_is_refused(tmp_path):
    p = tmp_path / "x.cpk"
    p.write_bytes(b"NOPE" + b"\0" * 64)
    with pytest.raises(cpk.CpkError):
        cpk.Cpk(p)


def test_encrypted_table_is_refused(tmp_path):
    p = tmp_path / "x.cpk"
    p.write_bytes(b"CPK \xff\0\0\0" + (16).to_bytes(8, "little") + b"\x12\x34" * 8)
    with pytest.raises(cpk.CpkError, match="encrypted"):
        cpk.Cpk(p)


def test_compressed_file_is_refused(make_cpk):
    archive = cpk.Cpk(make_cpk("a.cpk", {"c.bin": b"CRILAYLA" + b"\0" * 8}))
    with pytest.raises(cpk.CpkError, match="CRILAYLA"):
        archive.read("c.bin")


def test_utf_table_reads_every_column_type_and_constants():
    cols = [("u8", 0), ("s8", 1), ("u16", 2), ("s16", 3), ("u32", 4), ("s32", 5), ("u64", 6), ("s64", 7)]
    cols += [("f", 8), ("name", 0xA), ("blob", 0xB), ("kind", 4)]
    rows = [
        {"u8": 255, "s8": -1, "u16": 65535, "s16": -2, "u32": 7, "s32": -3, "u64": 2**40, "s64": -4, "f": 0.5}
        | {"name": "Bologna", "blob": b"\x01\x02"},
        {"u8": 0, "s8": 1, "u16": 2, "s16": 3, "u32": 4, "s32": 5, "u64": 6, "s64": 7, "f": 1.0}
        | {"name": "Inter", "blob": b""},
    ]
    table = cpk.parse_utf(utf_table("T", cols, rows, constants={"kind": 9}))
    assert table[0] == rows[0] | {"kind": 9}
    assert table[1] == rows[1] | {"kind": 9}


def test_utf_table_with_an_unknown_column_type_is_refused():
    table = bytearray(utf_table("T", [("x", 4)], [{"x": 1}]))
    table[8 + 24] = 0x50 | 0x9  # the first column's type byte: 9 is no known type
    with pytest.raises(cpk.CpkError, match="type 9"):
        cpk.parse_utf(bytes(table))


def test_table_size_field_is_read_little_endian(make_cpk):
    data = make_cpk("a.cpk", FILES).read_bytes()
    assert data[:4] == b"CPK " and struct.unpack_from("<Q", data, 8)[0] > 0


def test_cpk_files_are_opened_read_only(make_cpk, monkeypatch):
    modes = []
    real_open = open
    monkeypatch.setattr("builtins.open", lambda f, mode="r", *a, **k: modes.append(mode) or real_open(f, mode, *a, **k))
    cpk.Cpk(make_cpk("a.cpk", FILES)).read("common/etc/pesdb/Team.bin")
    assert modes and set(modes) == {"rb"}
