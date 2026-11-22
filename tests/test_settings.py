"""The app's settings (settings.json in the app data folder: FLKM_HOME, else %APPDATA%/FLKitsManager): the game folder
and how kits are shown. A missing or damaged file gives the defaults."""

from pathlib import Path

from flkm import settings


def test_app_data_folder_is_flkm_home(home):
    assert settings.home() == home


def test_app_data_folder_defaults_to_appdata(monkeypatch, tmp_path):
    monkeypatch.delenv("FLKM_HOME")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert settings.home() == tmp_path / "FLKitsManager"


def test_without_appdata_the_user_profile_is_used(monkeypatch, tmp_path):
    monkeypatch.delenv("FLKM_HOME")
    monkeypatch.delenv("APPDATA")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert settings.home() == tmp_path / "AppData" / "Roaming" / "FLKitsManager"


def test_defaults_without_a_settings_file():
    s = settings.load()
    assert s.game_dir is None and s.view == "folded"


def test_saved_settings_are_loaded_back(home):
    settings.save(settings.Settings(game_dir="D:\\Games\\FL27", view="unrolled"))
    assert (home / "settings.json").is_file()
    assert settings.load() == settings.Settings(game_dir="D:\\Games\\FL27", view="unrolled")


def test_damaged_or_unknown_settings_give_the_defaults(home):
    home.mkdir()
    (home / "settings.json").write_text("{not json", encoding="utf-8")
    assert settings.load() == settings.Settings()
    (home / "settings.json").write_text('["a list"]', encoding="utf-8")
    assert settings.load() == settings.Settings()
    (home / "settings.json").write_text('{"view": "sideways", "game_dir": 5, "other": 1}', encoding="utf-8")
    assert settings.load() == settings.Settings()


def test_a_game_folder_has_sider(game, tmp_path):
    assert not settings.is_game_dir(tmp_path / "nowhere")
    assert not settings.is_game_dir(game)
    (game / "SiderAddons" / "sider.ini").write_text("", encoding="utf-8")
    assert settings.is_game_dir(game)
