"""The game's database tables (common/etc/pesdb/*.bin): WESYS-packed (zlib), Team.bin read into teams with their id,
English name and abbreviation."""

import struct

import pytest

from conftest import competition_record, country_record, entry_record, regulation_record, team_record, wesys
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


def test_competitions_from_competition_bin():
    data = wesys(competition_record(10, "ITALY_D1_LEAGUE") + competition_record(337, "FL_250_LEAGUE"))
    assert [(c.id, c.name) for c in pesdb.competitions(data)] == [(10, "ITALY_D1_LEAGUE"), (337, "FL_250_LEAGUE")]


def test_domestic_leagues_are_told_from_cups_and_continental_competitions():
    names = [
        "ITALY_D1_LEAGUE",
        "ENGLAND_D2_LEAGUE",
        "FL_363_LEAGUE",
        "UEFA_CHAMPIONS_LEAGUE",
        "ITALY_D1_CUP",
        "FL_369_SUPER",
        "FL_365_UPO",
        "EURO",
    ]
    assert [pesdb.Competition(1, n).is_league for n in names] == [True, True, True] + [False] * 5


def test_country_prefix_of_a_game_league():
    assert pesdb.Competition(10, "ITALY_D1_LEAGUE").country_code == "ITALY"
    assert pesdb.Competition(40, "US_D1_LEAGUE").country_code == "US"
    assert pesdb.Competition(251, "FL_363_LEAGUE").country_code is None  # Mod Studio league: country in its recipe


def test_division_of_a_game_league():
    assert pesdb.Competition(69, "ITALY_D2_LEAGUE").division == 2
    assert pesdb.Competition(1, "XX_D12_LEAGUE").division == 12
    assert pesdb.Competition(251, "FL_363_LEAGUE").division is None
    assert pesdb.Competition(16, "ITALY_D1_CUP").division is None


def test_competition_entries_from_competition_entry_bin():
    data = wesys(entry_record(186, 10, 3) + entry_record(73947, 337, 0) + entry_record(5, 0x1FB))
    assert [(e.team_id, e.competition_id, e.position) for e in pesdb.competition_entries(data)] == [
        (186, 10, 3),
        (73947, 337, 0),
        (5, 0x1FB, 0),
    ]


def test_real_competition_entry_layout():
    # Aalborg in FL_363_LEAGUE (251) and a Ukrainian Premier League team (337), bytes as found in the game
    e = pesdb.competition_entries(struct.pack("<III", 73947, 0, 0x1FB))[0]
    assert (e.competition_id, e.position) == (251, 1)
    e = pesdb.competition_entries(struct.pack("<III", 1, 0, 0x1000151))[0]
    assert (e.competition_id, e.position) == (337, 1)


def test_countries_from_country_bin():
    data = wesys(country_record(50, "ITALY", 2, 2) + country_record(162, "AUSTRALIA", 6, 3))
    assert [(c.id, c.name, c.continent, c.federation) for c in pesdb.countries(data)] == [
        (50, "ITALY", 2, "UEFA"),
        (162, "AUSTRALIA", 6, "AFC"),
    ]


def test_every_confederation_code():
    data = b"".join(country_record(i, f"C{i}", 1, code) for i, code in enumerate(range(8)))
    assert [c.federation for c in pesdb.countries(data)] == [
        None,
        None,
        "UEFA",
        "AFC",
        "CONMEBOL",
        "CAF",
        "CONCACAF",
        "OFC",
    ]


def test_league_names_as_the_game_shows_them():
    data = wesys(
        regulation_record("ITALY_D1_LEAGUE", "Serie A TIM", "Serie A TIM")
        + regulation_record("DENMARK_D1_LEAGUE_SPLIT_TOTAL", "3F Superliga")
        + regulation_record("DENMARK_D1_LEAGUE_0", "Regular Season")
        + regulation_record("ITALY_D1_LEAGUE", "Second stage")
    )
    names = pesdb.regulation_names(data)
    assert names == {
        "ITALY_D1_LEAGUE": "Serie A TIM",  # the first record of a code wins
        "DENMARK_D1_LEAGUE_SPLIT_TOTAL": "3F Superliga",
        "DENMARK_D1_LEAGUE_0": "Regular Season",
    }


def test_league_name_without_english_takes_another_language():
    names = pesdb.regulation_names(regulation_record("FL_1_LEAGUE", "", "Liga Uno"))
    assert names == {"FL_1_LEAGUE": "Liga Uno"}


def test_record_without_any_name_is_left_out():
    assert pesdb.regulation_names(regulation_record("FL_1_LEAGUE", "")) == {}


@pytest.mark.parametrize(
    ("reader", "record", "size"),
    [
        (pesdb.competitions, competition_record(1, "A"), 36),
        (pesdb.competition_entries, entry_record(1, 1), 12),
        (pesdb.countries, country_record(1, "A", 1, 2), 1420),
        (pesdb.regulation_names, regulation_record("A", "A"), 2352),
    ],
)
def test_tables_of_a_wrong_size_are_refused(reader, record, size):
    with pytest.raises(pesdb.PesdbError, match=str(size)):
        reader(wesys(record + b"\0"))


def test_regulation_records_with_the_low_byte_of_their_competition_id():
    data = regulation_record("ITALY_D1_LEAGUE", "Serie A TIM", low_id=10) + regulation_record(
        "UEFA Conference League", "UEFA Conference League", low_id=174
    )
    assert pesdb.regulation_records(data) == [
        (10, "ITALY_D1_LEAGUE", "Serie A TIM"),
        (174, "UEFA Conference League", "UEFA Conference League"),
    ]
