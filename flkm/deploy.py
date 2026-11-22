"""Deploy: installs the staged kits into the game; Undo puts back what the last deploy changed.

Where a kit goes:
- the team has a kitserver folder: the folder is copied once to content/kits/FLKitsManager/<id> <name> (later
  deploys change the copy) and the new texture replaces the slot's; the app's block at the end of map.txt points the
  team to the copy (the kitserver takes the last line of a team);
- otherwise (kits from the game files): the texture goes to livecpk/FLKitsManager/<game path>, and that root is put
  first in sider.ini (the first root wins).
Crests and competition logos always go to livecpk/FLKitsManager/<game path>.

Nothing is written while the game runs. map.txt and sider.ini get a <file>.bak-<date> copy before their first change
of the day. Each deploy is recorded in <app data>/deploys/<id>: manifest.json lists every file it wrote and whether
it existed, before/ keeps a copy of the ones that did; Undo uses them, newest deploy first.
"""

import datetime
import json
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from flkm.game import kitmap, kits, process, sider_ini
from flkm.staging import Staging

APP_ROOT = ".\\livecpk\\" + kitmap.APP_FOLDER  # the app's root as sider.ini names it
_UNSAFE = re.compile(r'[<>:"/\\|?*]')
_BOM = b"\xef\xbb\xbf"


class DeployError(Exception):
    pass


class GameRunning(DeployError):
    pass


class GameStateUnknown(DeployError):
    pass


class NothingToUndo(DeployError):
    pass


@dataclass(frozen=True)
class Deployment:
    id: str
    changes: int  # staged kits and logos it installed (0 for a relink)
    files: int  # files it wrote
    logos: int = 0  # how many of the changes were logos


@dataclass(frozen=True)
class Status:
    block_lost: bool  # the app has kit folders but map.txt does not point to them
    root_lost: bool  # the app has textures in its root but sider.ini does not list it first

    @property
    def ok(self) -> bool:
        return not (self.block_lost or self.root_lost)


class _Paths:
    def __init__(self, game_dir: Path):
        self.sider = Path(game_dir) / "SiderAddons"
        self.ini = self.sider / "sider.ini"
        self.kits = self.sider / "content" / "kits"
        self.map = self.kits / "map.txt"
        self.app_kits = self.kits / kitmap.APP_FOLDER
        self.app_root = self.sider / "livecpk" / kitmap.APP_FOLDER

    def app_folders(self) -> list[tuple[int, str]]:
        """(team id, folder name) of the app's kit folders, named "<id> <name>" """
        if not self.app_kits.is_dir():
            return []
        out = []
        for d in sorted(self.app_kits.iterdir()):
            head = d.name.split(" ", 1)[0]
            if d.is_dir() and head.isdigit():
                out.append((int(head), d.name))
        return out

    def app_folder(self, team_id: int) -> Path | None:
        return next((self.app_kits / name for tid, name in self.app_folders() if tid == team_id), None)

    def root_used(self) -> bool:
        return self.app_root.is_dir() and any(p.is_file() for p in self.app_root.rglob("*"))


