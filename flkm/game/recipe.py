"""The Mod Studio recipe of the active world (%APPDATA%/FL26ModStudio/recipes/<world>.json). Read only.

The recipe is large (hundreds of MB, mostly players), so instead of parsing all of it the league objects are found by
their leading "name" and "country" members.
"""

import json
import os
import re
from pathlib import Path

_STR = r'"((?:[^"\\]|\\.)*)"'
_LEAGUE = re.compile(rf'"name":\s*{_STR}\s*,\s*"country":\s*{_STR}')


def path(world: str | None) -> Path | None:
    if not world:
        return None
    return Path(os.environ.get("APPDATA", "")) / "FL26ModStudio" / "recipes" / f"{world}.json"


def league_countries(recipe: Path | None) -> dict[str, str]:
    """league name -> country name, as Mod Studio wrote them"""
    if recipe is None or not recipe.is_file():
        return {}
    text = recipe.read_text(encoding="utf-8", errors="replace")
    return {json.loads(f'"{n}"'): json.loads(f'"{c}"') for n, c in _LEAGUE.findall(text)}
