"""Main window: the team list on the left, the page of the chosen team on the right.

Kits chosen with Replace… (a texture), made with Kits from photos… or brought by Changes > Import kit pack (whole
kits), and crests chosen with Replace crest…, wait in the staging area (shown on the team page) until Changes > Deploy
installs them; Changes > Undo last deploy puts back what the last deploy changed.
"""

import dataclasses
import functools
import io
from collections.abc import Callable
from pathlib import Path

from PIL import Image
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import flkm
from flkm import catalog, claude, deploy, logo_pack, pack, settings
from flkm.competition_page import CompetitionPage
from flkm.competition_tree import CompetitionTree
from flkm.game import ftex, kits, logos, process
from flkm.history_dialog import DeployHistoryDialog, describe
from flkm.import_dialog import ImportDialog
from flkm.logo_import_dialog import LogoImportDialog
from flkm.photo_kit_dialog import PhotoKitDialog, run_in_thread
from flkm.photokit.maker import makers_folder
from flkm.photokit import team as photo_team
from flkm.staging import Staging
from flkm.team_page import PENDING_COLOUR, TeamPage, common_folder, kit_picture, slot_name
from flkm.team_tree import TeamTree

APP_NAME = "FL Kits Manager"
GAME_NAME = "SP Football Life 2027"
PICTURES = "Pictures (*.png *.dds *.jpg *.jpeg *.webp)"
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


def _installed() -> list:
    """the deploys still installed, newest first"""
    return [d for d in deploy.history(settings.home()) if not d.undone]


def _waiting(changes: list) -> str:
    logo_count = sum(c.kind == "logo" for c in changes)
    return _count(len(changes) - logo_count, logo_count)


