"""The main window: the team list on the left, the team page on the right. The game folder comes from the command
line or the settings, else the user chooses it; the chosen folder and the kit view are remembered."""

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

import flkm
from conftest import build_ftex, dxt5_block, team_record, wesys
from flkm import deploy, main_window, settings
from flkm.game import process
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


def add_team(game, team):
    """the game changed on disk: one more team in Team.bin"""
    team_bin = game / "SiderAddons" / "livecpk" / "_World" / "common" / "etc" / "pesdb" / "Team.bin"
    teams = [(186, "Bologna FC", "BOL"), (98, "Inter", "INT"), team]
    team_bin.write_bytes(wesys(b"".join(team_record(*t) for t in teams)))


def test_reload_is_possible_only_with_a_game_open(qtbot, game):
    w = make_window(qtbot)
    assert not w.reload_action.isEnabled()
    assert w.reload_action.shortcut().toString() == "F5"
    w.open_game(fake_game(game))
    assert w.reload_action.isEnabled()


def test_reload_reads_the_game_again(qtbot, game):
    w = make_window(qtbot, game_dir=fake_game(game))
    add_team(game, (73947, "Aalborg Boldspilklub", "AAL"))
    w.reload_action.trigger()
    assert len(w.catalog.teams) == 3 and w.statusBar().currentMessage() == f"3 teams · {game}"
    assert w.pages.currentWidget() is w.start  # no team was open


def test_reload_keeps_the_open_team_and_the_search(qtbot, game):
    w = make_window(qtbot, game_dir=fake_game(game))
    w.tree.search.setText("inter")
    w.tree.select_team(98)
    add_team(game, (73947, "Aalborg Boldspilklub", "AAL"))
    w.reload_action.trigger()
    assert w.tree.search.text() == "inter"
    assert w.pages.currentWidget() is w.page and w.page.title.text() == "Inter"
    assert w.tree.tree.currentItem().text(0) == "Inter"


def test_reload_shows_the_open_team_even_when_the_search_hides_it(qtbot, game):
    w = make_window(qtbot, game_dir=fake_game(game))
    w.tree.select_team(98)
    w.tree.search.setText("bologna")
    w.reload_action.trigger()
    assert w.pages.currentWidget() is w.page and w.page.title.text() == "Inter"


def test_reload_when_the_open_team_is_gone(qtbot, game):
    w = make_window(qtbot, game_dir=fake_game(game))
    add_team(game, (73947, "Aalborg Boldspilklub", "AAL"))
    w.reload_action.trigger()
    w.tree.select_team(73947)
    fake_game_teams_only_two(game)
    w.reload_action.trigger()
    assert w.pages.currentWidget() is w.start


def fake_game_teams_only_two(game):
    team_bin = game / "SiderAddons" / "livecpk" / "_World" / "common" / "etc" / "pesdb" / "Team.bin"
    team_bin.write_bytes(wesys(b"".join(team_record(*t) for t in [(186, "Bologna FC", "BOL"), (98, "Inter", "INT")])))


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


# --- Replace, Deploy, Undo -------------------------------------------------------------------------------------------

TEX = "Asset/model/character/uniform/texture/#windx11/"
OLD, NEW = build_ftex(4, 4, 4, [dxt5_block(0xF800)]), build_ftex(4, 4, 4, [dxt5_block(0x001F)])


def kit_game(game):
    """the fake game with Bologna's home kit in the livecpk root"""
    fake_game(game)
    textures = game / "SiderAddons" / "livecpk" / "_World" / TEX
    textures.mkdir(parents=True)
    (textures / "u0186p1.ftex").write_bytes(OLD)
    return game


def new_texture(tmp_path, data=NEW):
    p = tmp_path / "home.ftex"
    p.write_bytes(data)
    return p


class Dialogs:
    """answers the window's questions and records its messages"""

    def __init__(self, monkeypatch):
        self.answers, self.asked, self.warnings, self.infos = [], [], [], []
        self.file = ""
        monkeypatch.setattr(QMessageBox, "question", self._question)
        monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: self.warnings.append(text))
        monkeypatch.setattr(QMessageBox, "information", lambda parent, title, text: self.infos.append(text))
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (self.file, ""))

    def _question(self, parent, title, text, *a, **k):
        self.asked.append(text)
        return QMessageBox.Yes if (self.answers.pop(0) if self.answers else True) else QMessageBox.No


