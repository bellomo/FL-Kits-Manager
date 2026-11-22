"""Main window: team list on the left, kits of the selected team on the right (filled in from M2)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow

import flkm

APP_NAME = "FL Kits Manager"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {flkm.__version__}")
        self.setMinimumSize(1000, 650)
        placeholder = QLabel("No game folder selected yet.")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(placeholder)
