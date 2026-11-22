"""The game's database tables (common/etc/pesdb/*.bin). Read only.

A table is packed with a 16-byte header (00 01 01 "WESYS", u32 packed size, u32 size) followed by a zlib stream, and
holds fixed-size records:

- Team.bin, 1532 bytes: u32 id at 8, names in several languages in 70-byte slots (English at 368), abbreviation at 882.
- Competition.bin, 36 bytes: id low byte at 5 and high byte at 7, code name at 8 (ITALY_D1_LEAGUE, FL_363_LEAGUE...).
- CompetitionEntry.bin, 12 bytes: u32 team, an unknown u32, then a u32 holding the competition id (low byte in bits
  0-7, high byte in bits 24-31) and the team's position (bits 8-15).
- Country.bin, 1420 bytes: id in the low 10 bits of the u32 at 0, continent at 4, confederation at 5, upper case
  English name at 288.
- CompetitionRegulation.bin, 2352 bytes, one per competition stage: names as the game shows them in 115-byte language
  slots (9 from 20, English at 480; 11 more from 1087) and the competition's code name at 1055 (32 bytes:
  ITALY_D1_LEAGUE, or DENMARK_D1_LEAGUE_SPLIT_TOTAL for a league played in phases).
"""

import re
import struct
import zlib
from dataclasses import dataclass

TEAM_RECORD = 1532
COMPETITION_RECORD = 36
ENTRY_RECORD = 12
COUNTRY_RECORD = 1420
REGULATION_RECORD = 2352
FEDERATIONS = {2: "UEFA", 3: "AFC", 4: "CONMEBOL", 5: "CAF", 6: "CONCACAF", 7: "OFC"}
_MAGIC = b"\x00\x01\x01WESYS"
_LEAGUE = re.compile(r"^(?:FL_\d+|([A-Z]+)_D(\d+))_LEAGUE$")


class PesdbError(ValueError):
    pass


@dataclass(frozen=True)
class Team:
    id: int
    name: str
    abbr: str


@dataclass(frozen=True)
class Competition:
    id: int
    name: str

    @property
    def is_league(self) -> bool:
        """a domestic league (not a cup, a play-off or a continental competition)"""
        return bool(_LEAGUE.match(self.name))

    @property
    def country_code(self) -> str | None:
        """ITALY for ITALY_D1_LEAGUE; None for the leagues Mod Studio adds (FL_<n>_LEAGUE)"""
        m = _LEAGUE.match(self.name)
        return m.group(1) if m else None

    @property
    def division(self) -> int | None:
        """1 for ITALY_D1_LEAGUE; None for the leagues Mod Studio adds"""
        m = _LEAGUE.match(self.name)
        return int(m.group(2)) if m and m.group(2) else None


@dataclass(frozen=True)
class Entry:
    team_id: int
    competition_id: int
    position: int


@dataclass(frozen=True)
class Country:
    id: int
    name: str
    continent: int
    federation: str | None


def unpack(data: bytes) -> bytes:
    if data[:8] != _MAGIC:
        return data
    try:
        table = zlib.decompress(data[16:])
    except zlib.error as e:
        raise PesdbError(f"damaged WESYS table: {e}") from e
    return table


def _text(record: bytes, offset: int, length: int) -> str:
    return record[offset : offset + length].split(b"\0", 1)[0].decode("utf-8", "replace")


def _records(data: bytes, size: int, table: str):
    raw = unpack(data)
    if len(raw) % size:
        raise PesdbError(f"{table} of {len(raw)} bytes is not made of {size}-byte records")
    return (raw[start : start + size] for start in range(0, len(raw), size))


def teams(data: bytes) -> list[Team]:
    return [
        Team(struct.unpack_from("<I", r, 8)[0], _text(r, 368, 70), _text(r, 882, 10))
        for r in _records(data, TEAM_RECORD, "Team.bin")
    ]


def competitions(data: bytes) -> list[Competition]:
    return [
        Competition(r[5] | r[7] << 8, _text(r, 8, 28)) for r in _records(data, COMPETITION_RECORD, "Competition.bin")
    ]


def competition_entries(data: bytes) -> list[Entry]:
    out = []
    for r in _records(data, ENTRY_RECORD, "CompetitionEntry.bin"):
        team, _, packed = struct.unpack("<III", r)
        out.append(Entry(team, (packed & 0xFF) | (packed >> 24) << 8, (packed >> 8) & 0xFF))
    return out


def regulation_names(data: bytes) -> dict[str, str]:
    """code name -> name as the game shows it (English, else the first language that has one); the first record of a
    code wins (a competition has a record per stage)"""
    out: dict[str, str] = {}
    for r in _records(data, REGULATION_RECORD, "CompetitionRegulation.bin"):
        slots = [_text(r, 20 + 115 * k, 115) for k in range(9)] + [_text(r, 1087 + 115 * k, 115) for k in range(11)]
        name = slots[4] or next((s for s in slots if s), None)
        if name:
            out.setdefault(_text(r, 1055, 32), name)
    return out


def countries(data: bytes) -> list[Country]:
    return [
        Country(struct.unpack_from("<I", r, 0)[0] & 0x3FF, _text(r, 288, 70), r[4], FEDERATIONS.get(r[5]))
        for r in _records(data, COUNTRY_RECORD, "Country.bin")
    ]