@pytest.fixture
def dialogs(monkeypatch):
    return Dialogs(monkeypatch)


@pytest.fixture
def closed_game(monkeypatch):
    state = {"running": False}
    monkeypatch.setattr(process, "game_running", lambda: state["running"])
    return state


def bologna(qtbot, game):
    w = make_window(qtbot, game_dir=kit_game(game))
    w.tree.select_team(186)
    return w


def app_texture(game):
    return game / "SiderAddons" / "livecpk" / "FLKitsManager" / TEX / "u0186p1.ftex"


def test_changes_menu_without_a_game(qtbot):
    w = make_window(qtbot)
    actions = (w.deploy_action, w.discard_action, w.undo_action, w.relink_action)
    assert [a.isEnabled() for a in actions] == [False] * 4
    assert w.deploy_action.shortcut().toString() == "Ctrl+D"


def test_replace_a_kit_waits_for_deploy(qtbot, game, tmp_path, dialogs):
    w = bologna(qtbot, game)
    assert not w.deploy_action.isEnabled() and not w.pending_label.isVisibleTo(w)
    dialogs.file = str(new_texture(tmp_path))
    w.page.cards[0].replace_button.click()
    card = w.page.cards[0]
    assert card.pending and card.source.text() == "New kit, not deployed yet: home.ftex"
    assert card.source.toolTip() == str(tmp_path / "home.ftex")
    assert w.deploy_action.isEnabled() and w.discard_action.isEnabled()
    assert w.pending_label.isVisibleTo(w) and w.pending_label.text() == "1 kit waiting for Deploy"
    assert not app_texture(game).exists()  # nothing written to the game yet
    assert len(make_window(qtbot).staging.changes) == 1  # kept when the app is closed


def test_replace_cancelled(qtbot, game, dialogs):
    w = bologna(qtbot, game)
    w.page.cards[0].replace_button.click()
    assert not w.page.cards[0].pending and w.staging.changes == []


def test_replace_with_a_file_that_is_not_a_texture(qtbot, game, tmp_path, dialogs):
    w = bologna(qtbot, game)
    dialogs.file = str(new_texture(tmp_path, b"nope"))
    w.page.cards[0].replace_button.click()
    assert w.staging.changes == [] and dialogs.warnings[0].startswith(f"{tmp_path / 'home.ftex'} is not a readable")


def test_keep_the_current_kit(qtbot, game, tmp_path, dialogs):
    w = bologna(qtbot, game)
    dialogs.file = str(new_texture(tmp_path))
    w.page.cards[0].replace_button.click()
    w.page.cards[0].discard_button.click()
    assert not w.page.cards[0].pending and w.staging.changes == [] and not w.deploy_action.isEnabled()


def test_discard_all_changes_asks_first(qtbot, game, tmp_path, dialogs):
    w = bologna(qtbot, game)
    dialogs.file = str(new_texture(tmp_path))
    w.page.cards[0].replace_button.click()
    dialogs.answers = [False]
    w.discard_action.trigger()
    assert len(w.staging.changes) == 1
    w.discard_action.trigger()
    assert w.staging.changes == [] and not w.page.cards[0].pending
    assert dialogs.asked[0] == "Discard 1 kit waiting for Deploy?"


def test_deploy_installs_the_kits_and_reads_the_game_again(qtbot, game, tmp_path, dialogs, closed_game):
    w = bologna(qtbot, game)
    dialogs.file = str(new_texture(tmp_path))
    w.page.cards[0].replace_button.click()
    w.deploy_action.trigger()
    assert dialogs.asked[0].startswith("Install 1 kit in the game?\n\nBologna FC: Home\n")
    assert app_texture(game).read_bytes() == NEW
    assert w.staging.changes == [] and not w.deploy_action.isEnabled() and w.undo_action.isEnabled()
    card = w.page.cards[0]
    assert not card.pending and "FLKitsManager" in card.source.text()  # the page shows the installed kit
    assert w.statusBar().currentMessage() == "Deployed 1 kit. Restart the game to see it."


