"""The staging area: kits chosen to replace the game's, kept (with a copy of each file) until Deploy installs them.

<folder>/staging.json lists the changes. A change is one kit of one team, either
- "texture": a new texture only, <folder>/files/u<team><slot>.ftex (Replace…), or
- "kit": a whole kitserver kit from a pack, <folder>/files/u<team><slot>/ with config.txt and its textures.
- "logo": a team's crest (slot "crest") or a competition's logo (slot "emblem", team_id = the competition's id),
  <folder>/files/<slot>_<id>/<game path of each PNG>.
A new change for the same kit replaces the old one; a new logo keeps the staged files it does not replace.
"""

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from flkm.game import ftex, ftex_write

LOGO_FOLDER = "common/render/symbol/"  # crests and competition logos are below this game folder


@dataclass(frozen=True)
class Change:
    team_id: int
    team_name: str
    slot: str
    file: str  # name of the copy in <folder>/files (a file for a texture, a folder for a kit)
    source: str  # where it comes from: the file the user chose, or the pack and its team folder
    kind: str = "texture"  # "texture", "kit" or "logo"
    texture: str = ""  # kit: the name of the kit's texture in its folder


def _plain(name: str) -> bool:
    return bool(name) and name not in (".", "..") and not any(c in name for c in "/\\:")


class Staging:
    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.changes: list[Change] = self._load()

    def _load(self) -> list[Change]:
        try:
            data = json.loads((self.folder / "staging.json").read_text(encoding="utf-8"))
            return [Change(**c) for c in data["changes"]]
        except (OSError, ValueError, TypeError, KeyError):
            return []

    def _save(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        data = {"changes": [asdict(c) for c in self.changes]}
        (self.folder / "staging.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def path(self, change: Change) -> Path:
        return self.folder / "files" / change.file

    def texture_path(self, change: Change) -> Path:
        """the kit's texture: the file of a texture change, the texture in the folder of a kit change"""
        return self.path(change) / change.texture if change.kind == "kit" else self.path(change)

    def _drop(self, change: Change) -> None:
        target = self.path(change)
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)

    def _put(self, change: Change) -> Change:
        for old in [c for c in self.changes if (c.team_id, c.slot) == (change.team_id, change.slot)]:
            if old.file != change.file:
                self._drop(old)
            self.changes.remove(old)
        self.changes.append(change)
        self._save()
        return change

    def add(self, team_id: int, team_name: str, slot: str, src: Path, header: bytes | None = None) -> Change:
        """stages src (.ftex as it is, .png or .dds made into an FTEX with the header of the kit it replaces) as the
        texture of the team's slot; raises FtexError if src cannot be a kit texture"""
        data = ftex_write.kit_texture(Path(src), header)
        change = Change(team_id, team_name, slot, f"u{team_id}{slot}.ftex", str(src))
        self.path(change).parent.mkdir(parents=True, exist_ok=True)
        self.path(change).write_bytes(data)
        return self._put(change)

    def add_kit(
        self, team_id: int, team_name: str, slot: str, files: dict[str, bytes], texture: str, source: str
    ) -> Change:
        """stages a whole kit (file name -> bytes, texture = the kit's texture among them); raises ValueError for a
        file name with a folder in it or a missing texture, FtexError for a texture that cannot be read"""
        bad = [name for name in files if not _plain(name)]
        if bad:
            raise ValueError(f"Not a plain file name in the kit: {bad[0]!r}")
        if texture not in files:
            raise ValueError(f"The kit has no {texture}.")
        ftex.parse(files[texture])
        change = Change(team_id, team_name, slot, f"u{team_id}{slot}", source, kind="kit", texture=texture)
        self._drop(change)
        folder = self.path(change)
        folder.mkdir(parents=True)
        for name, data in files.items():
            (folder / name).write_bytes(data)
        return self._put(change)

    def add_logo(self, owner_id: int, name: str, slot: str, files: dict[str, bytes], source: str) -> Change:
        """stages logo files (game path -> PNG) of a team ("crest") or competition ("emblem"); files staged before
        for the same logo and not given again are kept. Raises ValueError for a path outside the logo folders."""
        for path in files:
            parts = path.split("/")
            if not path.startswith(LOGO_FOLDER) or not all(_plain(p) for p in parts):
                raise ValueError(f"Not a logo file: {path!r}")
        old = self.logo(slot, owner_id)
        merged = (self.logo_files(old) if old else {}) | files
        change = Change(owner_id, name, slot, f"{slot}_{owner_id}", source, kind="logo")
        self._drop(change)
        for path, data in merged.items():
            target = self.path(change) / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return self._put(change)

    def logo(self, slot: str, owner_id: int) -> Change | None:
        return next((c for c in self.changes if c.kind == "logo" and (c.slot, c.team_id) == (slot, owner_id)), None)

    def logo_files(self, change: Change) -> dict[str, bytes]:
        folder = self.path(change)
        return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}

    def for_team(self, team_id: int) -> dict[str, Change]:
        """the team's kits waiting for Deploy, by slot"""
        return {c.slot: c for c in self.changes if c.team_id == team_id and c.kind != "logo"}

    def remove(self, team_id: int, slot: str) -> None:
        for c in [c for c in self.changes if (c.team_id, c.slot) == (team_id, slot)]:
            self._drop(c)
            self.changes.remove(c)
        self._save()

    def keep_copy(self, folder: Path) -> None:
        """copies the staged changes (list and files) to folder, a staging area of its own"""
        copy = Staging(folder)
        shutil.copytree(self.folder / "files", copy.folder / "files")
        copy.changes = list(self.changes)
        copy._save()

    def take(self, folder: Path) -> list[Change]:
        """stages the changes of another staging area (keep_copy), replacing what is staged for the same kits"""
        other = Staging(folder)
        for change in other.changes:
            self._drop(change)
            src, dst = other.path(change), self.path(change)
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            self._put(change)
        return other.changes

    def clear(self) -> None:
        shutil.rmtree(self.folder / "files", ignore_errors=True)
        self.changes = []
        self._save()
