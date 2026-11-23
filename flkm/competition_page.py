"""The competition page: name and details, and the three variants of its logo, each on a light and a dark background
(as the game's menus show them), with Replace… for one variant and Replace logo… for all three."""

from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from flkm.catalog import Competition
from flkm.team_page import PENDING_COLOUR, TITLE_EXTRA, folder_row, open_folder, show_folder, to_pixmap

LOGO_SIZE = 160  # each logo picture on the page
LIGHT, DARK = (240, 240, 240, 255), (32, 32, 32, 255)
NAMES = {"": "Normal", "b": "Dark (for light backgrounds)", "w": "White (for dark backgrounds)"}


def _on(image: Image.Image, background: tuple) -> Image.Image:
    logo = image.convert("RGBA")
    logo.thumbnail((LOGO_SIZE, LOGO_SIZE), Image.LANCZOS)
    out = Image.new("RGBA", (LOGO_SIZE, LOGO_SIZE), background)
    out.alpha_composite(logo, ((LOGO_SIZE - logo.width) // 2, (LOGO_SIZE - logo.height) // 2))
    return out


class VariantCard(QWidget):
    def __init__(self, variant: str, image: Image.Image | None, text: str, pending: bool):
        super().__init__()
        self.variant = variant
        self.name = QLabel(NAMES[variant] + (" · new" if pending else ""))
        bold = QFont()
        bold.setBold(True)
        self.name.setFont(bold)
        self.light, self.dark = QLabel(alignment=Qt.AlignCenter), QLabel(alignment=Qt.AlignCenter)
        for label, background in ((self.light, LIGHT), (self.dark, DARK)):
            label.setFixedSize(LOGO_SIZE, LOGO_SIZE)
            if image is None:
                label.setText("No logo")
            else:
                label.setPixmap(to_pixmap(_on(image, background)))
        self.source = QLabel(text)
        self.source.setStyleSheet(f"color: {PENDING_COLOUR if pending else 'gray'}")
        self.source.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.source.setWordWrap(True)
        self.replace_button = QPushButton("Replace…")
        self.replace_button.setToolTip("Choose a picture for this variant only (installed by Deploy)")
        pictures = QHBoxLayout()
        pictures.addWidget(self.light)
        pictures.addWidget(self.dark)
        pictures.addStretch()
        layout = QVBoxLayout(self)
        layout.addWidget(self.name)
        layout.addLayout(pictures)
        layout.addWidget(self.source)
        layout.addWidget(self.replace_button, 0, Qt.AlignLeft)


class CompetitionPage(QWidget):
    replace_requested = Signal(str)  # "all" or a variant ("", "b", "w")
    discard_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.cards: list[VariantCard] = []
        self.title = QLabel()
        big = QFont(self.font())
        big.setPointSize(self.font().pointSize() + TITLE_EXTRA)
        big.setBold(True)
        self.title.setFont(big)
        self.details = QLabel()
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.replace_all_button = QPushButton("Replace logo…")
        self.replace_all_button.setToolTip("Choose one picture for all three variants (installed by Deploy)")
        self.keep_button = QPushButton("Keep the current logo")
        self.keep_button.setToolTip("Drop the new logo waiting for Deploy: the game keeps the logo it has")
        self.keep_button.setVisible(False)
        self.replace_all_button.clicked.connect(lambda: self.replace_requested.emit("all"))
        self.keep_button.clicked.connect(self.discard_requested)
        self.folder: Path | None = None
        self.folder_row, self.folder_label, self.open_folder_button = folder_row("Logo", "competition's logo")
        self.open_folder_button.clicked.connect(lambda: open_folder(self.folder))
        self.grid = QGridLayout()
        buttons = QHBoxLayout()
        buttons.addWidget(self.replace_all_button)
        buttons.addWidget(self.keep_button)
        buttons.addStretch()
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.details)
        layout.addLayout(buttons)
        layout.addWidget(self.folder_row)
        layout.addLayout(self.grid)
        layout.addStretch()

    def show_competition(
        self, comp: Competition, variants: dict, pending: bool = False, folder: Path | None = None
    ) -> None:
        """variants: variant -> (picture or None, where it is in `folder` or a note, waiting for Deploy); pending: the
        logo has changes; folder: the folder of its files in the game, shown once above the variants"""
        self.folder = folder
        show_folder(self.folder_row, self.folder_label, folder)
        self.title.setText(comp.name)
        self.details.setText(" · ".join(v for v in (f"id {comp.id}", comp.code, comp.country, comp.federation) if v))
        for card in self.cards:
            card.setParent(None)
            card.deleteLater()
        self.cards = [VariantCard(v, *variants[v]) for v in NAMES]
        for i, card in enumerate(self.cards):
            card.replace_button.clicked.connect(lambda _=False, v=card.variant: self.replace_requested.emit(v))
            self.grid.addWidget(card, 0, i, Qt.AlignTop | Qt.AlignLeft)
        self.keep_button.setVisible(pending)