def test_deploy_of_several_kits(qtbot, game, tmp_path, dialogs, closed_game):
    w = bologna(qtbot, game)
    w.staging.add(186, "Bologna FC", "p1", new_texture(tmp_path))
    w.staging.add(5, "New Club", "p1", new_texture(tmp_path))
    w._update_changes()
    w.deploy_action.trigger()
    assert w.statusBar().currentMessage() == "Deployed 2 kits. Restart the game to see them."


def test_deploy_cancelled(qtbot, game, tmp_path, dialogs, closed_game):
    w = bologna(qtbot, game)
    dialogs.file = str(new_texture(tmp_path))
    w.page.cards[0].replace_button.click()
    dialogs.answers = [False]
    w.deploy_action.trigger()
    assert not app_texture(game).exists() and len(w.staging.changes) == 1


def test_deploy_while_the_game_runs(qtbot, game, tmp_path, dialogs, closed_game):
    w = bologna(qtbot, game)
    dialogs.file = str(new_texture(tmp_path))
    w.page.cards[0].replace_button.click()
    closed_game["running"] = True
    w.deploy_action.trigger()
    assert dialogs.warnings == ["SP Football Life 2027 is running: close the game first."]
    assert not app_texture(game).exists() and len(w.staging.changes) == 1


def test_deploy_when_the_game_state_is_unknown_asks_the_user(qtbot, game, tmp_path, dialogs, closed_game):
    w = bologna(qtbot, game)
    dialogs.file = str(new_texture(tmp_path))
    w.page.cards[0].replace_button.click()
    closed_game["running"] = None
    dialogs.answers = [True, False]  # install: yes; is the game closed: no
    w.deploy_action.trigger()
    assert dialogs.asked[1].startswith("Cannot tell whether SP Football Life 2027 is running.")
    assert not app_texture(game).exists()
    w.deploy_action.trigger()  # yes and yes
    assert app_texture(game).read_bytes() == NEW


def test_undo_last_deploy(qtbot, game, tmp_path, dialogs, closed_game):
    w = bologna(qtbot, game)
    dialogs.file = str(new_texture(tmp_path))
    w.page.cards[0].replace_button.click()
    w.deploy_action.trigger()
    dialogs.answers = [False]
    w.undo_action.trigger()
    assert app_texture(game).exists()
    w.undo_action.trigger()
    assert dialogs.asked[-1] == "Undo the last deploy (1 kit)? The files it changed are put back as they were."
    assert not app_texture(game).exists() and not w.undo_action.isEnabled()
    assert "_World" in w.page.cards[0].source.text()
    assert w.statusBar().currentMessage() == "Last deploy undone. Restart the game to see the change."


def test_links_lost_after_a_mod_studio_build_are_shown_and_reapplied(qtbot, game, tmp_path, dialogs, closed_game):
    w = bologna(qtbot, game)
    assert not w.links_banner.isVisibleTo(w)
    dialogs.file = str(new_texture(tmp_path))
    w.page.cards[0].replace_button.click()
    w.deploy_action.trigger()
    ini = game / "SiderAddons" / "sider.ini"
    ini.write_text('cpk.root = ".\\livecpk\\_World"\n', encoding="utf-8")  # rewritten by another tool
    w.reload_action.trigger()
    assert w.links_banner.isVisibleTo(w) and "sider.ini" in w.links_text.text()
    w.relink_button.click()
    assert not w.links_banner.isVisibleTo(w) and "FLKitsManager" in ini.read_text(encoding="utf-8")


def test_an_error_while_deploying_is_shown(qtbot, game, tmp_path, dialogs, closed_game, monkeypatch):
    w = bologna(qtbot, game)
    dialogs.file = str(new_texture(tmp_path))
    w.page.cards[0].replace_button.click()

    def broken(*a, **k):
        raise PermissionError("access denied")

    monkeypatch.setattr(deploy, "deploy", broken)
    w.deploy_action.trigger()
    assert dialogs.warnings == ["Deploy failed: access denied"]


def test_quit_action_closes_the_window(qtbot):
    w = make_window(qtbot)
    w.show()
    w.quit_action.trigger()
    assert not w.isVisible()


def test_window_module_names_the_app():
    assert main_window.APP_NAME == "FL Kits Manager"
