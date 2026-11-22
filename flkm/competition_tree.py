"""The competition list: a tree federation > country > competition (International: no country), with a search box
(name, code or id)."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLineEdit, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QVBoxLayout, QWidget

from flkm.catalog import Catalog

OPEN_UP = 50  # a search that finds at most this many competitions shows them all opened up
INTERNATIONAL = "International"
_COMP_ID = Qt.UserRole


class CompetitionTree(QWidget):
    competition_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.catalog: Catalog | None = None
        self.search = QLineEdit(placeholderText="Search a competition by name or id")
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
        found = {c.id for c in self.catalog.search_competitions(text)}
        groups = {
            fed: {country: [c for c in comps if c.id in found] for country, comps in countries.items()}
            for fed, countries in self.catalog.competitions_by_federation().items()
        }
        groups = {f: {c: cs for c, cs in countries.items() if cs} for f, countries in groups.items()}
        groups = {f: countries for f, countries in groups.items() if countries}
        if not groups:
            item = QTreeWidgetItem(["No competition found"])
            item.setFlags(Qt.ItemIsEnabled)
            self.tree.addTopLevelItem(item)
            return
        for fed, countries in groups.items():
            fed_item = QTreeWidgetItem([f"{fed or INTERNATIONAL} ({sum(len(cs) for cs in countries.values())})"])
            self.tree.addTopLevelItem(fed_item)
            for country, comps in countries.items():
                parent = fed_item
                if country is not None:
                    parent = QTreeWidgetItem(fed_item, [f"{country} ({len(comps)})"])
                for c in comps:
                    item = QTreeWidgetItem(parent, [c.name])
                    item.setData(0, _COMP_ID, c.id)
                    item.setToolTip(0, f"id {c.id} · {c.code}")
        if text.strip() and len(found) <= OPEN_UP:
            self.tree.expandAll()

    def select(self, comp_id: int) -> bool:
        """chooses the competition in the tree; False when the tree does not show it"""
        it = QTreeWidgetItemIterator(self.tree)
        while it.value():
            item = it.value()
            if item.data(0, _COMP_ID) == comp_id:
                self.tree.setCurrentItem(item)
                return True
            it += 1
        return False

    def _chosen(self, item: QTreeWidgetItem | None) -> None:
        comp_id = item.data(0, _COMP_ID) if item is not None else None
        if comp_id is not None:
            self.competition_selected.emit(comp_id)
