"""The game's database tables (common/etc/pesdb/*.bin). Read only.

A table is packed with a 16-byte header (00 01 01 "WESYS", u32 packed size, u32 size) followed by a zlib stream.
Team.bin holds one 1532-byte record per team: u32 id at 8, names in several languages in 70-byte slots (English at
368), abbreviation at 882.
"""

import struct
import zlib
from dataclasses import dataclass

TEAM_RECORD = 1532
_MAGIC = b"\x00\x01\x01WESYS"


class PesdbError(ValueError):
    pass


@dataclass(frozen=True)
class Team:
    id: int
    name: str
    abbr: str


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


def teams(data: bytes) -> list[Team]:
    table = unpack(data)
    if len(table) % TEAM_RECORD:
        raise PesdbError(f"Team.bin of {len(table)} bytes is not made of {TEAM_RECORD}-byte records")
    out = []
    for start in range(0, len(table), TEAM_RECORD):
        r = table[start : start + TEAM_RECORD]
        out.append(Team(struct.unpack_from("<I", r, 8)[0], _text(r, 368, 70), _text(r, 882, 10)))
    return out
