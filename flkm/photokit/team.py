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
from flkm.photokit.photo import EXTENSIONS, kit_part

SLOTS = {"home": "p1", "away": "p2", "third": "p3", "gk": "g1"}
PARTS = ("shirt", "back", "shorts", "socks")
CELLS = [(kit, part) for kit in SLOTS for part in PARTS]  # the photos of a team, in reading order


def place_photos(paths: list, chosen: dict) -> tuple[dict, list]:
    """(chosen, left over): each photo goes to the (kit, part) its file name says (home_1.png, back_away.png, h1.jpg,
    ...; it replaces the photo there), the others to the first empty cells in CELLS order; left over: no cell free."""
    chosen = dict(chosen)
    unnamed = []
    for p in paths:
        kit, part = kit_part(Path(p).name)
        if kit:
            chosen[(kit, part)] = p
        else:
            unnamed.append(p)
    free = [cell for cell in CELLS if cell not in chosen]
    for cell, p in zip(free, unnamed):
        chosen[cell] = p
    return chosen, unnamed[len(free) :]


def photos_in_folder(folder) -> list[Path]:
    """The photos (PNG, JPEG, WebP) of a folder, sorted by name; not its subfolders."""
    return sorted((p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS), key=str)


def save_pasted(image: Image.Image, folder) -> Path:
    """Saves a pasted or dropped picture as <folder>\\pasted\\pasted_<n>.png (the next free n); returns the file."""
    target = Path(folder) / "pasted"
    target.mkdir(parents=True, exist_ok=True)
    n = 1
    while (target / f"pasted_{n}.png").exists():
        n += 1
    image.save(target / f"pasted_{n}.png")
    return target / f"pasted_{n}.png"


def chosen_to_photos(chosen: dict) -> dict[str, dict[str, list]]:
    """{(kit, part): photo} -> {kit: {part: [photo]}}, the form copy_photos takes."""
    photos: dict[str, dict[str, list]] = {}
    for (kit, part), p in chosen.items():
        photos.setdefault(kit, {})[part] = [p]
    return photos


@dataclass
class MadeTeam:
    folder: Path
    textures: dict[str, Path]  # slot -> texture PNG
    maker: str | None  # the cached maker used, or None
    new_maker: bool = False  # the maker was not in the cache: saved now
    missing: list[str] = field(default_factory=list)  # kits without a shirt photo
    notes: list[str] = field(default_factory=list)  # what was found or not, what to check


DEDUCED = {  # a part without its photo, and what it is made from (draft.py), in the order shown
    "back": "the back (the front mirrored, no back sponsor)",
    "shorts": "the shorts (the shirt colour)",
    "socks": "the socks (the shorts colour)",
}


def deduced_notes(team: dict) -> list[str]:
    """One note per kit with parts made without their photo (the "deduced" parts draft.py writes in team.json)."""
    notes = []
    for kit, spec in team["kits"].items():
        deduced = spec.get("_draft", {}).get("deduced", [])
        if deduced:
            notes.append(f"{kit}: no photo of " + ", ".join(DEDUCED[p] for p in DEDUCED if p in deduced))
    return notes


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
    # read first: the photos chosen may be the ones copied before (the dialog opens with them)
    files = {
        _photo_name(kit, part, n, Path(p).suffix.lower()): Path(p).read_bytes()
        for kit, parts in photos.items()
        for part, paths in parts.items()
        for n, p in enumerate(paths, 1)
    }
    shutil.rmtree(ref, ignore_errors=True)
    ref.mkdir(parents=True)
    for name, data in files.items():
        (ref / name).write_bytes(data)
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


def make_team(
    game: GameFiles,
    team_id: int,
    folder,
    makers_dir,
    maker: str | None = None,
    keep_logos: bool = False,
    crest: Image.Image | None = None,
    tones: dict | None = None,
):
    """The kit textures of a team from the photos in <folder>\\ref (see copy_photos), made in folder; maker: the name
    of the team's maker in the cache, when known; crest: a picture to use instead of the game's crest (a new crest
    waiting for Deploy); tones: kit -> which photo gives the colours of a kit with front and back photos in two tones
    ("front" or "back"; "auto" when not given, see pattern.read_kit_pattern). The logos cut before are cut again
    unless keep_logos (kept: logos joined by hand). Returns a MadeTeam; raises PhotoKitError without a crest (given
    or in the game) or a shirt photo."""
    folder = Path(folder)
    if crest is None:
        found = logos.find_crest(game, team_id)
        if not found:
            raise PhotoKitError(f"the game has no crest for team {team_id}")
        crest = logos.picture(found)
    crest.save(folder / "crest.png")
    if not keep_logos:
        shutil.rmtree(folder / "logos", ignore_errors=True)
    path, missing, notes = draft_team(str(folder), crest="crest.png", force=True, tones=tones)
    team = _read(path)
    notes += deduced_notes(team)
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


def made_before(folder) -> MadeTeam | None:
    """The kits made last in the work folder (their textures are still there), to see them again without making
    them; None when there are none."""
    folder = Path(folder)
    textures = {slot: folder / f"{kit}.png" for kit, slot in SLOTS.items() if (folder / f"{kit}.png").is_file()}
    return MadeTeam(folder, textures, None) if textures else None


def saved_tones(folder) -> dict[str, str]:
    """The tones chosen when the kits of the work folder were made last ("front" or "back" per kit; see make_team)."""
    path = Path(folder) / "team.json"
    if not path.is_file():
        return {}
    kits = _read(str(path))["kits"]
    return {k: v["_draft"]["tone"] for k, v in kits.items() if "tone" in v.get("_draft", {})}


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
