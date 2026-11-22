"""Where the game takes a file from. Read only.

Order (the first source that has the file wins): the livecpk roots of sider.ini in their order, then the update CPKs
in download/, then the CPKs in Data/ (in both folders the newest name first, e.g. data_s26271 before data_s2627).
"""

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from flkm.game import sider_ini
from flkm.game.cpk import Cpk, CpkError


@dataclass(frozen=True)
class Found:
    path: str  # the game path, folders separated by "/"
    source: str  # where it was found, e.g. "livecpk\\_FL26Megapack" or "download\\data_s26271.cpk"
    file: Path | None = None  # a loose file in a livecpk root
    archive: Cpk | None = None

    def read(self) -> bytes:
        return self.file.read_bytes() if self.file else self.archive.read(self.path)

    @property
    def folder(self) -> Path:
        """the folder of the loose file, or of the CPK that holds it"""
        return self.file.parent if self.file else self.archive.path.parent

    @property
    def file_name(self) -> str:
        """the file's name in that folder ("<cpk> › <file>" for a file in a CPK)"""
        return self.file.name if self.file else f"{self.archive.path.name} › {self.path.rsplit('/', 1)[-1]}"


def _windows(p: Path) -> str:
    return str(PureWindowsPath(p))


class GameFiles:
    def __init__(self, game_dir: Path):
        self.game_dir = Path(game_dir)
        self.sider_folder = self.game_dir / "SiderAddons"
        ini = self.sider_folder / "sider.ini"
        self.sider = sider_ini.load(ini) if ini.is_file() else sider_ini.parse("", folder=self.sider_folder)
        self.roots = self.sider.root_paths()
        self.archives: list[Cpk] = []
        self.skipped: list[Path] = []  # CPKs that could not be read
        for folder in ("download", "Data"):
            for p in sorted((self.game_dir / folder).glob("*.cpk"), reverse=True):
                try:
                    self.archives.append(Cpk(p))
                except (CpkError, OSError):
                    self.skipped.append(p)

    def _label(self, root: Path) -> str:
        try:
            return _windows(root.relative_to(self.sider_folder))
        except ValueError:
            return _windows(root)

    def find(self, path: str) -> Found | None:
        for root in self.roots:
            f = root / Path(*path.split("/"))
            if f.is_file():
                return Found(path, self._label(root), file=f)
        for archive in self.archives:
            if archive.get(path):
                return Found(path, _windows(archive.path.relative_to(self.game_dir)), archive=archive)
        return None
