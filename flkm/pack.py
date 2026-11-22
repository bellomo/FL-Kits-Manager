"""Kit packs as fans distribute them, read only: a folder or a zip with kitserver team folders.

A team folder has one sub folder per kit (p1, p2, ... players; g1, ... goalkeepers) with config.txt and its textures;
order.ini and gk_order.ini list the kits (else the kit folders are taken in order). The kit's texture is KitFile in
config.txt, else the file named u<id><slot>.ftex. The map lines to copy into map.txt (`186, "League\\Team"`), when the
pack has them in a .txt file, give the team's id in the patch the pack was made for: ids change between patches, so
match() checks each team by name too.
"""

import difflib
import re
import unicodedata
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from flkm.catalog import Team

_SLOT = re.compile(r"^[pg]\d+$")
_KIT_FILE = re.compile(r"^\s*KitFile\s*=\s*(\S+)", re.MULTILINE)
_MAP_LINE = re.compile(r'^\s*(\d+)\s*,\s*"([^"]+)"', re.MULTILINE)
# words that say what kind of club it is, not which one: left out when names are compared
_GENERIC = set(
    "fc ac afc cf sc ss ssc us as ac calcio club football futbol futebol fk sk bk cd ud sd rc rcd ca cs sv vfb vfl"
    " tsg bv sl sporting de del la el le the and".split()
)


class PackError(Exception):
    pass


@dataclass(frozen=True)
class PackTeam:
    path: str  # where the team folder is in the pack, folders separated by "/"
    name: str  # the folder's name
    slots: tuple[str, ...]  # its usable kits, in order
    map_id: int | None  # the team's id in the pack's map lines


def _slot_key(slot: str) -> tuple[bool, int]:
    return (slot[0] == "g", int(slot[1:]))


def _text(data: bytes) -> str:
    return data.decode("utf-8-sig", errors="replace")


def _join(*parts: str) -> str:
    """a path in the pack (the pack's root is the empty string)"""
    return "/".join(p for p in parts if p)


class Pack:
    def __init__(self, files: dict[str, Callable[[], bytes]]):
        """files: path in the pack ("a/b/c.txt") -> function reading its bytes"""
        self._files = files
        self._textures: dict[tuple[str, str], str] = {}
        self.teams = self._find_teams()

    @property
    def paths(self) -> list[str]:
        """every file in the pack"""
        return list(self._files)

    def read(self, path: str) -> bytes:
        try:
            return self._files[path]()
        except RuntimeError as e:  # zipfile: encrypted member
            raise PackError(f"The zip is password protected: extract it, then import the folder. ({e})") from e

    def _read(self, path: str) -> bytes:
        return self._files[path]()

    def _children(self, folder: str) -> tuple[set[str], set[str]]:
        """names of the files and of the folders directly in a folder of the pack"""
        files, folders = set(), set()
        prefix = folder + "/" if folder else ""
        for path in self._files:
            if path.startswith(prefix):
                head, _, rest = path[len(prefix) :].partition("/")
                (folders if rest else files).add(head)
        return files, folders

    def _texture(self, folder: str, slot: str) -> str | None:
        files, _ = self._children(_join(folder, slot))
        if "config.txt" not in files:
            return None
        named = _KIT_FILE.search(_text(self._read(_join(folder, slot, "config.txt"))))
        if named:
            name = named.group(1) + ".ftex"
            return name if name in files else None
        default = sorted(f for f in files if re.fullmatch(rf"u\d+{slot}\.ftex", f))
        return default[0] if default else None

    def _find_teams(self) -> list[PackTeam]:
        folders = sorted({str(PurePosixPath(p).parent.parent) for p in self._files if p.endswith("/config.txt")})
        map_ids = self._map_ids()
        teams = []
        for folder in folders:
            folder = "" if folder == "." else folder
            files, subfolders = self._children(folder)
            found = {s for s in subfolders if _SLOT.match(s) and self._texture(folder, s)}
            for s in found:
                self._textures[(folder, s)] = self._texture(folder, s)
            listed = [
                line.strip()
                for name in ("order.ini", "gk_order.ini")
                if name in files
                for line in _text(self._read(_join(folder, name))).splitlines()
                if line.strip()
            ]
            slots = tuple(s for s in listed if s in found) if listed else tuple(sorted(found, key=_slot_key))
            if slots:
                name = PurePosixPath(folder).name
                teams.append(PackTeam(folder, name, slots, map_ids.get(folder.casefold())))
        return teams

    def _map_ids(self) -> dict[str, int]:
        """team folder (lower case) -> id, from the map lines in the pack's .txt files"""
        lines = []
        for path in self._files:
            if path.lower().endswith(".txt") and not path.lower().endswith("/config.txt"):
                lines += _MAP_LINE.findall(_text(self._read(path)))
        folders = {str(PurePosixPath(p).parent.parent).casefold() for p in self._files if p.endswith("/config.txt")}
        out = {}
        for team_id, target in lines:
            target = target.replace("\\", "/").strip("/").casefold()
            for folder in folders:
                if folder == target or folder.endswith("/" + target):
                    out[folder] = int(team_id)
        return out

    def texture_name(self, team: PackTeam, slot: str) -> str:
        return self._textures[(team.path, slot)]

    def kit_files(self, team: PackTeam, slot: str) -> dict[str, bytes]:
        """the files of one kit: name -> bytes"""
        files, _ = self._children(_join(team.path, slot))
        return {name: self.read(_join(team.path, slot, name)) for name in sorted(files)}


