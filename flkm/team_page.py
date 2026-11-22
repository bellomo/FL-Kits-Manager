"""The team page: the team's name and details, and its kits folded or unrolled."""

import os
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QEvent, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from flkm import render
from flkm.catalog import Team
from flkm.game.kits import slot_name

UNROLLED = 320  # size of an unrolled kit on the page
TITLE_EXTRA = 6  # the team name is this many points larger than the text
COLUMNS = {"folded": 2, "unrolled": 3}
PENDING_COLOUR = "#d9822b"  # kits waiting for Deploy


def to_pixmap(img: Image.Image) -> QPixmap:
    rgb = img.convert("RGB")
    data = rgb.tobytes()
    return QPixmap.fromImage(QImage(data, rgb.width, rgb.height, 3 * rgb.width, QImage.Format_RGB888).copy())


def kit_picture(kit, view: str) -> Image.Image:
    if view == "folded":
        out = render.folded(kit.picture(1024))
        return out.resize((out.width // 2, out.height // 2), Image.LANCZOS)
    return render.unrolled(kit.picture(512), UNROLLED)


class KitCard(QWidget):
    """one kit; `pending` = a kit waiting for Deploy, `added` = a kit the team does not have yet (from a pack)"""

    def __init__(
        self,
        kit,
        view: str,
        pending: bool = False,
        added: bool = False,
        text: str | None = None,
        parent: QWidget | None = None,
    ):
        """text: where the kit is (default: kit.source)"""
        super().__init__(parent)
        self.kit, self.pending = kit, pending
        self.name = QLabel(slot_name(kit.slot) + (" · new" if pending else ""))
        bold = QFont()
        bold.setBold(True)
        self.name.setFont(bold)
        if pending:
            self.name.setStyleSheet(f"color: {PENDING_COLOUR}")
        self.picture = QLabel(alignment=Qt.AlignCenter)
        self.source = QLabel(kit.source if text is None else text)
        self.source.setStyleSheet(f"color: {PENDING_COLOUR if pending else 'gray'}")
        self.source.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.source.setWordWrap(True)
        self.replace_button = QPushButton("Replace…")
        self.replace_button.setToolTip(
            "Choose an .ftex, .png or .dds texture to use for this kit (installed by Deploy)"
        )
        self.replace_button.setVisible(not added)  # a texture needs a kit to go into
        self.discard_button = QPushButton("Don't add this kit" if added else "Keep the current kit")
        self.discard_button.setVisible(pending)
        buttons = QHBoxLayout()
        buttons.addWidget(self.replace_button)
        buttons.addWidget(self.discard_button)
        buttons.addStretch()
        layout = QVBoxLayout(self)
        for w in (self.name, self.picture, self.source):
            layout.addWidget(w)
        layout.addLayout(buttons)
        self.draw(view)

    def draw(self, view: str) -> None:
        try:
            self.picture.setPixmap(to_pixmap(kit_picture(self.kit, view)))
        except (ValueError, OSError) as e:  # damaged texture or archive
            self.picture.setText(f"Cannot read this kit: {e}")


class TeamPage(QWidget):
    view_changed = Signal(str)
    replace_requested = Signal(str)  # slot
    discard_requested = Signal(str)  # slot

    def __init__(self, view: str = "folded", parent: QWidget | None = None):
        super().__init__(parent)
        self.view = view
        self.cards: list[KitCard] = []
        self.title = QLabel()
        self._title_font()
        self.details = QLabel()
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.folded_button = QPushButton("Folded", checkable=True)
        self.unrolled_button = QPushButton("Unrolled", checkable=True)
        group = QButtonGroup(self)
        for b in (self.folded_button, self.unrolled_button):
            group.addButton(b)
        (self.folded_button if view == "folded" else self.unrolled_button).setChecked(True)
        self.folded_button.clicked.connect(lambda: self.set_view("folded"))
        self.unrolled_button.clicked.connect(lambda: self.set_view("unrolled"))
        self.folder: Path | None = None
        self.folder_label = QLabel()
        self.folder_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.folder_label.setStyleSheet("color: gray")
        self.folder_label.setSizePolicy(
            QSizePolicy.Ignored, QSizePolicy.Preferred
        )  # a long path does not widen the page
        self.open_folder_button = QPushButton("Open folder")
        self.open_folder_button.setToolTip("Open the folder of the team's kits in Explorer")
        self.open_folder_button.clicked.connect(self.open_folder)
        self.folder_row = QWidget()
        row = QHBoxLayout(self.folder_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("Kits in:"))
        row.addWidget(self.folder_label, 1)
        row.addWidget(self.open_folder_button)
        self.folder_row.setVisible(False)
        self.empty = QLabel("No kits found for this team.")
        self.grid = QGridLayout()
        grid_widget = QWidget()
        grid_widget.setLayout(self.grid)
        scroll = QScrollArea(widgetResizable=True)
        scroll.setWidget(grid_widget)

        header = QHBoxLayout()
        names = QVBoxLayout()
        names.addWidget(self.title)
        names.addWidget(self.details)
        header.addLayout(names, 1)
        header.addWidget(self.folded_button)
        header.addWidget(self.unrolled_button)
        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(self.folder_row)
        layout.addWidget(self.empty)
        layout.addWidget(scroll, 1)

    def _title_font(self) -> None:
        big = QFont(self.font())
        big.setPointSize(self.font().pointSize() + TITLE_EXTRA)
        big.setBold(True)
        self.title.setFont(big)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802 (Qt name)
        if event.type() == QEvent.FontChange:  # the user changed the text size
            self._title_font()
        super().changeEvent(event)

    def show_team(self, team: Team, kits: list, pending: dict | None = None) -> None:
        """kits: the team's kits; pending: slot -> kit waiting for Deploy, shown instead of the current one"""
        pending = pending or {}
        self.title.setText(team.name)
        self.details.setText(
            " · ".join(str(v) for v in (f"id {team.id}", team.abbr, team.league, team.country, team.federation) if v)
        )
        for card in self.cards:
            card.setParent(None)
            card.deleteLater()
        have = {k.slot for k in kits}
        try:
            self.folder = Path(os.path.commonpath([k.folder for k in kits])) if kits else None
        except ValueError:  # on different drives
            self.folder = None
        self.folder_label.setText(str(self.folder or ""))
        self.folder_label.setToolTip(str(self.folder or ""))
        self.folder_row.setVisible(self.folder is not None)

        def card(k) -> KitCard:
            if k.slot in pending:
                return KitCard(pending[k.slot], self.view, pending=True)
            path = k.folder / k.file_name
            c = KitCard(k, self.view, text=str(path.relative_to(self.folder) if self.folder else path))
            c.source.setToolTip(str(path))
            return c

        self.cards = [card(k) for k in kits]
        self.cards += [KitCard(pending[s], self.view, pending=True, added=True) for s in pending if s not in have]
        self.cards.sort(key=lambda c: (c.kit.slot[0] == "g", int(c.kit.slot[1:])))  # players first, then goalkeepers
        for card in self.cards:
            slot = card.kit.slot
            card.replace_button.clicked.connect(lambda _=False, s=slot: self.replace_requested.emit(s))
            card.discard_button.clicked.connect(lambda _=False, s=slot: self.discard_requested.emit(s))
        self._place()
        self.empty.setVisible(not self.cards)

    def open_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.folder)))

    def _place(self) -> None:
        columns = COLUMNS[self.view]
        for i, card in enumerate(self.cards):
            self.grid.addWidget(card, i // columns, i % columns, Qt.AlignTop | Qt.AlignLeft)

    def set_view(self, view: str) -> None:
        self.view = view
        for card in self.cards:
            self.grid.removeWidget(card)
            card.draw(view)
        self._place()
        self.view_changed.emit(view)