def _count(kit_count: int, logo_count: int) -> str:
    """'2 kits', '1 logo', '1 kit and 2 logos'"""
    parts = [_kits(kit_count)] if kit_count or not logo_count else []
    if logo_count:
        parts.append(f"{logo_count} logo" + ("" if logo_count == 1 else "s"))
    return " and ".join(parts)


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
        self.comp_id: int | None = None  # the competition whose page is open

        self.tree = TeamTree()
        self.comp_tree = CompetitionTree()
        self.sides = QTabWidget()
        self.sides.addTab(self.tree, "Teams")
        self.sides.addTab(self.comp_tree, "Competitions")
        self.page = TeamPage(view=self.settings.view)
        self.comp_page = CompetitionPage()
        self.start = QWidget()
        self.start_text = QLabel(f"Choose the folder of {GAME_NAME} to see its teams and kits.")
        self.start_text.setAlignment(Qt.AlignCenter)
        self.choose_button = QPushButton("Choose the game folder…")
        self.choose_button.setToolTip("Choose the folder where SP Football Life 2027 is installed")
        start_layout = QVBoxLayout(self.start)
        start_layout.addStretch()
        start_layout.addWidget(self.start_text)
        start_layout.addWidget(self.choose_button, 0, Qt.AlignCenter)
        start_layout.addStretch()
        self.pages = QStackedWidget()
        self.pages.addWidget(self.start)
        self.pages.addWidget(self.page)
        self.pages.addWidget(self.comp_page)

        self.links_banner = QWidget()  # shown when another tool removed the app's links to its kits
        self.links_banner.setStyleSheet(f"background: {PENDING_COLOUR}; color: white")
        self.links_text = QLabel()
        self.links_text.setWordWrap(True)
        self.relink_button = QPushButton("Re-apply")
        self.relink_button.setToolTip("Write again the links to the deployed kits that another tool removed")
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
        splitter.addWidget(self.sides)
        splitter.addWidget(right)
        splitter.setSizes([320, 880])
        self.setCentralWidget(splitter)
        self.pending_label = QLabel()
        self.pending_label.setStyleSheet(f"color: {PENDING_COLOUR}; font-weight: bold")
        self.statusBar().addPermanentWidget(self.pending_label)
        self.claude: claude.Cli | None = None
        self.claude_label = QLabel()
        self.statusBar().addPermanentWidget(self.claude_label)

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
        self.import_folder_action = QAction("Import kits and logos (&folder)…", self, enabled=False)
        self.import_zip_action = QAction("Import kits and logos (&zip)…", self, enabled=False)
        for action in (self.import_folder_action, self.import_zip_action):
            action.setStatusTip("Take whole kits from a kit pack (kitserver team folders); they wait for Deploy")
            changes.addAction(action)
        changes.addSeparator()
        self.deploy_action = QAction("&Deploy to the game", self, shortcut=QKeySequence("Ctrl+D"))
        self.deploy_action.setStatusTip("Install the kits waiting for Deploy (the game must be closed)")
        self.discard_action = QAction("Dis&card all changes", self)
        self.undo_action = QAction("&Undo last deploy", self)
        self.undo_action.setStatusTip("Put back the files the last deploy changed")
        self.history_action = QAction("Deploy &history…", self)
        self.history_action.setStatusTip(
            "Every deploy: go back to before one, re-apply an undone one, clear the history"
        )
        self.relink_action = QAction("&Re-apply links to the app's kits", self)
        self.relink_action.setStatusTip("Write again the app's lines in map.txt and its root in sider.ini")
        for action in (self.deploy_action, self.discard_action, self.undo_action, self.history_action):
            changes.addAction(action)
        changes.addSeparator()
        changes.addAction(self.relink_action)
        claude_menu = self.menuBar().addMenu("C&laude")
        self.choose_claude_action = QAction("&Choose Claude Code…", self)
        self.choose_claude_action.setStatusTip(
            "Choose the claude program (claude.exe) the app uses for its Claude features"
        )
        self.find_claude_action = QAction("&Look for Claude Code again", self)
        self.find_claude_action.setStatusTip("Forget the program chosen and look for Claude Code where it is installed")
        claude_menu.addAction(self.choose_claude_action)
        claude_menu.addAction(self.find_claude_action)
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
        self.history_action.triggered.connect(self.show_history)
        self.relink_action.triggered.connect(self.relink)
        self.choose_claude_action.triggered.connect(self.choose_claude)
        self.find_claude_action.triggered.connect(lambda: self.find_claude(forget=True))
        self.relink_button.clicked.connect(self.relink)
        self.tree.team_selected.connect(self.show_team)
        self.page.view_changed.connect(self._view_changed)
        self.page.replace_requested.connect(self.replace_kit)
        self.page.discard_requested.connect(self.keep_kit)
        self.page.crest_replace_requested.connect(self.replace_crest)
        self.page.crest_discard_requested.connect(self.keep_crest)
        self.page.photos_requested.connect(self.kits_from_photos)
        self.comp_tree.competition_selected.connect(self.show_competition)
        self.comp_page.replace_requested.connect(self.replace_logo)
        self.comp_page.discard_requested.connect(self.keep_logo)

        self.find_claude()
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
        self.game_dir, self.team_id, self.comp_id = game_dir, None, None
        self.tree.set_catalog(self.catalog)
        self.comp_tree.set_catalog(self.catalog)
        self.start_text.setText("Choose a team on the left.")
        self.choose_button.hide()
        self.pages.setCurrentWidget(self.start)
        self.reload_action.setEnabled(True)
        self.statusBar().showMessage(f"{len(self.catalog.teams)} teams · {game_dir}")
        self._save(game_dir=str(game_dir))
        self._update_changes()

    def reload(self) -> None:
        """reads the game again, keeping the search and the open team"""
        team_id, comp_id = self.team_id, self.comp_id
        on_comp = self.pages.currentWidget() is self.comp_page
        self.open_game(self.game_dir)
        if on_comp:
            if self.catalog.competition(comp_id) and not self.comp_tree.select(comp_id):
                self.show_competition(comp_id)  # the search hides it
        elif team_id is not None and self.catalog.get(team_id) and not self.tree.select_team(team_id):
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
        self._show_crest(team_id)
        self.team_id = team_id
        self.pages.setCurrentWidget(self.page)

    def _staged_crest(self, team_id: int) -> Image.Image | None:
        """the team's new crest waiting for Deploy, or None"""
        staged = self.staging.logo("crest", team_id)
        if not staged:
            return None
        return Image.open(io.BytesIO(self.staging.logo_files(staged)[logos.crest_files(team_id)[512]]))

    def _show_crest(self, team_id: int) -> None:
        staged = self.staging.logo("crest", team_id)
        if staged:
            image = self._staged_crest(team_id)
            self.page.show_crest(image, f"New crest, not deployed yet: {Path(staged.source).name}", pending=True)
            self.page.crest_source.setToolTip(staged.source)
            return
        found = logos.find_crest(self.catalog.files, team_id)
        if found is None:
            self.page.show_crest(None, "No crest in the game files")
        else:
            self.page.show_crest(logos.picture(found), found.file_name, folder=found.folder)
        self.page.crest_source.setToolTip("")

    def replace_crest(self) -> None:
        team = self.catalog.get(self.team_id)
        path, _ = QFileDialog.getOpenFileName(self, f"New crest for {team.name}", "", PICTURES)
        if not path:
            return
        try:
            files = logos.make_crest(logos.load(Path(path)), team.id)
        except logos.LogoError as e:
            QMessageBox.warning(self, APP_NAME, str(e))
            return
        self.staging.add_logo(team.id, team.name, "crest", files, path)
        self._changes_made()

    def keep_crest(self) -> None:
        self.staging.remove(self.team_id, "crest")
        self._changes_made()

    # --- competitions ------------------------------------------------------------------------------------------------

    def show_competition(self, comp_id: int) -> None:
        staged = self.staging.logo("emblem", comp_id)
        files = self.staging.logo_files(staged) if staged else {}
        names = logos.emblem_files(comp_id)
        variants, tips, found = {}, {}, {}
        for v in logos.VARIANTS:
            new = files.get(names[(v, 512)])
            if new is not None:
                source = self._logo_sources(staged).get(v, staged.source)
                variants[v] = (Image.open(io.BytesIO(new)), f"New logo, not deployed yet: {Path(source).name}", True)
                tips[v] = source
            elif (f := logos.find_emblem(self.catalog.files, comp_id, v)) is None:
                variants[v] = (None, "Not in the game files", False)
            else:
                found[v] = f
        folder = common_folder([f.folder for f in found.values()])
        for v, f in found.items():
            path = f.folder / f.file_name
            variants[v] = (logos.picture(f), str(path.relative_to(folder) if folder else path), False)
            tips[v] = str(path)
        self.comp_page.show_competition(
            self.catalog.competition(comp_id), variants, pending=staged is not None, folder=folder
        )
        for card in self.comp_page.cards:
            card.source.setToolTip(tips.get(card.variant, ""))
        self.comp_id = comp_id
        self.pages.setCurrentWidget(self.comp_page)

    def _logo_sources(self, change) -> dict[str, str]:
        """variant -> the picture it was made from (kept in the change's source as variant=path lines)"""
        return dict(line.split("=", 1) for line in change.source.splitlines() if "=" in line)

    def replace_logo(self, which: str) -> None:
        comp = self.catalog.competition(self.comp_id)
        what = "logo" if which == "all" else f"{logos.VARIANTS[which].lower()} logo"
        path, _ = QFileDialog.getOpenFileName(self, f"New {what} for {comp.name}", "", PICTURES)
        if not path:
            return
        try:
            image = logos.load(Path(path))
        except logos.LogoError as e:
            QMessageBox.warning(self, APP_NAME, str(e))
            return
        chosen = list(logos.VARIANTS) if which == "all" else [which]
        old = self.staging.logo("emblem", comp.id)
        sources = self._logo_sources(old) if old else {}
        sources.update({v: path for v in chosen})
        files = logos.make_emblem({v: image for v in chosen}, comp.id)
        source = "\n".join(f"{v}={p}" for v, p in sorted(sources.items()))
        self.staging.add_logo(comp.id, comp.name, "emblem", files, source)
        self._changes_made()

    def keep_logo(self) -> None:
        self.staging.remove(self.comp_id, "emblem")
        self._changes_made()

    # --- changes -----------------------------------------------------------------------------------------------------

    def import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Folder of a kit or logo pack", "")
        if folder:
            self.import_pack(Path(folder))

    def import_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Kit or logo pack", "", "Zip files (*.zip)")
        if path:
            self.import_pack(Path(path))

    def import_pack(self, source: Path) -> None:
        """matches the pack's team folders with the game's teams, and its logos with the teams and competitions; the
        kits and logos the user confirms wait for Deploy"""
        try:
            kit_pack = pack.open_pack(source)
        except pack.PackError as e:
            QMessageBox.warning(self, APP_NAME, str(e))
            return
        found = logo_pack.find(kit_pack, self.catalog.teams, self.catalog.competitions)
        if not kit_pack.teams and not found:
            QMessageBox.information(
                self,
                APP_NAME,
                f"No kitserver team folders (with kit folders like p1, g1) or logos found in {source.name}.",
            )
            return
        kits_added = self._import_kits(source, kit_pack) if kit_pack.teams else None
        logos_added = self._import_logos(source, kit_pack, found) if found else None
        if kits_added is None and logos_added is None:  # every dialog cancelled
            return
        self._update_changes()
        if self.pages.currentWidget() is self.comp_page:
            self.show_competition(self.comp_id)
        elif self.team_id is not None:
            self.show_team(self.team_id)
        self.statusBar().showMessage(
            f"{_count(kits_added or 0, logos_added or 0)} from {source.name} waiting for Deploy."
        )

    def _import_logos(self, source: Path, kit_pack: pack.Pack, found: list) -> int | None:
        """the logos the user confirms are staged; None if the dialog is cancelled"""
        dialog = LogoImportDialog(
            source.name, found, self.catalog.search, self.catalog.search_competitions, kit_pack.read, self
        )
        if dialog.exec() != QDialog.Accepted:
            return None
        made, failed = logo_pack.logos_of(kit_pack, dialog.chosen(), source.name)
        for logo in made:
            self.staging.add_logo(logo.owner, logo.name, logo.slot, logo.files, logo.source)
        if failed:
            QMessageBox.warning(self, APP_NAME, "Some logos were not added:\n" + "\n".join(failed[:20]))
        return len(made)

    def _import_kits(self, source: Path, kit_pack: pack.Pack) -> int | None:
        """the kits the user confirms are staged; None if the dialog is cancelled"""
        matches = pack.match(kit_pack.teams, self.catalog.teams)
        dialog = ImportDialog(source.name, matches, self.catalog.search, self)
        if dialog.exec() != QDialog.Accepted:
            return None
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
        return added

    def replace_kit(self, slot: str) -> None:
        team = self.catalog.get(self.team_id)
        path, _ = QFileDialog.getOpenFileName(
            self, f"New {slot_name(slot)} kit for {team.name}", "", "Kit textures (*.ftex *.png *.dds)"
        )
        if not path:
            return
        try:
            kit = next((k for k in self.catalog.kits(team.id) if k.slot == slot), None)
            header = kit.texture().data[:0x40] if kit else None  # an image takes the header of the kit it replaces
            self.staging.add(team.id, team.name, slot, Path(path), header)
        except (ftex.FtexError, ValueError, OSError) as e:
            QMessageBox.warning(self, APP_NAME, f"{path} cannot be used for this kit: {e}")
            return
        self._changes_made()

    def kits_from_photos(self) -> None:
        """The Kits from photos dialog; its kits are staged like Replace… does. Each team has its work folder (the
        photos chosen, the logos cut from them, the textures): the dialog opens with the photos chosen last time."""
        team = self.catalog.get(self.team_id)
        work = settings.home() / "photokits" / str(team.id)
        work.mkdir(parents=True, exist_ok=True)
        ref = work / "ref"
        chosen, _ = photo_team.place_photos(photo_team.photos_in_folder(ref) if ref.is_dir() else [], {})
        game_kits = {k.slot: k for k in self.catalog.kits(team.id) if k.slot in photo_team.SLOTS.values()}
        current = {slot: functools.partial(kit_picture, kit) for slot, kit in game_kits.items()}  # view -> picture
        files, crest = self.catalog.files, self._staged_crest(team.id)

        def make(photos: dict, tones: dict):
            photo_team.copy_photos(photo_team.chosen_to_photos(photos), work)
            return photo_team.make_team(files, team.id, work, makers_folder(), crest=crest, tones=tones)

        tones = photo_team.saved_tones(work)
        made = photo_team.made_before(work)
        dialog = PhotoKitDialog(
            team.name, work, make, current, chosen, tones, parent=self, view=self.page.view, made=made
        )
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            photo_team.stage_textures(self.staging, team.id, team.name, dialog.made, game_kits)
        except (ftex.FtexError, ValueError, OSError) as e:
            QMessageBox.warning(self, APP_NAME, f"The kits from the photos cannot be used: {e}")
        self._changes_made()

    def keep_kit(self, slot: str) -> None:
        self.staging.remove(self.team_id, slot)
        self._changes_made()

    def discard_changes(self) -> None:
        if self._ask(f"Discard {_waiting(self.staging.changes)} waiting for Deploy?"):
            self.staging.clear()
            self._changes_made()

    def deploy_changes(self) -> None:
        changes = self.staging.changes
        listing = "\n".join(
            f"{c.team_name}: {slot_name(c.slot)}{' (whole kit)' if c.kind == 'kit' else ''}" for c in changes
        )
        what = _waiting(changes)
        question = (
            f"Install {what} in the game?\n\n{listing}\n\n"
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
            self._after_game_change(f"Deployed {what}. Restart the game to see {them}.")

    def undo_deploy(self) -> None:
        last = _installed()[0]
        what = _count(last.changes - last.logos, last.logos) if last.changes else "re-applied links"
        if not self._ask(f"Undo the last deploy ({what})? The files it changed are put back as they were."):
            return
        if self._undo(None):
            self._after_game_change("Last deploy undone. Restart the game to see the change.")

    def _undo(self, to: str | None) -> list | None:
        """undoes the deploys down to `to`; asks before putting back files another tool changed since"""

        def op(unknown_ok: bool):
            run = functools.partial(deploy.undo, self.game_dir, settings.home(), process.game_running, unknown_ok, to)
            try:
                return run()
            except deploy.FilesChanged as e:
                listing = "\n".join(e.files)
                question = (
                    f"These files changed after the deploy (another tool, like a Mod Studio Build, or by hand):"
                    f"\n\n{listing}\n\nPut them back as they were before the deploy anyway? Those changes would be "
                    "lost."
                )
                return run(force=True) if self._ask(question) else None

        return self._game_op("Undo", op)

    def show_history(self) -> None:
        DeployHistoryDialog(
            lambda: deploy.history(settings.home()), self.go_back, self.reapply_deploy, self.clear_deploys, self
        ).exec()

    def go_back(self, deploy_id: str) -> bool:
        """undoes the deploy and the newer ones still installed (asks first)"""
        if self.game_dir is None:
            QMessageBox.warning(self, APP_NAME, "Choose the game folder first.")
            return False
        installed = _installed()
        chosen = installed[: [d.id for d in installed].index(deploy_id) + 1]
        listing = "\n".join(f"{d.when:%d/%m/%Y %H:%M}  {describe(d)}" for d in chosen)
        n = len(chosen)
        question = (
            f"Undo {'this deploy' if n == 1 else f'these {n} deploys, newest first'}?\n\n{listing}\n\n"
            "The files they changed are put back as they were. Re-apply brings their changes back."
        )
        if not self._ask(question) or not self._undo(deploy_id):
            return False
        self._after_game_change(f"{'Deploy' if n == 1 else f'{n} deploys'} undone. Restart the game to see the change.")
        return True

    def reapply_deploy(self, deploy_id: str) -> bool:
        """the changes of an undone deploy wait for Deploy again"""
        try:
            back = deploy.reapply(settings.home(), deploy_id, self.staging)
        except (deploy.DeployError, OSError) as e:
            QMessageBox.warning(self, APP_NAME, f"Re-apply failed: {e}")
            return False
        self._changes_made()
        self.statusBar().showMessage(f"{_waiting(back)} waiting for Deploy again.")
        return True

    def clear_deploys(self, chosen: set[str]) -> bool:
        """deletes the records of the chosen deploys (and of the older installed ones), after asking"""
        gone = deploy.to_clear(deploy.history(settings.home()), chosen)
        n = len(gone)
        question = (
            f"Delete {'this deploy' if n == 1 else f'these {n} deploys'} from the history? They can no longer be "
            "undone or re-applied; the game files are not touched. This cannot be undone."
        )
        if not self._ask(question):
            return False
        deploy.clear_history(settings.home(), gone)
        self._update_changes()
        self.statusBar().showMessage(f"{'1 deploy' if n == 1 else f'{n} deploys'} deleted from the history.")
        return True

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
        if self.pages.currentWidget() is self.comp_page:
            self.show_competition(self.comp_id)
        else:
            self.show_team(self.team_id)

    def _update_changes(self) -> None:
        """menu, status bar and banner follow the staging area and the game"""
        open_game = self.game_dir is not None
        waiting = len(self.staging.changes)
        self.deploy_action.setEnabled(open_game and waiting > 0)
        self.discard_action.setEnabled(waiting > 0)
        self.undo_action.setEnabled(open_game and bool(_installed()))
        self.history_action.setEnabled(bool(deploy.history(settings.home())))
        self.relink_action.setEnabled(open_game)
        self.import_folder_action.setEnabled(open_game)
        self.import_zip_action.setEnabled(open_game)
        self.pending_label.setText(f"{_waiting(self.staging.changes)} waiting for Deploy")
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

    # --- Claude Code --------------------------------------------------------------------------------------------------

    def find_claude(self, forget: bool = False) -> None:
        """looks for Claude Code in the background (forget: the program chosen before is not tried first)"""
        if forget:
            self._save(claude_path=None)
        self.claude_label.setText("Looking for Claude Code…")
        saved = self.settings.claude_path
        run_in_thread(lambda: claude.find(saved), self._claude_found, lambda message: self._claude_found(None))

    def _claude_found(self, cli: claude.Cli | None) -> None:
        self.claude = cli
        self.claude_label.setText(claude.describe(cli))
        if cli:
            self.claude_label.setStyleSheet("")
            self.claude_label.setToolTip(
                f"{cli.path}\nFound: {cli.source}. Used for the Claude features; Claude > Choose Claude Code… to use "
                "another one."
            )
        else:
            self.claude_label.setStyleSheet("color: gray")
            self.claude_label.setToolTip(
                "Claude is optional: without it everything else works. To use the Claude features, install Claude "
                "Code (or the Claude desktop app) and sign in, or choose claude.exe with Claude > Choose Claude Code…"
            )

    def choose_claude(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose Claude Code", "", "Claude Code (claude.exe claude.cmd claude);;All files (*)"
        )
        if not path:
            return
        self.claude_label.setText("Checking Claude Code…")
        run_in_thread(
            lambda: claude.check(path),
            lambda cli: self._claude_chosen(path, cli),
            lambda m: self._claude_chosen(path, None),
        )

    def _claude_chosen(self, path: str, cli: claude.Cli | None) -> None:
        if cli is None:
            self._claude_found(self.claude)  # the one used before stays
            QMessageBox.warning(
                self, APP_NAME, f"{Path(path).name} is not Claude Code: it did not answer `claude --version`."
            )
            return
        self._save(claude_path=str(cli.path))
        self._claude_found(cli)
        self.statusBar().showMessage(f"Using {claude.describe(cli)}: {cli.path}")

    def _save(self, **changes) -> None:
        self.settings = dataclasses.replace(self.settings, **changes)
        settings.save(self.settings)