class _Journal:
    """records every file a deploy writes, keeping a copy of what was there"""

    def __init__(self, paths: _Paths, folder: Path):
        self.paths, self.folder = paths, folder
        self.files: list[dict] = []
        self._seen: set[str] = set()

    def before_write(self, path: Path) -> None:
        rel = path.relative_to(self.paths.sider).as_posix()
        if rel in self._seen:
            return
        self._seen.add(rel)
        existed = path.is_file()
        if existed:
            keep = self.folder / "before" / rel
            keep.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, keep)
        self.files.append({"path": rel, "existed": existed})

    def write(self, path: Path, data: bytes) -> None:
        self.before_write(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def remove(self, path: Path) -> None:
        self.before_write(path)
        path.unlink()


def _check(game_running: Callable[[], bool | None], unknown_ok: bool) -> None:
    state = game_running()
    if state:
        raise GameRunning("SP Football Life 2027 is running: close the game first.")
    if state is None and not unknown_ok:
        raise GameStateUnknown("Cannot tell whether SP Football Life 2027 is running.")


def _safe(name: str) -> str:
    return _UNSAFE.sub("_", name).strip(" .") or "team"


def _read(path: Path) -> tuple[str, bool]:
    raw = path.read_bytes() if path.is_file() else b""
    return raw.decode("utf-8-sig"), raw.startswith(_BOM)


def _backup(path: Path, today: datetime.date) -> None:
    bak = path.with_name(f"{path.name}.bak-{today:%Y%m%d}")
    if path.is_file() and not bak.exists():
        shutil.copy2(path, bak)


def _write_text(journal: _Journal, path: Path, text: str, bom: bool, today: datetime.date) -> None:
    _backup(path, today)
    journal.write(path, (_BOM if bom else b"") + text.encode("utf-8"))


def _link(paths: _Paths, journal: _Journal, today: datetime.date) -> None:
    """map.txt and sider.ini point to what the app has installed"""
    text, bom = _read(paths.map)
    new = kitmap.with_app_block(text, paths.app_folders())
    if new != text:
        _write_text(journal, paths.map, new, bom, today)
    text, bom = _read(paths.ini)
    new = sider_ini.with_root(text, APP_ROOT) if paths.root_used() else sider_ini.without_root(text, APP_ROOT)
    if new != text:
        _write_text(journal, paths.ini, new, bom, today)


def _kit_folder(paths: _Paths, kit_map: kitmap.KitMap, team_id: int) -> Path | None:
    """the team's kitserver folder: the app's copy, else the folder map.txt names (if it exists)"""
    folder = paths.app_folder(team_id)
    if folder is not None:
        return folder
    source = kit_map.path_of(team_id)
    return source if source is not None and source.is_dir() else None


def _list_kit(journal: _Journal, folder: Path, slot: str) -> None:
    """adds the kit to order.ini (players) or gk_order.ini (goalkeepers) when it is not listed"""
    path = folder / ("gk_order.ini" if slot.startswith("g") else "order.ini")
    lines = (
        [s.strip() for s in path.read_text(encoding="utf-8-sig").splitlines() if s.strip()] if path.is_file() else []
    )
    if slot not in lines:
        journal.write(path, ("\n".join([*lines, slot]) + "\n").encode())


def _put_kit(journal: _Journal, folder: Path, staging: Staging, change, listed: bool) -> None:
    """the kit's folder gets exactly the staged kit's files"""
    slot_dir = folder / change.slot
    if slot_dir.is_dir():
        for f in sorted(p for p in slot_dir.iterdir() if p.is_file()):
            journal.remove(f)
    for f in sorted(staging.path(change).iterdir()):
        journal.write(slot_dir / f.name, f.read_bytes())
    if listed:
        _list_kit(journal, folder, change.slot)


def _install(paths: _Paths, journal: _Journal, staging: Staging) -> None:
    """writes the staged kits, whole kits first (a texture may go into a kit folder they make); _check_slots has made
    sure that every texture for a kitserver team has a kit to go into"""
    kit_map = kitmap.load(paths.map)
    made: set[Path] = set()  # kit folders this deploy makes from nothing (it keeps their kit lists)
    for change in (c for c in staging.changes if c.kind == "logo"):
        for path, data in staging.logo_files(change).items():
            journal.write(paths.app_root / path, data)
    for change in sorted((c for c in staging.changes if c.kind != "logo"), key=lambda c: c.kind != "kit"):
        folder = paths.app_folder(change.team_id)
        if folder is None:
            source = _kit_folder(paths, kit_map, change.team_id)
            if source is not None or change.kind == "kit":
                folder = paths.app_kits / f"{change.team_id} {_safe(change.team_name)}"
                for f in sorted(p for p in source.rglob("*") if p.is_file()) if source else []:
                    journal.write(folder / f.relative_to(source), f.read_bytes())
                if source is None:
                    made.add(folder)
        if folder is None:
            data = staging.path(change).read_bytes()
            journal.write(paths.app_root / kits.TEXTURES / f"u{change.team_id:04d}{change.slot}.ftex", data)
        elif change.kind == "kit":
            listed = folder in made or any((folder / n).is_file() for n in ("order.ini", "gk_order.ini"))
            _put_kit(journal, folder, staging, change, listed)
        else:
            kit = next(k for k in kits.folder_kits(change.team_id, folder, "") if k.slot == change.slot)
            journal.write(kit.file, staging.path(change).read_bytes())


def _check_slots(paths: _Paths, staging: Staging) -> None:
    """refuses, before anything is written, a texture for a kit that the team's kitserver folder will not have"""
    kit_map = kitmap.load(paths.map)
    for change in (c for c in staging.changes if c.kind == "texture"):
        folder = _kit_folder(paths, kit_map, change.team_id)
        new_kits = any(c.kind == "kit" for c in staging.changes if c.team_id == change.team_id)
        if folder is None and not new_kits:
            continue  # kits from the game files: the texture goes to the app's livecpk root
        have = {k.slot for k in kits.folder_kits(change.team_id, folder, "")} if folder else set()
        if change.slot not in have:
            raise DeployError(
                f"{change.team_name}: the new {kits.slot_name(change.slot)} texture needs a kit to go into, and the "
                f"team's kitserver folder has no {change.slot} kit. Import a whole kit for it from a pack instead."
            )


def _new_id() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def _finish(home: Path, journal: _Journal, deploy_id: str, changes: list[dict]) -> Deployment:
    manifest = {"id": deploy_id, "changes": changes, "files": journal.files}
    (journal.folder / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return Deployment(deploy_id, len(changes), len(journal.files), sum(c.get("kind") == "logo" for c in changes))


def deploy(
    game_dir: Path,
    staging: Staging,
    home: Path,
    game_running: Callable[[], bool | None] = process.game_running,
    unknown_ok: bool = False,
    today: datetime.date | None = None,
) -> Deployment:
    if not staging.changes:
        raise DeployError("Nothing to deploy.")
    _check(game_running, unknown_ok)
    paths = _Paths(game_dir)
    _check_slots(paths, staging)
    deploy_id = _new_id()
    journal = _Journal(paths, Path(home) / "deploys" / deploy_id)
    journal.folder.mkdir(parents=True)
    _install(paths, journal, staging)
    _link(paths, journal, today or datetime.date.today())
    changes = [
        {"team_id": c.team_id, "team_name": c.team_name, "slot": c.slot, "kind": c.kind, "source": c.source}
        for c in staging.changes
    ]
    result = _finish(home, journal, deploy_id, changes)
    staging.clear()
    return result


def relink(
    game_dir: Path,
    home: Path,
    game_running: Callable[[], bool | None] = process.game_running,
    unknown_ok: bool = False,
    today: datetime.date | None = None,
) -> Deployment:
    """writes again the app's block in map.txt and its root in sider.ini (after a Mod Studio Build)"""
    _check(game_running, unknown_ok)
    paths = _Paths(game_dir)
    deploy_id = _new_id()
    journal = _Journal(paths, Path(home) / "deploys" / deploy_id)
    journal.folder.mkdir(parents=True)
    _link(paths, journal, today or datetime.date.today())
    return _finish(home, journal, deploy_id, [])


def status(game_dir: Path) -> Status:
    paths = _Paths(game_dir)
    text, _ = _read(paths.map)
    block = kitmap.app_block(text) or []
    roots = sider_ini.parse(_read(paths.ini)[0]).cpk_roots
    return Status(
        block_lost=bool(paths.app_folders()) and block != paths.app_folders(),
        root_lost=paths.root_used() and (not roots or roots[0] != APP_ROOT),
    )


def history(home: Path) -> list[Deployment]:
    folder = Path(home) / "deploys"
    out = []
    for d in sorted(folder.iterdir(), reverse=True) if folder.is_dir() else []:
        m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        logo_count = sum(c.get("kind") == "logo" for c in m["changes"])
        out.append(Deployment(m["id"], len(m["changes"]), len(m["files"]), logo_count))
    return out


def _prune(path: Path, stop: set[Path]) -> None:
    """removes the empty folders above a removed file, up to the folders the app writes into"""
    parent = path.parent
    while parent not in stop and parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent


def undo(
    game_dir: Path,
    home: Path,
    game_running: Callable[[], bool | None] = process.game_running,
    unknown_ok: bool = False,
) -> Deployment:
    """puts back what the last deploy (or relink) changed"""
    done = history(home)
    if not done:
        raise NothingToUndo("Nothing to undo.")
    _check(game_running, unknown_ok)
    paths = _Paths(game_dir)
    folder = Path(home) / "deploys" / done[0].id
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    stop = {paths.kits, paths.sider / "livecpk", paths.sider}
    for entry in reversed(manifest["files"]):
        target = paths.sider / entry["path"]
        if entry["existed"]:
            target.parent.mkdir(parents=True, exist_ok=True)  # an emptied kit folder may have been removed
            shutil.copy2(folder / "before" / entry["path"], target)
        else:
            target.unlink(missing_ok=True)
            _prune(target, stop)
    shutil.rmtree(folder)
    return done[0]
