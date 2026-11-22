"""Main window: the team list on the left, the page of the chosen team on the right.

Kits chosen with Replace… (a texture) or Changes > Import kit pack (whole kits) wait in the staging area (shown on
the team page) until Changes > Deploy installs them; Changes > Undo last deploy puts back what the last deploy changed.
"""

import dataclasses
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import flkm
from flkm import catalog, deploy, pack, settings
from flkm.game import ftex, kits, process
from flkm.import_dialog import ImportDialog
from flkm.staging import Staging
from flkm.team_page import PENDING_COLOUR, TeamPage, slot_name
from flkm.team_tree import TeamTree

APP_NAME = "FL Kits Manager"
GAME_NAME = "SP Football Life 2027"
_SYSTEM_FONT: list[QFont] = []  # the application font before the user changed the text size


def _system_font() -> QFont:
    if not _SYSTEM_FONT:
        _SYSTEM_FONT.append(QFont(QApplication.font()))
    return _SYSTEM_FONT[0]


def _apply_text_size(size: int | None) -> None:
    font = QFont(_system_font())
    if size is not None:
        font.setPointSize(size)
    QApplication.setFont(font)


def _kits(n: int) -> str:
    return f"{n} kit" if n == 1 else f"{n} kits"


class MainWindow(QMainWindow):
    def __init__(self, game_dir: Path | None = None):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {flkm.__version__}")
        self.setMinimumSize(1000, 650)
        self.settings = settings.load()
        self.staging = Staging(settings.home() / "staging")
        self.catalog: catalog.Catalog | None = None
        self.game_dir: Path | None = None
        self.team_id: int | None = None  # the team whose page is open

        self.tree = TeamTree()
        self.page = TeamPage(view=self.settings.view)
        self.start = QWidget()
        self.start_text = QLabel(f"Choose the folder of {GAME_NAME} to see its teams and kits.")
        self.start_text.setAlignment(Qt.AlignCenter)
        self.choose_button = QPushButton("Choose the game folder…")
        start_layout = QVBoxLayout(self.start)
        start_layout.addStretch()
        start_layout.addWidget(self.start_text)
        start_layout.addWidget(self.choose_button, 0, Qt.AlignCenter)
        start_layout.addStretch()
        self.pages = QStackedWidget()
        self.pages.addWidget(self.start)
        self.pages.addWidget(self.page)

        self.links_banner = QWidget()  # shown when another tool removed the app's links to its kits
        self.links_banner.setStyleSheet(f"background: {PENDING_COLOUR}; color: white")
        self.links_text = QLabel()
        self.links_text.setWordWrap(True)
        self.relink_button = QPushButton("Re-apply")
        banner_layout = QHBoxLayout(self.links_banner)
        banner_layout.addWidget(self.links_text, 1)
        banner_layout.addWidget(self.relink_button)
        self.links_banner.hide()
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.links_banner)
        right_layout.addWidget(self.pages, 1)

        splitter = QSplitter()
        splitter.addWidget(self.tree)
        splitter.addWidget(right)
        splitter.setSizes([320, 880])
        self.setCentralWidget(splitter)
        self.pending_label = QLabel()
        self.pending_label.setStyleSheet(f"color: {PENDING_COLOUR}; font-weight: bold")
        self.statusBar().addPermanentWidget(self.pending_label)

        menu = self.menuBar().addMenu("&File")
        self.game_action = QAction("&Game folder…", self)
        self.quit_action = QAction("&Quit", self)
        self.reload_action = QAction("&Reload", self, shortcut=QKeySequence("F5"), enabled=False)
        self.reload_action.setStatusTip("Read the game again (after changing kits, map.txt or the Mod Studio world)")
        menu.addAction(self.game_action)
        menu.addAction(self.reload_action)
        menu.addSeparator()
        menu.addAction(self.quit_action)
        view = self.menuBar().addMenu("&View")
        self.larger_text_action = QAction("&Larger text", self, shortcuts=[QKeySequence("Ctrl++"), "Ctrl+="])
        self.smaller_text_action = QAction("&Smaller text", self, shortcut=QKeySequence("Ctrl+-"))
        self.default_text_action = QAction("&Default text size", self, shortcut=QKeySequence("Ctrl+0"))
        for action in (self.larger_text_action, self.smaller_text_action, self.default_text_action):
            view.addAction(action)
        changes = self.menuBar().addMenu("&Changes")
        self.import_folder_action = QAction("Import kit pack (&folder)…", self, enabled=False)
        self.import_zip_action = QAction("Import kit pack (&zip)…", self, enabled=False)
        for action in (self.import_folder_action, self.import_zip_action):
            action.setStatusTip("Take whole kits from a kit pack (kitserver team folders); they wait for Deploy")
            changes.addAction(action)
        changes.addSeparator()
        self.deploy_action = QAction("&Deploy to the game", self, shortcut=QKeySequence("Ctrl+D"))
        self.deploy_action.setStatusTip("Install the kits waiting for Deploy (the game must be closed)")
        self.discard_action = QAction("Dis&card all changes", self)
        self.undo_action = QAction("&Undo last deploy", self)
        self.undo_action.setStatusTip("Put back the files the last deploy changed")
        self.relink_action = QAction("&Re-apply links to the app's kits", self)
        self.relink_action.setStatusTip("Write again the app's lines in map.txt and its root in sider.ini")
        for action in (self.deploy_action, self.discard_action, self.undo_action):
            changes.addAction(action)
        changes.addSeparator()
        changes.addAction(self.relink_action)
        self.larger_text_action.triggered.connect(lambda: self._step_text(+1))
        self.smaller_text_action.triggered.connect(lambda: self._step_text(-1))
        self.default_text_action.triggered.connect(lambda: self.set_text_size(None))
        _apply_text_size(self.settings.font_size)

        self.choose_button.clicked.connect(self.choose_game)
        self.game_action.triggered.connect(self.choose_game)
        self.quit_action.triggered.connect(self.close)
        self.reload_action.triggered.connect(self.reload)
        self.import_folder_action.triggered.connect(self.import_folder)
        self.import_zip_action.triggered.connect(self.import_zip)
        self.deploy_action.triggered.connect(self.deploy_changes)
        self.discard_action.triggered.connect(self.discard_changes)
        self.undo_action.triggered.connect(self.undo_deploy)
        self.relink_action.triggered.connect(self.relink)
        self.relink_button.clicked.connect(self.relink)
        self.tree.team_selected.connect(self.show_team)
        self.page.view_changed.connect(self._view_changed)
        self.page.replace_requested.connect(self.replace_kit)
        self.page.discard_requested.connect(self.keep_kit)

        if game_dir is not None:
            self.open_game(Path(game_dir))
        elif self.settings.game_dir and settings.is_game_dir(Path(self.settings.game_dir)):
            self.open_game(Path(self.settings.game_dir))
        self._update_changes()

    # --- game and teams ----------------------------------------------------------------------------------------------

    def choose_game(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, f"Folder of {GAME_NAME}", self.settings.game_dir or "")
        if folder:
            self.open_game(Path(folder))

    def open_game(self, game_dir: Path) -> None:
        if not settings.is_game_dir(game_dir):
            QMessageBox.warning(
                self,
                APP_NAME,
                f"{game_dir} is not the {GAME_NAME} folder: SiderAddons\\sider.ini is missing.",
            )
            return
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.catalog = catalog.load(game_dir)
        finally:
            QGuiApplication.restoreOverrideCursor()
        self.game_dir, self.team_id = game_dir, None
        self.tree.set_catalog(self.catalog)
        self.start_text.setText("Choose a team on the left.")
        self.choose_button.hide()
        self.pages.setCurrentWidget(self.start)
        self.reload_action.setEnabled(True)
        self.statusBar().showMessage(f"{len(self.catalog.teams)} teams · {game_dir}")
        self._save(game_dir=str(game_dir))
        self._update_changes()

    def reload(self) -> None:
        """reads the game again, keeping the search and the open team"""
        team_id = self.team_id
        self.open_game(self.game_dir)
        if team_id is not None and self.catalog.get(team_id) and not self.tree.select_team(team_id):
            self.show_team(team_id)  # the search hides it

    def show_team(self, team_id: int) -> None:
        staged = self.staging.for_team(team_id)

        def label(c) -> str:
            if c.kind == "kit":
                return f"New kit from {c.source.split(': ')[0]}, not deployed yet"  # the pack; its folder: tooltip
            return f"New kit, not deployed yet: {Path(c.source).name}"

        pending = {
            slot: kits.Kit(team_id, slot, label(c), file=self.staging.texture_path(c)) for slot, c in staged.items()
        }
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.page.show_team(self.catalog.get(team_id), self.catalog.kits(team_id), pending)
        finally:
            QGuiApplication.restoreOverrideCursor()
        for card in self.page.cards:
            if card.pending:
                card.source.setToolTip(staged[card.kit.slot].source)  # the whole path of the chosen file or pack
        self.team_id = team_id
        self.pages.setCurrentWidget(self.page)

    # --- changes -----------------------------------------------------------------------------------------------------

    def import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Folder of a kit pack", "")
        if folder:
            self.import_pack(Path(folder))

    def import_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Kit pack", "", "Zip files (*.zip)")
        if path:
            self.import_pack(Path(path))

    def import_pack(self, source: Path) -> None:
        """matches the pack's team folders with the game's teams; the kits the user confirms wait for Deploy"""
        try:
            kit_pack = pack.open_pack(source)
        except pack.PackError as e:
            QMessageBox.warning(self, APP_NAME, str(e))
            return
        if not kit_pack.teams:
            QMessageBox.information(
                self, APP_NAME, f"No kitserver team folders (with kit folders like p1, g1) found in {source.name}."
            )
            return
        matches = pack.match(kit_pack.teams, self.catalog.teams)
        dialog = ImportDialog(source.name, matches, self.catalog.search, self)
        if dialog.exec() != QDialog.Accepted:
            return
        added, failed = 0, []
        for pack_team, team in dialog.chosen():
            where = pack_team.path or "(the pack itself)"
            for slot in pack_team.slots:
                try:
                    files = kit_pack.kit_files(pack_team, slot)
                    texture = kit_pack.texture_name(pack_team, slot)
                    self.staging.add_kit(team.id, team.name, slot, files, texture, f"{source.name}: {where}")
                    added += 1
                except (pack.PackError, ftex.FtexError, ValueError, OSError) as e:
                    failed.append(f"{where} {slot}: {e}")
        if failed:
            QMessageBox.warning(self, APP_NAME, "Some kits were not added:\n" + "\n".join(failed[:20]))
        self._update_changes()
        if self.team_id is not None:
            self.show_team(self.team_id)
        self.statusBar().showMessage(f"{_kits(added)} from {source.name} waiting for Deploy.")

    def replace_kit(self, slot: str) -> None:
        team = self.catalog.get(self.team_id)
        path, _ = QFileDialog.getOpenFileName(
            self, f"New {slot_name(slot)} kit for {team.name}", "", "FTEX textures (*.ftex)"
        )
        if not path:
            return
        try:
            self.staging.add(team.id, team.name, slot, Path(path))
        except (ftex.FtexError, ValueError, OSError) as e:
            QMessageBox.warning(self, APP_NAME, f"{path} is not a readable FTEX texture: {e}")
            return
        self._changes_made()

    def keep_kit(self, slot: str) -> None:
        self.staging.remove(self.team_id, slot)
        self._changes_made()

    def discard_changes(self) -> None:
        if self._ask(f"Discard {_kits(len(self.staging.changes))} waiting for Deploy?"):
            self.staging.clear()
            self._changes_made()

    def deploy_changes(self) -> None:
        changes = self.staging.changes
        listing = "\n".join(
            f"{c.team_name}: {slot_name(c.slot)}{' (whole kit)' if c.kind == 'kit' else ''}" for c in changes
        )
        question = (
            f"Install {_kits(len(changes))} in the game?\n\n{listing}\n\n"
            "The game must be closed. Changes > Undo last deploy puts back the files as they were."
        )
        if not self._ask(question):
            return
        done = self._game_op(
            "Deploy",
            lambda unknown_ok: deploy.deploy(
                self.game_dir,
                self.staging,
                settings.home(),
                game_running=process.game_running,
                unknown_ok=unknown_ok,
            ),
        )
        if done:
            them = "it" if done.changes == 1 else "them"
            self._after_game_change(f"Deployed {_kits(done.changes)}. Restart the game to see {them}.")

    def undo_deploy(self) -> None:
        last = deploy.history(settings.home())[0]
        what = _kits(last.changes) if last.changes else "re-applied links"
        if not self._ask(f"Undo the last deploy ({what})? The files it changed are put back as they were."):
            return
        undone = self._game_op(
            "Undo",
            lambda unknown_ok: deploy.undo(
                self.game_dir, settings.home(), game_running=process.game_running, unknown_ok=unknown_ok
            ),
        )
        if undone:
            self._after_game_change("Last deploy undone. Restart the game to see the change.")

    def relink(self) -> None:
        done = self._game_op(
            "Re-apply",
            lambda unknown_ok: deploy.relink(
                self.game_dir, settings.home(), game_running=process.game_running, unknown_ok=unknown_ok
            ),
        )
        if done:
            self._after_game_change("Links to the app's kits written again. Restart the game to see them.")

    def _game_op(self, name: str, op: Callable[[bool], deploy.Deployment]) -> deploy.Deployment | None:
        """runs a change to the game files; asks the user when it cannot tell whether the game is running"""
        try:
            try:
                return op(False)
            except deploy.GameStateUnknown as e:
                if not self._ask(f"{e}\n\nIs the game closed? Go on only if it is."):
                    return None
                return op(True)
        except deploy.DeployError as e:
            QMessageBox.warning(self, APP_NAME, str(e))
        except OSError as e:
            QMessageBox.warning(self, APP_NAME, f"{name} failed: {e.strerror or e}")
        return None

    def _after_game_change(self, message: str) -> None:
        self.reload()
        self.statusBar().showMessage(message)

    def _changes_made(self) -> None:
        self._update_changes()
        self.show_team(self.team_id)

    def _update_changes(self) -> None:
        """menu, status bar and banner follow the staging area and the game"""
        open_game = self.game_dir is not None
        waiting = len(self.staging.changes)
        self.deploy_action.setEnabled(open_game and waiting > 0)
        self.discard_action.setEnabled(waiting > 0)
        self.undo_action.setEnabled(open_game and bool(deploy.history(settings.home())))
        self.relink_action.setEnabled(open_game)
        self.import_folder_action.setEnabled(open_game)
        self.import_zip_action.setEnabled(open_game)
        self.pending_label.setText(f"{_kits(waiting)} waiting for Deploy")
        self.pending_label.setVisible(waiting > 0)
        state = deploy.status(self.game_dir) if open_game else deploy.Status(False, False)
        lost = [name for name, gone in (("map.txt", state.block_lost), ("sider.ini", state.root_lost)) if gone]
        self.links_text.setText(
            f"{' and '.join(lost)} no longer point{'s' if len(lost) == 1 else ''} to the kits installed by "
            f"{APP_NAME} (another tool, like a Mod Studio Build, rewrote {'it' if len(lost) == 1 else 'them'})."
        )
        self.links_banner.setVisible(bool(lost))

    def _ask(self, question: str) -> bool:
        return QMessageBox.question(self, APP_NAME, question) == QMessageBox.Yes

    # --- settings ----------------------------------------------------------------------------------------------------

    def set_text_size(self, size: int | None) -> None:
        """text size in points for the whole app; None = the system's"""
        _apply_text_size(size)
        self._save(font_size=size)

    def _step_text(self, step: int) -> None:
        current = self.settings.font_size or _system_font().pointSize()
        sizes = settings.FONT_SIZES
        self.set_text_size(max(sizes[0], min(sizes[-1], current + step)))

    def _view_changed(self, view: str) -> None:
        self._save(view=view)

    def _save(self, **changes) -> None:
        self.settings = dataclasses.replace(self.settings, **changes)
        settings.save(self.settings)
