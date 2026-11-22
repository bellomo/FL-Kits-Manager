"""The main window: the team list on the left, the team page on the right. The game folder comes from the command
line or the settings, else the user chooses it; the chosen folder and the kit view are remembered."""

import zipfile
from pathlib import PurePath

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

import flkm
from conftest import build_ftex, competition_record, dxt5_block, team_record, wesys
from flkm import deploy, main_window, settings
from flkm.game import ftex, process
from flkm.import_dialog import ImportDialog
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


def test_replace_with_a_png_keeps_the_header_of_the_kit_it_replaces(qtbot, game, tmp_path, dialogs):
    w = bologna(qtbot, game)
    old = w.catalog.kits(186)[0].texture().data[:0x40]
    src = tmp_path / "home.png"
    Image.new("RGBA", (256, 256), (0, 0, 255, 255)).save(src)
    dialogs.file = str(src)
    w.page.cards[0].replace_button.click()
    data = w.staging.path(w.staging.changes[0]).read_bytes()
    assert data[0x10 + 1 : 0x40] == old[0x10 + 1 :] and ftex.parse(data).width == 256
    assert w.page.cards[0].source.text() == "New kit, not deployed yet: home.png"


def test_replace_with_an_image_that_is_not_a_kit(qtbot, game, tmp_path, dialogs):
    w = bologna(qtbot, game)
    src = tmp_path / "small.png"
    Image.new("RGBA", (64, 64)).save(src)
    dialogs.file = str(src)
    w.page.cards[0].replace_button.click()
    assert w.staging.changes == [] and "256, 512, 1024, 2048 or 4096" in dialogs.warnings[0]


def test_replace_cancelled(qtbot, game, dialogs):
    w = bologna(qtbot, game)
    w.page.cards[0].replace_button.click()
    assert not w.page.cards[0].pending and w.staging.changes == []


def test_replace_with_a_file_that_is_not_a_texture(qtbot, game, tmp_path, dialogs):
    w = bologna(qtbot, game)
    dialogs.file = str(new_texture(tmp_path, b"nope"))
    w.page.cards[0].replace_button.click()
    assert w.staging.changes == [] and dialogs.warnings[0].startswith(
        f"{tmp_path / 'home.ftex'} cannot be used for this kit"
    )


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
    assert not card.pending and "FLKitsManager" in w.page.folder_label.text()  # the page shows the installed kit
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
    assert "_World" in w.page.folder_label.text()
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


def test_undo_and_reapply_while_the_game_runs_change_nothing(qtbot, game, tmp_path, dialogs, closed_game):
    w = bologna(qtbot, game)
    dialogs.file = str(new_texture(tmp_path))
    w.page.cards[0].replace_button.click()
    w.deploy_action.trigger()
    closed_game["running"] = True
    w.undo_action.trigger()
    w.relink_action.trigger()
    assert app_texture(game).read_bytes() == NEW and len(deploy.history(settings.home())) == 1
    assert dialogs.warnings == ["SP Football Life 2027 is running: close the game first."] * 2


def test_an_error_while_deploying_is_shown(qtbot, game, tmp_path, dialogs, closed_game, monkeypatch):
    w = bologna(qtbot, game)
    dialogs.file = str(new_texture(tmp_path))
    w.page.cards[0].replace_button.click()

    def broken(*a, **k):
        raise PermissionError("access denied")

    monkeypatch.setattr(deploy, "deploy", broken)
    w.deploy_action.trigger()
    assert dialogs.warnings == ["Deploy failed: access denied"]


# --- importing kit packs ---------------------------------------------------------------------------------------------


def make_pack(root, colour=NEW):
    """a pack with Bologna's home and third kits and a club the game does not have"""
    base = root / "Serie A Kitpack"
    for team, slots in (("Bologna", ("p1", "p3")), ("Zalgiris", ("p1",))):
        for slot in slots:
            folder = base / team / slot
            folder.mkdir(parents=True)
            (folder / "config.txt").write_text(f"KitFile=k{slot}\n", encoding="utf-8")
            (folder / f"k{slot}.ftex").write_bytes(colour)
    (base / "map.txt").write_text('186, "Bologna"\n', encoding="utf-8")
    return base


