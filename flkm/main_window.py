"""Main window: the team list on the left, the page of the chosen team on the right."""

import dataclasses
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
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
from flkm import catalog, settings
from flkm.team_page import TeamPage
from flkm.team_tree import TeamTree

APP_NAME = "FL Kits Manager"
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


class MainWindow(QMainWindow):
    def __init__(self, game_dir: Path | None = None):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {flkm.__version__}")
        self.setMinimumSize(1000, 650)
        self.settings = settings.load()
        self.catalog: catalog.Catalog | None = None
        self.game_dir: Path | None = None
        self.team_id: int | None = None  # the team whose page is open

        self.tree = TeamTree()
        self.page = TeamPage(view=self.settings.view)
        self.start = QWidget()
        self.start_text = QLabel("Choose the folder of SP Football Life 2027 to see its teams and kits.")
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
        splitter = QSplitter()
        splitter.addWidget(self.tree)
        splitter.addWidget(self.pages)
        splitter.setSizes([320, 880])
        self.setCentralWidget(splitter)

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
        self.larger_text_action.triggered.connect(lambda: self._step_text(+1))
        self.smaller_text_action.triggered.connect(lambda: self._step_text(-1))
        self.default_text_action.triggered.connect(lambda: self.set_text_size(None))
        _apply_text_size(self.settings.font_size)

        self.choose_button.clicked.connect(self.choose_game)
        self.game_action.triggered.connect(self.choose_game)
        self.quit_action.triggered.connect(self.close)
        self.reload_action.triggered.connect(self.reload)
        self.tree.team_selected.connect(self.show_team)
        self.page.view_changed.connect(self._view_changed)

        if game_dir is not None:
            self.open_game(Path(game_dir))
        elif self.settings.game_dir and settings.is_game_dir(Path(self.settings.game_dir)):
            self.open_game(Path(self.settings.game_dir))

    def choose_game(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Folder of SP Football Life 2027", self.settings.game_dir or "")
        if folder:
            self.open_game(Path(folder))

    def open_game(self, game_dir: Path) -> None:
        if not settings.is_game_dir(game_dir):
            QMessageBox.warning(
                self,
                APP_NAME,
                f"{game_dir} is not the SP Football Life 2027 folder: SiderAddons\\sider.ini is missing.",
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

    def reload(self) -> None:
        """reads the game again, keeping the search and the open team"""
        team_id = self.team_id
        self.open_game(self.game_dir)
        if team_id is not None and self.catalog.get(team_id) and not self.tree.select_team(team_id):
            self.show_team(team_id)  # the search hides it

    def show_team(self, team_id: int) -> None:
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.page.show_team(self.catalog.get(team_id), self.catalog.kits(team_id))
        finally:
            QGuiApplication.restoreOverrideCursor()
        self.team_id = team_id
        self.pages.setCurrentWidget(self.page)

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
