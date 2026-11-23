"""The import dialog: the team folders of a kit pack and the game team each one goes to.

Sure matches (id and name agree, or a single team with the name) are ticked; the others show why they need checking.
The user can tick them, or choose the team by id or name (Choose team… or a double click).
"""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
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

from flkm.catalog import Team
from flkm.game.kits import slot_name
from flkm.pack import Match, PackTeam

COLUMNS = ("", "Folder in the pack", "Kits", "Team in the game", "How it was matched")
CHECK_COLOUR = "#d9822b"  # rows the user should check
NOTE = (
    "Each kit of the pack replaces the team's kit of the same kind (Home, Away, ...); the team's other kits stay. "
    "A team whose kits come from the game files gets a kitserver folder with only the pack's kits. "
    "Nothing is written to the game before Deploy."
)


class ImportDialog(QDialog):
    def __init__(self, source_name: str, matches: list[Match], search: Callable[[str], list[Team]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Import kits from {source_name}")
        self.resize(1000, 520)
        self.matches = list(matches)
        self.search = search
        self.summary = QLabel()
        self.table = QTableWidget(len(self.matches), len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        for row in range(len(self.matches)):
            self._fill(row, checked=self.matches[row].sure and self.matches[row].team is not None)
        self.table.itemChanged.connect(lambda _: self._update())
        self.table.cellDoubleClicked.connect(lambda row, _col: self.choose_team(row))
        note = QLabel(NOTE)
        note.setWordWrap(True)
        note.setStyleSheet("color: gray")
        self.choose_button = QPushButton("Choose team…")
        self.choose_button.setToolTip("Choose the game team the selected kit folder goes to (or double-click its row)")
        self.choose_button.clicked.connect(self._choose_selected)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText("Add to changes")
        self.buttons.button(QDialogButtonBox.Ok).setToolTip("Add the ticked kits to the changes (installed by Deploy)")
        self.buttons.button(QDialogButtonBox.Cancel).setToolTip("Close without adding any kit")
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

    def _fill(self, row: int, checked: bool) -> None:
        m = self.matches[row]
        self.table.blockSignals(True)
        tick = QTableWidgetItem()
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        tick.setFlags(flags | Qt.ItemIsUserCheckable if m.team else flags)
        tick.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        how = m.how + (f": {m.note}" if m.note else "")
        texts = (
            m.pack_team.path or "(the pack itself)",
            ", ".join(slot_name(s) for s in m.pack_team.slots),
            f"{m.team.name} (id {m.team.id})" if m.team else "—",
            how,
        )
        self.table.setItem(row, 0, tick)
        for col, text in enumerate(texts, start=1):
            item = QTableWidgetItem(text)
            if not m.sure:
                item.setForeground(QColor(CHECK_COLOUR))
            self.table.setItem(row, col, item)
        self.table.blockSignals(False)

    def _update(self) -> None:
        sure = sum(m.sure for m in self.matches)
        self.summary.setText(f"{len(self.matches)} team folders: {sure} sure, {len(self.matches) - sure} to check.")
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(self.chosen()))

    def chosen(self) -> list[tuple[PackTeam, Team]]:
        """the ticked rows: pack team folder and the game team it goes to"""
        return [
            (m.pack_team, m.team)
            for row, m in enumerate(self.matches)
            if m.team is not None and self.table.item(row, 0).checkState() == Qt.Checked
        ]

    def set_team(self, row: int, team: Team) -> None:
        self.matches[row] = Match(self.matches[row].pack_team, team, "chosen", True)
        self._fill(row, checked=True)
        self._update()

    def _choose_selected(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.choose_team(rows[0].row())

    def choose_team(self, row: int) -> None:
        name = self.matches[row].pack_team.name
        text, ok = QInputDialog.getText(self, "Choose team", f"Game team for “{name}” (id or name):")
        if not ok or not text.strip():
            return
        found = self.search(text)
        exact = [t for t in found if str(t.id) == text.strip()]
        if exact or len(found) == 1:
            self.set_team(row, (exact or found)[0])
            return
        if not found:
            QMessageBox.warning(self, "Choose team", f"No team in the game matches “{text.strip()}”.")
            return
        labels = [f"{t.name} (id {t.id})" for t in found]
        label, ok = QInputDialog.getItem(self, "Choose team", f"Game team for “{name}”:", labels, 0, False)
        if ok and label in labels:
            self.set_team(row, found[labels.index(label)])
