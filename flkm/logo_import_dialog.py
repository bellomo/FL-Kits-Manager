"""The logo import dialog: the logos found in a pack (flkm.logo_pack), a small picture of each and the team or
competition it goes to.

Sure ones (named as the game names them, or after a single team or competition) are ticked; the others show why they
need checking. The user can tick them, or choose the team or competition by id or name (Choose… or a double click).
"""

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from flkm import logo_pack
from flkm.catalog import Competition, Team
from flkm.game import logos
from flkm.import_dialog import CHECK_COLOUR
from flkm.logo_pack import LogoFile
from flkm.pack import PackError
from flkm.team_page import to_pixmap

COLUMNS = ("", "Picture", "File in the pack", "Goes to", "How it was matched")
ICON = 40  # the small picture of each logo
NOTE = (
    "A crest is made into the game's three sizes. A competition's logo replaces the variants the pack has (normal, "
    "dark, white); a picture named after the competition is used for all three. Nothing is written to the game "
    "before Deploy."
)


class LogoImportDialog(QDialog):
    def __init__(
        self,
        source_name: str,
        found: list[LogoFile],
        search_teams: Callable[[str], list[Team]],
        search_comps: Callable[[str], list[Competition]],
        read: Callable[[str], bytes],
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Import logos from {source_name}")
        self.resize(1000, 560)
        self.found = list(found)
        self.search_teams, self.search_comps = search_teams, search_comps
        self.summary = QLabel()
        self.table = QTableWidget(len(self.found), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setIconSize(QSize(ICON, ICON))
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(ICON + 6)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        for row, f in enumerate(self.found):
            self.table.setItem(row, 1, self._picture(read, f.path))
            self._fill(row, checked=f.sure and f.owner is not None)
        self.table.itemChanged.connect(lambda _: self._update())
        self.table.cellDoubleClicked.connect(lambda row, _col: self.choose(row))
        note = QLabel(NOTE)
        note.setWordWrap(True)
        note.setStyleSheet("color: gray")
        self.choose_button = QPushButton("Choose…")
        self.choose_button.setToolTip("Choose the team or competition this logo goes to")
        self.choose_button.clicked.connect(self._choose_selected)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText("Add to changes")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        bottom = QHBoxLayout()
        bottom.addWidget(self.choose_button)
        bottom.addStretch()
        bottom.addWidget(self.buttons)
        layout = QVBoxLayout(self)
        layout.addWidget(self.summary)
        layout.addWidget(self.table, 1)
        layout.addWidget(note)
        layout.addLayout(bottom)
        self._update()

    @staticmethod
    def _picture(read: Callable[[str], bytes], path: str) -> QTableWidgetItem:
        try:
            image = logos.read_picture(read(path), path)
        except (logos.LogoError, PackError):
            return QTableWidgetItem("?")
        image.thumbnail((ICON, ICON))
        return QTableWidgetItem(QIcon(to_pixmap(image, alpha=True)), "")

    def _fill(self, row: int, checked: bool) -> None:
        f = self.found[row]
        self.table.blockSignals(True)
        tick = QTableWidgetItem()
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        tick.setFlags(flags | Qt.ItemIsUserCheckable if f.owner is not None else flags)
        tick.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.table.setItem(row, 0, tick)
        texts = (f.path, logo_pack.label(f), f.how + (f": {f.note}" if f.note else ""))
        for col, text in enumerate(texts, start=2):
            item = QTableWidgetItem(text)
            if not f.sure:
                item.setForeground(QColor(CHECK_COLOUR))
            self.table.setItem(row, col, item)
        self.table.blockSignals(False)

    def _update(self) -> None:
        sure = sum(f.sure for f in self.found)
        self.summary.setText(f"{len(self.found)} logos: {sure} sure, {len(self.found) - sure} to check.")
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(self.chosen()))

    def chosen(self) -> list[LogoFile]:
        """the ticked logos"""
        return [
            f
            for row, f in enumerate(self.found)
            if f.owner is not None and self.table.item(row, 0).checkState() == Qt.Checked
        ]

    def _set(self, row: int, f: LogoFile) -> None:
        self.found[row] = f
        self._fill(row, checked=True)
        self._update()

    def _choose_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.choose(rows[0].row())

    def choose(self, row: int) -> None:
        f = self.found[row]
        name = f.path.rsplit("/", 1)[-1]
        title = "Choose team or competition"
        text, ok = QInputDialog.getText(self, title, f"Team or competition for “{name}” (id or name):")
        if not ok or not text.strip():
            return
        options = [(f"Crest of {t.name} (id {t.id})", logo_pack.to_team(f, t)) for t in self.search_teams(text)]
        options += [(f"{c.name} logo (id {c.id})", logo_pack.to_competition(f, c)) for c in self.search_comps(text)]
        if not options:
            QMessageBox.warning(self, title, f"No team or competition in the game matches “{text.strip()}”.")
            return
        if len(options) == 1:
            self._set(row, options[0][1])
            return
        labels = [label for label, _ in options]
        label, ok = QInputDialog.getItem(self, title, f"Team or competition for “{name}”:", labels, 0, False)
        if ok and label in labels:
            self._set(row, options[labels.index(label)][1])
