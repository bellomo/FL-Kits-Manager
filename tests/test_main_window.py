"""The main window: the team list on the left, the team page on the right. The game folder comes from the command
line or the settings, else the user chooses it; the chosen folder and the kit view are remembered."""

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

import flkm
from conftest import team_record, wesys
from flkm import main_window, settings
from flkm.main_window import MainWindow


def fake_game(game):
    sider = game / "SiderAddons"
    (sider / "sider.ini").write_text('cpk.root = ".\\livecpk\\_World"\n', encoding="utf-8")
    pesdb = sider / "livecpk" / "_World" / "common" / "etc" / "pesdb"
    pesdb.mkdir(parents=True)
    teams = [(186, "Bologna FC", "BOL"), (98, "Inter", "INT")]
    (pesdb / "Team.bin").write_bytes(wesys(b"".join(team_record(*t) for t in teams)))
    return game


def make_window(qtbot, **kw):
    w = MainWindow(**kw)
    qtbot.addWidget(w)
    return w


def test_title_has_name_and_version(qtbot):
    assert make_window(qtbot).windowTitle() == f"FL Kits Manager {flkm.__version__}"


def test_window_is_large_enough_for_the_team_list_and_kits(qtbot):
    w = make_window(qtbot)
    assert w.minimumWidth() >= 1000 and w.minimumHeight() >= 650


def test_without_a_game_folder_the_user_is_asked_to_choose_it(qtbot):
    w = make_window(qtbot)
    assert w.pages.currentWidget() is w.start
    assert w.choose_button.text() == "Choose the game folder…"
    assert w.catalog is None


def test_game_folder_from_the_command_line_is_opened_and_remembered(qtbot, game):
    w = make_window(qtbot, game_dir=fake_game(game))
    assert w.catalog is not None and len(w.catalog.teams) == 2
    assert w.tree.tree.topLevelItemCount() == 1
    assert w.statusBar().currentMessage() == f"2 teams · {game}"
    assert settings.load().game_dir == str(game)


def test_game_folder_from_the_settings(qtbot, game):
    settings.save(settings.Settings(game_dir=str(fake_game(game))))
    assert make_window(qtbot).catalog is not None


def test_a_folder_that_is_not_the_game_is_refused(qtbot, tmp_path, monkeypatch):
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warnings.append(text))
    w = make_window(qtbot, game_dir=tmp_path)
    assert w.catalog is None and w.pages.currentWidget() is w.start
    assert warnings == [f"{tmp_path} is not the SP Football Life 2027 folder: SiderAddons\\sider.ini is missing."]


def test_a_remembered_folder_that_is_gone_is_ignored(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: (_ for _ in ()).throw(AssertionError("no warning")))
    settings.save(settings.Settings(game_dir=str(tmp_path / "gone")))
    assert make_window(qtbot).catalog is None


def test_choosing_the_game_folder(qtbot, game, monkeypatch):
    w = make_window(qtbot)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: "")
    w.choose_button.click()  # cancelled
    assert w.catalog is None
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: str(fake_game(game)))
    w.game_action.trigger()
    assert w.catalog is not None and w.pages.currentWidget() is w.start  # no team chosen yet


def test_choosing_a_team_shows_its_page(qtbot, game):
    w = make_window(qtbot, game_dir=fake_game(game))
    league = w.tree.tree.topLevelItem(0).child(0).child(0)
    w.tree.tree.setCurrentItem(league.child(0))
    assert w.pages.currentWidget() is w.page
    assert w.page.title.text() == "Bologna FC"
    assert w.page.empty.isVisibleTo(w.page)  # no textures in the fake game


def test_kit_view_is_remembered(qtbot, game):
    w = make_window(qtbot, game_dir=fake_game(game))
    w.page.unrolled_button.click()
    assert settings.load().view == "unrolled"
    assert make_window(qtbot).page.view == "unrolled"


@pytest.fixture
def app_font(qapp):
    """the application font as it was: changing the text size must not leak into other tests"""
    original = QApplication.font()
    yield original
    QApplication.setFont(original)


def test_larger_and_smaller_text(qtbot, app_font):
    w = make_window(qtbot)
    start = QApplication.font().pointSize()
    w.larger_text_action.trigger()
    w.larger_text_action.trigger()
    assert QApplication.font().pointSize() == start + 2
    assert settings.load().font_size == start + 2
    w.smaller_text_action.trigger()
    assert QApplication.font().pointSize() == start + 1
    assert settings.load().font_size == start + 1


def test_default_text_size(qtbot, app_font):
    w = make_window(qtbot)
    start = QApplication.font().pointSize()
    w.larger_text_action.trigger()
    w.default_text_action.trigger()
    assert QApplication.font().pointSize() == start
    assert settings.load().font_size is None


def test_text_size_has_limits(qtbot, app_font):
    settings.save(settings.Settings(font_size=settings.FONT_SIZES[-1]))
    w = make_window(qtbot)
    w.larger_text_action.trigger()
    assert QApplication.font().pointSize() == settings.FONT_SIZES[-1]
    settings.save(settings.Settings(font_size=settings.FONT_SIZES[0]))
    w = make_window(qtbot)
    w.smaller_text_action.trigger()
    assert QApplication.font().pointSize() == settings.FONT_SIZES[0]


def test_remembered_text_size_is_used_at_start(qtbot, app_font):
    settings.save(settings.Settings(font_size=17))
    make_window(qtbot)
    assert QApplication.font().pointSize() == 17


def test_text_size_shortcuts(qtbot, app_font):
    w = make_window(qtbot)
    assert w.larger_text_action.shortcut().toString() == "Ctrl++"
    assert w.smaller_text_action.shortcut().toString() == "Ctrl+-"
    assert w.default_text_action.shortcut().toString() == "Ctrl+0"


def test_quit_action_closes_the_window(qtbot):
    w = make_window(qtbot)
    w.show()
    w.quit_action.trigger()
    assert not w.isVisible()


def test_window_module_names_the_app():
    assert main_window.APP_NAME == "FL Kits Manager"
