"""The app's settings: settings.json in the app data folder (FLKM_HOME, else %APPDATA%/FLKitsManager)."""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

VIEWS = ("folded", "unrolled")


@dataclass(frozen=True)
class Settings:
    game_dir: str | None = None
    view: str = "folded"  # how kits are shown: folded (as in the game) or unrolled (the texture)


def home() -> Path:
    if os.environ.get("FLKM_HOME"):
        return Path(os.environ["FLKM_HOME"])
    appdata = os.environ.get("APPDATA")
    return (Path(appdata) if appdata else Path.home() / "AppData" / "Roaming") / "FLKitsManager"


def _file() -> Path:
    return home() / "settings.json"


def load() -> Settings:
    try:
        data = json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Settings()
    if not isinstance(data, dict):
        return Settings()
    game_dir, view = data.get("game_dir"), data.get("view", "folded")
    if not (game_dir is None or isinstance(game_dir, str)) or view not in VIEWS:
        return Settings()
    return Settings(game_dir=game_dir, view=view)


def save(s: Settings) -> None:
    _file().parent.mkdir(parents=True, exist_ok=True)
    _file().write_text(json.dumps(asdict(s), indent=2), encoding="utf-8")


def is_game_dir(path: Path) -> bool:
    return (Path(path) / "SiderAddons" / "sider.ini").is_file()
