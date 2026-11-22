"""The Mod Studio recipe of the active world (%APPDATA%/FL26ModStudio/recipes/<world>.json). Read only.

The recipe is large (hundreds of MB, mostly players), so instead of parsing all of it the league objects are found by
their leading "name" and "country" members; the league's "cup_name" and "supercup_name" come after them, before the
next league.
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

_STR = r'"((?:[^"\\]|\\.)*)"'
_LEAGUE = re.compile(rf'"name":\s*{_STR}\s*,\s*"country":\s*{_STR}')
_CUP = re.compile(rf'"cup_name":\s*{_STR}')
_SUPERCUP = re.compile(rf'"supercup_name":\s*{_STR}')


@dataclass(frozen=True)
class League:
    name: str
    country: str
    cup: str | None  # the name of its cup, if Mod Studio adds one
    supercup: str | None


def path(world: str | None) -> Path | None:
    if not world:
        return None
    return Path(os.environ.get("APPDATA", "")) / "FL26ModStudio" / "recipes" / f"{world}.json"


def _text(s: str) -> str:
    return json.loads(f'"{s}"')


def leagues(recipe: Path | None) -> list[League]:
    """the leagues Mod Studio adds, as it wrote them"""
    if recipe is None or not recipe.is_file():
        return []
    text = recipe.read_text(encoding="utf-8", errors="replace")
    found = list(_LEAGUE.finditer(text))
    edits = text.find('"edits"', found[-1].end()) if found else -1
    out = []
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else (edits if edits >= 0 else len(text))
        cup, supercup = _CUP.search(text, m.end(), end), _SUPERCUP.search(text, m.end(), end)
        out.append(
            League(
                _text(m.group(1)),
                _text(m.group(2)),
                _text(cup.group(1)) if cup else None,
                _text(supercup.group(1)) if supercup else None,
            )
        )
    return out


def league_countries(recipe: Path | None) -> dict[str, str]:
    """league name -> country name, as Mod Studio wrote them"""
    return {lg.name: lg.country for lg in leagues(recipe)}