@pytest.fixture
def accept_import(monkeypatch):
    """the import dialog is accepted as it opens (with its ticked rows)"""
    seen = []

    def exec_(dialog):
        seen.append(dialog)
        return QDialog.Accepted

    monkeypatch.setattr(ImportDialog, "exec", exec_)
    return seen


def test_import_actions_need_a_game(qtbot, game):
    w = make_window(qtbot)
    assert not w.import_folder_action.isEnabled() and not w.import_zip_action.isEnabled()
    w.open_game(kit_game(game))
    assert w.import_folder_action.isEnabled() and w.import_zip_action.isEnabled()


def test_import_a_pack_folder(qtbot, game, tmp_path, dialogs, accept_import, monkeypatch):
    w = bologna(qtbot, game)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: str(make_pack(tmp_path)))
    w.import_folder_action.trigger()
    [dialog] = accept_import
    assert dialog.windowTitle() == "Import kits from Serie A Kitpack"
    assert [(m.pack_team.name, m.team.id if m.team else None) for m in dialog.matches] == [
        ("Bologna", 186),
        ("Zalgiris", None),
    ]
    assert [(c.team_id, c.slot, c.kind) for c in w.staging.changes] == [(186, "p1", "kit"), (186, "p3", "kit")]
    assert [(c.name.text(), c.pending) for c in w.page.cards] == [("Home · new", True), ("Third · new", True)]
    assert w.page.cards[0].source.text() == "New kit from Serie A Kitpack, not deployed yet"
    assert w.page.cards[0].source.toolTip() == "Serie A Kitpack: Serie A Kitpack/Bologna"
    assert w.statusBar().currentMessage() == "2 kits from Serie A Kitpack waiting for Deploy."


def test_imported_kits_are_deployed_as_a_kitserver_folder(qtbot, game, tmp_path, dialogs, accept_import, closed_game):
    w = bologna(qtbot, game)
    w.import_pack(make_pack(tmp_path))
    w.deploy_action.trigger()
    assert dialogs.asked[-1].startswith("Install 2 kits in the game?\n\nBologna FC: Home (whole kit)\n")
    folder = game / "SiderAddons" / "content" / "kits" / "FLKitsManager" / "186 Bologna FC"
    assert (folder / "p3" / "kp3.ftex").read_bytes() == NEW
    assert [c.kit.source for c in w.page.cards] == ["kitserver: FLKitsManager\\186 Bologna FC"] * 2


def test_import_with_no_team_open(qtbot, game, tmp_path, dialogs, accept_import):
    w = make_window(qtbot, game_dir=kit_game(game))
    w.import_pack(make_pack(tmp_path))
    assert len(w.staging.changes) == 2 and w.pages.currentWidget() is w.start


def test_import_a_zip(qtbot, game, tmp_path, dialogs, accept_import):
    w = bologna(qtbot, game)
    base = make_pack(tmp_path / "src")
    z = tmp_path / "pack.zip"
    with zipfile.ZipFile(z, "w") as f:
        for p in base.rglob("*"):
            f.write(p, p.relative_to(base.parent).as_posix())
    dialogs.file = str(z)
    w.import_zip_action.trigger()
    assert len(w.staging.changes) == 2 and w.staging.changes[0].source == "pack.zip: Serie A Kitpack/Bologna"


def test_import_cancelled(qtbot, game, tmp_path, dialogs, accept_import, monkeypatch):
    w = bologna(qtbot, game)
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: "")
    w.import_folder_action.trigger()
    w.import_zip_action.trigger()  # dialogs.file is ""
    assert accept_import == []
    monkeypatch.setattr(ImportDialog, "exec", lambda d: QDialog.Rejected)
    w.import_pack(make_pack(tmp_path))
    assert w.staging.changes == []