def _safe(name: str) -> bool:
    parts = PurePosixPath(name).parts
    return bool(parts) and not name.startswith(("/", "\\")) and ".." not in parts and ":" not in parts[0]


def open_pack(source: Path) -> Pack:
    """a pack from a folder or a .zip file"""
    source = Path(source)
    if source.is_dir():
        base = source.parent
        return Pack({p.relative_to(base).as_posix(): p.read_bytes for p in sorted(source.rglob("*")) if p.is_file()})
    if not source.is_file():
        raise PackError(f"{source} not found.")
    try:
        archive = zipfile.ZipFile(source)
    except (zipfile.BadZipFile, OSError) as e:
        raise PackError(f"{source} cannot be read as a zip: {e}") from e
    names = [n for n in archive.namelist() if not n.endswith("/") and _safe(n)]
    return Pack({n: (lambda n=n: archive.read(n)) for n in names})


# --- matching ---------------------------------------------------------------------------------------------------------


def _words(name: str) -> list[str]:
    folded = "".join(c for c in unicodedata.normalize("NFKD", name.casefold()) if not unicodedata.combining(c))
    return [w for w in re.split(r"[^a-z0-9]+", folded.replace("&", " and ")) if w and w not in _GENERIC]


def same_name(a: str, b: str) -> bool:
    """whether two names are the same team's: the same words leaving out FC, Calcio, ... (one name may have more
    words, like a year), or nearly the same spelling"""
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return False
    if set(wa) <= set(wb) or set(wb) <= set(wa):
        return True
    return difflib.SequenceMatcher(None, " ".join(wa), " ".join(wb)).ratio() >= 0.9


@dataclass(frozen=True)
class Match:
    pack_team: PackTeam
    team: Team | None  # the game's team it goes to
    how: str  # "id and name", "name", "id", "none"
    sure: bool  # False: the user should check it
    note: str = ""


def match(pack_teams: list[PackTeam], game_teams: list[Team]) -> list[Match]:
    by_id = {t.id: t for t in game_teams}
    out = []
    for pt in pack_teams:
        id_team = by_id.get(pt.map_id) if pt.map_id is not None else None
        named = sorted(
            (t for t in game_teams if same_name(pt.name, t.name)),
            key=lambda t: (set(_words(t.name)) != set(_words(pt.name)), _words(t.name)),
        )
        if id_team is not None and id_team in named:
            out.append(Match(pt, id_team, "id and name", True))
        elif named:
            notes = [f"the pack's id {pt.map_id} is {id_team.name} in this game"] if id_team else []
            if len(named) > 1:
                notes.append("also " + ", ".join(t.name for t in named[1:]))
            out.append(Match(pt, named[0], "name", not notes, "; ".join(notes)))
        elif id_team is not None:
            out.append(Match(pt, id_team, "id", False, f"named {id_team.name} in this game"))
        else:
            out.append(Match(pt, None, "none", False, "no team with this id or name"))
    return out
