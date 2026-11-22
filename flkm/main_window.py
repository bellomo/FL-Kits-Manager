"""Main window: the team list on the left, the page of the chosen team on the right."""

import dataclasses
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (
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


class MainWindow(QMainWindow):
    def __init__(self, game_dir: Path | None = None):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {flkm.__version__}")
        self.setMinimumSize(1000, 650)
        self.settings = settings.load()
        self.catalog: catalog.Catalog | None = None

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
        menu.addAction(self.game_action)
        menu.addSeparator()
        menu.addAction(self.quit_action)

        self.choose_button.clicked.connect(self.choose_game)
        self.game_action.triggered.connect(self.choose_game)
        self.quit_action.triggered.connect(self.close)
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
        self.tree.set_catalog(self.catalog)
        self.start_text.setText("Choose a team on the left.")
        self.choose_button.hide()
        self.pages.setCurrentWidget(self.start)
        self.statusBar().showMessage(f"{len(self.catalog.teams)} teams · {game_dir}")
        self._save(game_dir=str(game_dir))

    def show_team(self, team_id: int) -> None:
        QGuiApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.page.show_team(self.catalog.get(team_id), self.catalog.kits(team_id))
        finally:
            QGuiApplication.restoreOverrideCursor()
        self.pages.setCurrentWidget(self.page)

    def _view_changed(self, view: str) -> None:
        self._save(view=view)

    def _save(self, **changes) -> None:
        self.settings = dataclasses.replace(self.settings, **changes)
        settings.save(self.settings)