def test_import_of_something_that_is_not_a_pack(qtbot, game, tmp_path, dialogs, accept_import):
    w = bologna(qtbot, game)
    (tmp_path / "empty").mkdir()
    w.import_pack(tmp_path / "empty")
    assert dialogs.infos == ["No kitserver team folders (with kit folders like p1, g1) found in empty."]
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"nope")
    w.import_pack(bad)
    assert dialogs.warnings[0].startswith(f"{bad} cannot be read as a zip")
    assert accept_import == []


def test_kits_that_cannot_be_added_are_listed(qtbot, game, tmp_path, dialogs, accept_import):
    w = bologna(qtbot, game)
    base = make_pack(tmp_path)
    (base / "Bologna" / "p3" / "kp3.ftex").write_bytes(b"not a texture")
    w.import_pack(base)
    assert [c.slot for c in w.staging.changes] == ["p1"]
    assert dialogs.warnings[0].startswith("Some kits were not added:\nSerie A Kitpack/Bologna p3: ")


def test_quit_action_closes_the_window(qtbot):
    w = make_window(qtbot)
    w.show()
    w.quit_action.trigger()
    assert not w.isVisible()


def test_window_module_names_the_app():
    assert main_window.APP_NAME == "FL Kits Manager"


# --- crests ----------------------------------------------------------------------------------------------------------

FLAG = "common/render/symbol/flag/"


def crest_game(game):
    """the kit game with Bologna's crest (256 px) in the livecpk root"""
    kit_game(game)
    flag = game / "SiderAddons" / "livecpk" / "_World" / FLAG
    flag.mkdir(parents=True)
    Image.new("RGBA", (256, 256), (200, 0, 0, 255)).save(flag / "e_000186_r_l.png")
    return game


def test_the_team_page_shows_the_crest_the_game_uses(qtbot, game):
    w = make_window(qtbot, game_dir=crest_game(game))
    w.tree.select_team(186)
    assert not w.page.crest.pixmap().isNull()
    assert w.page.crest_source.text() == "e_000186_r_l.png"
    w.tree.select_team(98)
    assert w.page.crest.text() == "No crest" and w.page.crest_source.text() == "No crest in the game files"


def test_replace_the_crest_waits_for_deploy_then_deploy_installs_it(qtbot, game, tmp_path, dialogs, closed_game):
    w = make_window(qtbot, game_dir=crest_game(game))
    w.tree.select_team(186)
    src = tmp_path / "bologna.png"
    Image.new("RGBA", (300, 300), (0, 0, 200, 255)).save(src)
    dialogs.file = str(src)
    w.page.replace_crest_button.click()
    assert w.page.crest_source.text() == "New crest, not deployed yet: bologna.png"
    assert w.page.crest_source.toolTip() == str(src) and w.page.keep_crest_button.isVisibleTo(w.page)
    assert w.pending_label.text() == "1 logo waiting for Deploy" and w.page.cards[0].kit.slot == "p1"
    w.deploy_action.trigger()
    assert "Bologna FC: Crest" in dialogs.asked[-1] and "Install 1 logo in the game?" in dialogs.asked[-1]
    app = game / "SiderAddons" / "livecpk" / "FLKitsManager" / FLAG
    assert sorted(p.name for p in app.iterdir()) == ["e_000186_r.png", "e_000186_r_l.png", "e_000186_r_ll.png"]
    assert w.statusBar().currentMessage() == "Deployed 1 logo. Restart the game to see it."
    assert w.page.crest_source.text() == "e_000186_r_ll.png"
    dialogs.answers = [False]
    w.undo_action.trigger()
    assert dialogs.asked[-1] == "Undo the last deploy (1 logo)? The files it changed are put back as they were."


