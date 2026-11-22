"""The game's database tables (common/etc/pesdb/*.bin): WESYS-packed (zlib), Team.bin read into teams with their id,
English name and abbreviation."""

import pytest

from conftest import team_record, wesys
from flkm.game import pesdb


def test_unpack_wesys():
    assert pesdb.unpack(wesys(b"hello table")) == b"hello table"


def test_unpacked_table_is_returned_as_it_is():
    assert pesdb.unpack(b"plain bytes") == b"plain bytes"


def test_truncated_wesys_is_refused():
    with pytest.raises(pesdb.PesdbError):
        pesdb.unpack(wesys(b"hello table")[:20])


def test_teams_from_team_bin():
    data = wesys(team_record(186, "Bologna FC", "BOL") + team_record(73947, "Aalborg Boldspilklub", "AAL"))
    teams = pesdb.teams(data)
    assert [(t.id, t.name, t.abbr) for t in teams] == [
        (186, "Bologna FC", "BOL"),
        (73947, "Aalborg Boldspilklub", "AAL"),
    ]


def test_names_are_utf8():
    teams = pesdb.teams(wesys(team_record(73930, "Arsenal Česká Lípa", "ARS")))
    assert teams[0].name == "Arsenal Česká Lípa"


def test_team_bin_of_a_wrong_size_is_refused():
    with pytest.raises(pesdb.PesdbError, match="1532"):
        pesdb.teams(wesys(team_record(1, "A", "A") + b"\0" * 10))
