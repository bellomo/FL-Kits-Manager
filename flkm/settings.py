"""The app's settings: settings.json in the app data folder (FLKM_HOME, else %APPDATA%/FLKitsManager)."""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

VIEWS = ("folded", "unrolled")
FONT_SIZES = tuple(range(8, 29))  # text sizes the user can choose, in points


@dataclass(frozen=True)
class Settings:
    game_dir: str | None = None
    view: str = "folded"  # how kits are shown: folded (as in the game) or unrolled (the texture)
    font_size: int | None = None  # text size in points; None = the system's
    claude_path: str | None = None  # Claude Code chosen by the user; None = looked for (claude.find)


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
    game_dir, view, font_size = data.get("game_dir"), data.get("view", "folded"), data.get("font_size")
    if not (game_dir is None or isinstance(game_dir, str)) or view not in VIEWS:
        return Settings()
    if font_size is not None and (isinstance(font_size, bool) or font_size not in FONT_SIZES):
        return Settings()
    claude_path = data.get("claude_path")
    if not (claude_path is None or isinstance(claude_path, str)):
        claude_path = None  # only this setting is lost
    return Settings(game_dir=game_dir, view=view, font_size=font_size, claude_path=claude_path)


def save(s: Settings) -> None:
    _file().parent.mkdir(parents=True, exist_ok=True)
    _file().write_text(json.dumps(asdict(s), indent=2), encoding="utf-8")


def is_game_dir(path: Path) -> bool:
    return (Path(path) / "SiderAddons" / "sider.ini").is_file()
