"""The team list: a tree federation > country > league > team, with a search box (name or id)."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from flkm.catalog import Catalog

OPEN_UP = 50  # a search that finds at most this many teams shows them all opened up
_NONE = ("Other", "Unknown country", "No league")  # names for a missing federation, country, league
_TEAM_ID = Qt.UserRole


class TeamTree(QWidget):
    team_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.catalog: Catalog | None = None
        self.search = QLineEdit(placeholderText="Search a team by name or id")
        self.search.setClearButtonEnabled(True)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.search)
        layout.addWidget(self.tree)
        self.search.textChanged.connect(self._fill)
        self.tree.currentItemChanged.connect(self._chosen)

    def set_catalog(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self._fill(self.search.text())

    def _fill(self, text: str) -> None:
        self.tree.clear()
        if self.catalog is None:
            return
        found = self.catalog.search(text)
        if not found:
            item = QTreeWidgetItem(["No team found"])
            item.setFlags(Qt.ItemIsEnabled)
            self.tree.addTopLevelItem(item)
            return
        for fed, countries in self.catalog.by_federation(found).items():
            fed_item = self._group(None, fed, 0, sum(len(ts) for ls in countries.values() for ts in ls.values()))
            for country, leagues in countries.items():
                country_item = self._group(fed_item, country, 1, sum(len(ts) for ts in leagues.values()))
                for league, teams in leagues.items():
                    league_item = self._group(country_item, league, 2, len(teams))
                    for t in teams:
                        item = QTreeWidgetItem(league_item, [t.name])
                        item.setData(0, _TEAM_ID, t.id)
                        item.setToolTip(0, f"id {t.id} · {t.abbr}")
        if text.strip() and len(found) <= OPEN_UP:
            self.tree.expandAll()

    def _group(self, parent: QTreeWidgetItem | None, name: str | None, level: int, count: int) -> QTreeWidgetItem:
        item = QTreeWidgetItem([f"{name or _NONE[level]} ({count})"])
        if parent is None:
            self.tree.addTopLevelItem(item)
        else:
            parent.addChild(item)
        return item

    def select_team(self, team_id: int) -> bool:
        """chooses the team in the tree (opening its groups); False when the tree does not show it"""
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            if item.data(0, _TEAM_ID) == team_id:
                parent = item.parent()
                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()
                self.tree.setCurrentItem(item)
                return True
            it += 1
        return False

    def _chosen(self, item: QTreeWidgetItem | None) -> None:
        team_id = item.data(0, _TEAM_ID) if item is not None else None
        if team_id is not None:
            self.team_selected.emit(team_id)