def test_kits_and_logos_waiting_are_counted_apart(qtbot, game, tmp_path, dialogs):
    w = make_window(qtbot, game_dir=crest_game(game))
    w.tree.select_team(186)
    dialogs.file = str(new_texture(tmp_path))
    w.page.cards[0].replace_button.click()
    src = tmp_path / "bologna.png"
    Image.new("RGBA", (64, 64)).save(src)
    dialogs.file = str(src)
    w.page.replace_crest_button.click()
    assert w.pending_label.text() == "1 kit and 1 logo waiting for Deploy"
    dialogs.answers = [False]
    w.discard_action.trigger()
    assert dialogs.asked[-1] == "Discard 1 kit and 1 logo waiting for Deploy?"


def test_keep_the_current_crest(qtbot, game, tmp_path, dialogs):
    w = make_window(qtbot, game_dir=crest_game(game))
    w.tree.select_team(186)
    src = tmp_path / "bologna.png"
    Image.new("RGBA", (64, 64)).save(src)
    dialogs.file = str(src)
    w.page.replace_crest_button.click()
    w.page.keep_crest_button.click()
    assert w.staging.changes == [] and w.page.crest_source.text() == "e_000186_r_l.png"


def test_replace_crest_cancelled_or_with_a_file_that_is_not_a_picture(qtbot, game, tmp_path, dialogs):
    w = make_window(qtbot, game_dir=crest_game(game))
    w.tree.select_team(186)
    w.page.replace_crest_button.click()
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"nope")
    dialogs.file = str(bad)
    w.page.replace_crest_button.click()
    assert w.staging.changes == [] and "bad.png cannot be read as a picture" in dialogs.warnings[0]


# --- competition logos -----------------------------------------------------------------------------------------------

EMB = "common/render/symbol/emblemLc/"


def comp_game(game):
    """the crest game with the Coppa Italia (16) and its normal logo (256 px) in the livecpk root"""
    crest_game(game)
    root = game / "SiderAddons" / "livecpk" / "_World"
    (root / "common/etc/pesdb/Competition.bin").write_bytes(wesys(competition_record(16, "ITALY_D1_CUP")))
    (root / EMB).mkdir(parents=True)
    Image.new("RGBA", (256, 256), (0, 160, 0, 255)).save(root / EMB / "emb_0016_l.png")
    return game


def coppa(qtbot, game):
    w = make_window(qtbot, game_dir=comp_game(game))
    w.sides.setCurrentWidget(w.comp_tree)
    assert w.comp_tree.select(16)
    return w


def test_teams_and_competitions_tabs(qtbot, game):
    w = make_window(qtbot, game_dir=comp_game(game))
    assert [w.sides.tabText(i) for i in range(w.sides.count())] == ["Teams", "Competitions"]
    assert w.comp_tree.tree.topLevelItem(0).text(0) == "International (1)"


def test_the_competition_page_shows_its_logos(qtbot, game):
    w = coppa(qtbot, game)
    assert w.pages.currentWidget() is w.comp_page and w.comp_page.title.text() == "ITALY_D1_CUP"
    normal, dark, _ = w.comp_page.cards
    assert normal.source.text() == "emb_0016_l.png" and not normal.light.pixmap().isNull()
    assert w.comp_page.folder_label.text() == str(game / "SiderAddons" / "livecpk" / "_World" / EMB)
    assert dark.source.text() == "Not in the game files"


