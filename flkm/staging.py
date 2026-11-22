"""The staging area: kits chosen to replace the game's, kept (with a copy of each texture) until Deploy installs them.

<folder>/staging.json lists the changes; <folder>/files/u<team><slot>.ftex are the textures.
"""

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from flkm.game import ftex


@dataclass(frozen=True)
class Change:
    team_id: int
    team_name: str
    slot: str
    file: str  # name of the copy in <folder>/files
    source: str  # the file the user chose


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

    def add(self, team_id: int, team_name: str, slot: str, src: Path) -> Change:
        """stages src as the texture of the team's slot; raises FtexError if src is not a readable FTEX"""
        data = Path(src).read_bytes()
        ftex.parse(data)
        change = Change(team_id, team_name, slot, f"u{team_id}{slot}.ftex", str(src))
        self.path(change).parent.mkdir(parents=True, exist_ok=True)
        self.path(change).write_bytes(data)
        self.changes = [c for c in self.changes if (c.team_id, c.slot) != (team_id, slot)] + [change]
        self._save()
        return change

    def for_team(self, team_id: int) -> dict[str, Change]:
        return {c.slot: c for c in self.changes if c.team_id == team_id}

    def remove(self, team_id: int, slot: str) -> None:
        for c in [c for c in self.changes if (c.team_id, c.slot) == (team_id, slot)]:
            self.path(c).unlink(missing_ok=True)
            self.changes.remove(c)
        self._save()

    def clear(self) -> None:
        shutil.rmtree(self.folder / "files", ignore_errors=True)
        self.changes = []
        self._save()
