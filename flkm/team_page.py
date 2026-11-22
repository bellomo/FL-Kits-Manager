"""The team page: the team's name and details, and its kits folded or unrolled."""

from PIL import Image
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QImage, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from flkm import render
from flkm.catalog import Team

UNROLLED = 320  # size of an unrolled kit on the page
COLUMNS = {"folded": 2, "unrolled": 3}
_NAMES = {"p1": "Home", "p2": "Away", "p3": "Third", "g1": "Goalkeeper"}


def slot_name(slot: str) -> str:
    if slot in _NAMES:
        return _NAMES[slot]
    return f"{'Goalkeeper' if slot[0] == 'g' else 'Kit'} {slot[1:]}"


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
    def __init__(self, kit, view: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.kit = kit
        self.name = QLabel(slot_name(kit.slot))
        bold = QFont()
        bold.setBold(True)
        self.name.setFont(bold)
        self.picture = QLabel(alignment=Qt.AlignCenter)
        self.source = QLabel(kit.source)
        self.source.setStyleSheet("color: gray")
        self.source.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout = QVBoxLayout(self)
        for w in (self.name, self.picture, self.source):
            layout.addWidget(w)
        self.draw(view)

    def draw(self, view: str) -> None:
        try:
            self.picture.setPixmap(to_pixmap(kit_picture(self.kit, view)))
        except (ValueError, OSError) as e:  # damaged texture or archive
            self.picture.setText(f"Cannot read this kit: {e}")


class TeamPage(QWidget):
    view_changed = Signal(str)

    def __init__(self, view: str = "folded", parent: QWidget | None = None):
        super().__init__(parent)
        self.view = view
        self.cards: list[KitCard] = []
        self.title = QLabel()
        big = QFont()
        big.setPointSize(16)
        big.setBold(True)
        self.title.setFont(big)
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
        layout.addWidget(self.empty)
        layout.addWidget(scroll, 1)

    def show_team(self, team: Team, kits: list) -> None:
        self.title.setText(team.name)
        self.details.setText(
            " · ".join(str(v) for v in (f"id {team.id}", team.abbr, team.league, team.country, team.federation) if v)
        )
        for card in self.cards:
            card.setParent(None)
            card.deleteLater()
        self.cards = [KitCard(k, self.view) for k in kits]
        self._place()
        self.empty.setVisible(not kits)

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
