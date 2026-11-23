"""Deploy history: every deploy recorded, newest first, installed or undone. Go back to before one (the newer ones are
undone first), re-apply an undone one (its changes wait for Deploy again), clear the ones ticked from the history."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from flkm.deploy import Deployment

HELP = (
    "Every deploy, newest first. Go back to before a deploy to undo it and the newer ones; re-apply an undone deploy "
    "to have its changes wait for Deploy again. Tick deploys and Clear history to delete their records."
)


def describe(d: Deployment) -> str:
    return ", ".join(d.items) or "Links to the app's kits written again"


def size_text(n: int) -> str:
    if n < 1024:
        return f"{n} bytes"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


class DeployHistoryDialog(QDialog):
    def __init__(
        self,
        load: Callable[[], list[Deployment]],
        go_back: Callable[[str], bool],
        reapply: Callable[[str], bool],
        clear: Callable[[set[str]], bool],
        parent: QWidget | None = None,
    ):
        """load() -> the deploys, newest first; go_back(id), reapply(id), clear(ids) do it (asking the user) and say
        whether something changed: the list is read again then."""
        super().__init__(parent)
        self.setWindowTitle("Deploy history")
        self.resize(900, 450)
        self.load, self.go_back, self.reapply, self.clear = load, go_back, reapply, clear
        self.deploys: list[Deployment] = []
        help_label = QLabel(HELP, wordWrap=True)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["When", "What", "State", "Size"])
        self.tree.setRootIsDecorated(False)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tree.currentItemChanged.connect(self._follow)
        self.tree.itemChanged.connect(self._ticked)
        self.total = QLabel()
        self.go_back_button = QPushButton("Go back to before this…")
        self.go_back_button.setToolTip(
            "Undo this deploy and every newer one still installed, newest first: the game files they changed are put "
            "back as they were (asks first)"
        )
        self.go_back_button.clicked.connect(lambda: self._run(self.go_back, self._current().id))
        self.reapply_button = QPushButton("Re-apply")
        self.reapply_button.setToolTip(
            "Put the changes of this undone deploy back among the changes waiting for Deploy (nothing is written to "
            "the game until you Deploy)"
        )
        self.reapply_button.clicked.connect(lambda: self._run(self.reapply, self._current().id))
        self.clear_button = QPushButton("Clear history…")
        self.clear_button.setToolTip(
            "Delete the records of the ticked deploys: they can no longer be undone or re-applied; the game files are "
            "not touched (asks first)"
        )
        self.clear_button.clicked.connect(lambda: self._run(self.clear, self._ticked_ids()))
        close = QPushButton("Close")
        close.setToolTip("Close the history")
        close.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        for b in (self.go_back_button, self.reapply_button, self.clear_button):
            buttons.addWidget(b)
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout = QVBoxLayout(self)
        layout.addWidget(help_label)
        layout.addWidget(self.tree, 1)
        layout.addWidget(self.total)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self) -> None:
        self.deploys = self.load()
        self.tree.blockSignals(True)
        self.tree.clear()
        grey = QBrush(QColor("gray"))
        for d in self.deploys:
            item = QTreeWidgetItem(
                [
                    d.when.strftime("%d/%m/%Y %H:%M"),
                    describe(d),
                    "Undone" if d.undone else "Installed",
                    size_text(d.size),
                ]
            )
            item.setCheckState(0, Qt.Unchecked)
            item.setToolTip(1, "\n".join(d.items) or describe(d))
            if d.undone:
                for col in range(4):
                    item.setForeground(col, grey)
            self.tree.addTopLevelItem(item)
        self.tree.blockSignals(False)
        for col in (0, 2, 3):
            self.tree.resizeColumnToContents(col)
        total = sum(d.size for d in self.deploys)
        self.total.setText(f"The history takes {size_text(total)}." if self.deploys else "No deploys recorded.")
        self._follow()
        self.clear_button.setEnabled(False)

    def _current(self) -> Deployment | None:
        item = self.tree.currentItem()
        return self.deploys[self.tree.indexOfTopLevelItem(item)] if item else None

    def _follow(self, *_) -> None:
        d = self._current()
        self.go_back_button.setEnabled(d is not None and not d.undone)
        self.reapply_button.setEnabled(d is not None and d.reapply)

    def _ticked_ids(self) -> set[str]:
        return {d.id for i, d in enumerate(self.deploys) if self.tree.topLevelItem(i).checkState(0) == Qt.Checked}

    def _ticked(self, item: QTreeWidgetItem, column: int) -> None:
        """an installed deploy ticked ticks the older installed ones (they cannot be undone without it); unticked, it
        unticks the newer installed ones"""
        i = self.tree.indexOfTopLevelItem(item)
        state = item.checkState(0)
        if not self.deploys[i].undone:
            older = state == Qt.Checked
            self.tree.blockSignals(True)
            for j, d in enumerate(self.deploys):
                if not d.undone and (j > i if older else j < i):
                    self.tree.topLevelItem(j).setCheckState(0, state)
            self.tree.blockSignals(False)
        self.clear_button.setEnabled(bool(self._ticked_ids()))

    def _run(self, action: Callable, arg) -> None:
        if action(arg):
            self.refresh()
