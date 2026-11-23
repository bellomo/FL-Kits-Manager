"""A team's kits from photos, end to end: the photos the user chose -> kit textures waiting for Deploy.

make_team works in a folder of its own (the photos in ref\\, the logos cut from them, team.json, the textures):
1. the crest is the game's own (the largest crest file of the team);
2. team.json is drafted from the photos (draft.py): colours, logos, pattern;
3. the maker's logo cut from a photo is looked up in the makers' cache (maker.py) and saved there if new, so shorts
   and socks get its mask, and kits whose photo hides it get it too;
4. one 2048x2048 texture per kit (build.py), for the game's slots p1 (home), p2 (away), p3 (third), g1 (goalkeeper).
stage_textures then stages them like Replace… does: they wait for Deploy.
"""

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from flkm.game import logos
from flkm.game.files import GameFiles
from flkm.photokit import PhotoKitError
from flkm.photokit.build import build_team
from flkm.photokit.draft import draft_team, write_team_json
from flkm.photokit.maker import find_maker, save_maker
from flkm.photokit.photo import EXTENSIONS

SLOTS = {"home": "p1", "away": "p2", "third": "p3", "gk": "g1"}
PARTS = ("shirt", "back", "shorts", "socks")


@dataclass
class MadeTeam:
    folder: Path
    textures: dict[str, Path]  # slot -> texture PNG
    maker: str | None  # the cached maker used, or None
    new_maker: bool = False  # the maker was not in the cache: saved now
    missing: list[str] = field(default_factory=list)  # kits without a shirt photo
    notes: list[str] = field(default_factory=list)  # what was found or not, what to check


def _photo_name(kit: str, part: str, n: int, ext: str) -> str:
    if part == "shirt":
        return f"{kit}_{n}{ext}"
    if part == "back":
        return f"back_{kit}_{n}{ext}"
    return f"{kit}_{part}_{n}{ext}"


def copy_photos(photos: dict[str, dict[str, list]], folder) -> Path:
    """Copies the chosen photos ({kit: {part: [paths]}}, kit in home/away/third/gk, part in shirt/back/shorts/socks)
    into <folder>\\ref with the names draft.py reads (home_1.png, back_home_1.png, home_shorts_1.png, ...), replacing
    the photos copied before; returns the ref folder. Raises PhotoKitError for an unknown kit or part, or a file that
    is not a photo."""
    ref = Path(folder) / "ref"
    for kit, parts in photos.items():
        for part, paths in parts.items():
            if kit not in SLOTS or part not in PARTS:
                raise PhotoKitError(f"not a kit photo: {kit} {part}")
            bad = [Path(p).name for p in paths if Path(p).suffix.lower() not in EXTENSIONS]
            if bad:
                raise PhotoKitError(f"not a photo (PNG, JPEG or WebP): {bad[0]}")
    shutil.rmtree(ref, ignore_errors=True)
    ref.mkdir(parents=True)
    for kit, parts in photos.items():
        for part, paths in parts.items():
            for n, p in enumerate(paths, 1):
                shutil.copyfile(p, ref / _photo_name(kit, part, n, Path(p).suffix.lower()))
    return ref


def _cached_maker(folder: Path, team: dict, makers_dir, name: str | None) -> tuple[str | None, bool]:
    """(the cached maker of the team, saved now?): the maker logo cut from the first kit that shows it, recognised
    in the cache or saved there (as `name` when given); without one on the photos, `name` if the cache has it."""
    shown = [k["maker_logo"]["file"] for k in team["kits"].values() if "maker_logo" in k]
    if not shown:
        return (name, False) if name and (Path(makers_dir) / f"{name}.png").is_file() else (None, False)
    logo = Image.open(folder / shown[0])
    if name:
        known = (Path(makers_dir) / f"{name}.png").is_file()
        return (name, False) if known else (save_maker(logo, makers_dir, name), True)
    found = find_maker(logo, makers_dir)
    return (found, False) if found else (save_maker(logo, makers_dir), True)


def make_team(game: GameFiles, team_id: int, folder, makers_dir, maker: str | None = None, keep_logos: bool = False):
    """The kit textures of a team from the photos in <folder>\\ref (see copy_photos), made in folder; maker: the name
    of the team's maker in the cache, when known. The logos cut before are cut again unless keep_logos (kept: logos
    joined by hand). Returns a MadeTeam; raises PhotoKitError without a crest in the game or a shirt photo."""
    folder = Path(folder)
    found = logos.find_crest(game, team_id)
    if not found:
        raise PhotoKitError(f"the game has no crest for team {team_id}")
    logos.picture(found).save(folder / "crest.png")
    if not keep_logos:
        shutil.rmtree(folder / "logos", ignore_errors=True)
    path, missing, notes = draft_team(str(folder), crest="crest.png", force=True)
    team = _read(path)
    name, new = _cached_maker(folder, team, makers_dir, maker)
    if name:
        team = {"crest": team["crest"], "maker": name, "kits": team["kits"]}
        write_team_json(path, team)
        notes.append(f"maker: {name} ({'new in the cache' if new else 'from the cache'})")
    for old in folder.glob("*.png"):  # textures of kits made before and not made now
        if old.stem in SLOTS:
            old.unlink()
    done = build_team(str(folder), str(makers_dir))
    return MadeTeam(folder, {SLOTS[k]: Path(p) for k, p in done.items()}, name, new, missing, notes)


def _read(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def stage_textures(staging, team_id: int, team_name: str, made: MadeTeam, current: dict) -> list:
    """Stages the textures of made as the team's kits (like Replace…): each takes the header of the kit it replaces
    (current: slot -> the team's Kit, when it has one). Returns the changes."""
    changes = []
    for slot, png in made.textures.items():
        kit = current.get(slot)
        header = kit.texture().data[:0x40] if kit else None
        changes.append(staging.add(team_id, team_name, slot, png, header))
    return changes
