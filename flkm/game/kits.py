"""Which kits a team wears and where each texture comes from. Read only.

1. The team has a kitserver folder in map.txt (and the folder exists): its slots come from order.ini (players) and
   gk_order.ini (goalkeepers), else from its slot folders; each slot's texture is KitFile in its config.txt, else
   u<id><slot>.ftex.
2. Otherwise the game's own files: Asset/model/character/uniform/texture/#windx11/u<id><slot>.ftex (id with at least
   4 digits), found like any game file (livecpk roots, then CPKs).
"""

import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from flkm.game import ftex
from flkm.game.files import Found, GameFiles
from flkm.game.kitmap import KitMap

TEXTURES = "Asset/model/character/uniform/texture/#windx11/"
GAME_SLOTS = ("p1", "p2", "p3", "p4", "p5", "g1", "g2")
_SLOT = re.compile(r"^[pg]\d+$")
_NAMES = {"p1": "Home", "p2": "Away", "p3": "Third", "g1": "Goalkeeper"}


def slot_name(slot: str) -> str:
    """Home, Away, Third, Kit 4, ..., Goalkeeper, Goalkeeper 2, ..."""
    if slot in _NAMES:
        return _NAMES[slot]
    return f"{'Goalkeeper' if slot[0] == 'g' else 'Kit'} {slot[1:]}"


_KIT_FILE = re.compile(r"^\s*KitFile\s*=\s*(\S+)", re.MULTILINE)


@dataclass(frozen=True)
class Kit:
    team_id: int
    slot: str  # p1, p2, ... players; g1, ... goalkeepers
    source: str  # "kitserver: <folder>" or where the game file was found
    file: Path | None = None  # kitserver texture
    found: Found | None = None  # game texture

    def texture(self) -> ftex.Ftex:
        return ftex.parse(self.file.read_bytes() if self.file else self.found.read())

    def preview(self, mip: int = 0) -> Image.Image:
        return ftex.to_image(self.texture(), mip=mip, opaque=True)

    def picture(self, size: int) -> Image.Image:
        """the texture from its smallest mip at least `size` pixels wide (else the largest mip), opaque"""
        tex = self.texture()
        indexes = sorted(m.index for m in tex.mips)
        mip = next((i for i in reversed(indexes) if tex.width >> i >= size), indexes[0])
        return ftex.to_image(tex, mip=mip, opaque=True)


def _lines(path: Path) -> list[str]:
    return [s.strip() for s in path.read_text(encoding="utf-8-sig").splitlines() if s.strip()] if path.is_file() else []


def _slot_key(slot: str) -> tuple[int, int]:
    return (slot[0] == "g", int(slot[1:]))


def folder_kits(team_id: int, folder: Path, label: str) -> list[Kit]:
    slots = _lines(folder / "order.ini") + _lines(folder / "gk_order.ini")
    if not slots:
        slots = sorted((d.name for d in folder.iterdir() if d.is_dir() and _SLOT.match(d.name)), key=_slot_key)
    out = []
    for slot in slots:
        config = folder / slot / "config.txt"
        name = _KIT_FILE.search(config.read_text(encoding="utf-8-sig", errors="replace")) if config.is_file() else None
        texture = folder / slot / f"{name.group(1) if name else f'u{team_id}{slot}'}.ftex"
        if texture.is_file():
            out.append(Kit(team_id, slot, f"kitserver: {label}", file=texture))
    return out


def team_kits(team_id: int, kit_map: KitMap, game: GameFiles) -> list[Kit]:
    folder = kit_map.path_of(team_id)
    if folder is not None and folder.is_dir():
        return folder_kits(team_id, folder, kit_map.entries[team_id].folder)
    out = []
    for slot in GAME_SLOTS:
        found = game.find(f"{TEXTURES}u{team_id:04d}{slot}.ftex")
        if found:
            out.append(Kit(team_id, slot, found.source, found=found))
    return out