def test_replace_the_whole_logo_then_one_variant_then_deploy(qtbot, game, tmp_path, dialogs, closed_game):
    w = coppa(qtbot, game)
    src = tmp_path / "coppa.png"
    Image.new("RGBA", (400, 400), (0, 0, 200, 255)).save(src)
    dialogs.file = str(src)
    w.comp_page.replace_all_button.click()
    assert [c.source.text() for c in w.comp_page.cards] == ["New logo, not deployed yet: coppa.png"] * 3
    assert w.comp_page.keep_button.isVisibleTo(w.comp_page) and w.comp_page.cards[0].source.toolTip() == str(src)
    white = tmp_path / "white.png"
    Image.new("RGBA", (100, 100), (255, 255, 255, 255)).save(white)
    dialogs.file = str(white)
    w.comp_page.cards[2].replace_button.click()
    assert w.comp_page.cards[2].source.text() == "New logo, not deployed yet: white.png"
    assert w.comp_page.cards[0].source.text() == "New logo, not deployed yet: coppa.png"
    assert w.pending_label.text() == "1 logo waiting for Deploy"
    w.deploy_action.trigger()
    assert "ITALY_D1_CUP: Logo" in dialogs.asked[-1]
    app = game / "SiderAddons" / "livecpk" / "FLKitsManager" / EMB
    assert len(list(app.iterdir())) == 6
    assert w.pages.currentWidget() is w.comp_page  # the page stays after the game is read again
    assert w.comp_page.cards[1].source.text() == "emb_0016_b_ll.png"


def test_keep_the_current_logo_and_errors(qtbot, game, tmp_path, dialogs):
    w = coppa(qtbot, game)
    w.comp_page.replace_all_button.click()  # cancelled
    bad = tmp_path / "bad.png"
    bad.write_bytes(b"nope")
    dialogs.file = str(bad)
    w.comp_page.cards[0].replace_button.click()
    assert w.staging.changes == [] and "cannot be read as a picture" in dialogs.warnings[0]
    src = tmp_path / "coppa.png"
    Image.new("RGBA", (40, 40)).save(src)
    dialogs.file = str(src)
    w.comp_page.cards[1].replace_button.click()
    assert [c.source.text() for c in w.comp_page.cards][:2] == [
        "emb_0016_l.png",
        "New logo, not deployed yet: coppa.png",
    ]
    w.comp_page.keep_button.click()
    assert w.staging.changes == [] and not w.comp_page.keep_button.isVisibleTo(w.comp_page)


def test_reload_keeps_the_open_competition(qtbot, game):
    w = coppa(qtbot, game)
    w.reload_action.trigger()
    assert w.pages.currentWidget() is w.comp_page and w.comp_page.title.text() == "ITALY_D1_CUP"
    w.comp_tree.search.setText("zzz")  # the search hides it
    w.reload_action.trigger()
    assert w.pages.currentWidget() is w.comp_page and w.comp_page.title.text() == "ITALY_D1_CUP"


def test_the_crest_folder_is_shown_once_and_the_crest_only_by_its_file_name(qtbot, game):
    w = make_window(qtbot, game_dir=crest_game(game))
    w.tree.select_team(186)
    assert w.page.crest_source.text() == "e_000186_r_l.png"
    assert w.page.crest_folder_label.text() == str(game / "SiderAddons" / "livecpk" / "_World" / FLAG)


def test_logo_variants_in_different_folders_show_their_path_from_the_common_folder(qtbot, game):
    comp_game(game)
    other = game / "SiderAddons" / "livecpk" / "FLKitsManager" / EMB
    other.mkdir(parents=True)
    Image.new("RGBA", (256, 256)).save(other / "emb_0016_w_l.png")
    with (game / "SiderAddons" / "sider.ini").open("a", encoding="utf-8") as ini:
        ini.write('cpk.root = ".\\livecpk\\FLKitsManager"\n')
    w = make_window(qtbot, game_dir=game)
    w.sides.setCurrentWidget(w.comp_tree)
    assert w.comp_tree.select(16)
    assert w.comp_page.folder_label.text() == str(game / "SiderAddons" / "livecpk")
    normal, _, white = w.comp_page.cards
    assert normal.source.text() == str(PurePath("_World", EMB, "emb_0016_l.png"))
    assert white.source.text() == str(PurePath("FLKitsManager", EMB, "emb_0016_w_l.png"))
    assert white.source.toolTip() == str(other / "emb_0016_w_l.png")
