"""The import dialog: the team folders of a kit pack and the game team each one goes to. Sure matches are ticked;
the others wait for the user to check them or choose the team (by id or name)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QInputDialog, QMessageBox

from conftest import buttons_without_tooltip
from flkm.catalog import Team
from flkm.import_dialog import ImportDialog
from flkm.pack import Match, PackTeam

BOLOGNA = Team(186, "Bologna FC", "BOL", "Serie A TIM", "Italy", "UEFA")
INTER = Team(119, "Inter Milan", "INT", "Serie A TIM", "Italy", "UEFA")
COMO = Team(4300, "Como 1907", "COM", "Serie A TIM", "Italy", "UEFA")
GAME = [BOLOGNA, INTER, COMO, Team(500, "Real Madrid CF", "RMA", None, None, None)]


def pt(name, slots=("p1", "p2")):
    return PackTeam(f"Serie A/{name}", name, slots, None)


MATCHES = [
    Match(pt("Bologna", ("p1", "p2", "g1")), BOLOGNA, "id and name", True),
    Match(pt("Internazionale", ("p1",)), INTER, "id", False, "named Inter Milan in this game"),
    Match(pt("Zalgiris"), None, "none", False, "no team with this id or name"),
]


def search(text):
    q = text.casefold()
    return [t for t in GAME if q in t.name.casefold() or q == str(t.id)]


def make(qtbot, matches=MATCHES):
    d = ImportDialog("Serie A Kitpack.zip", matches, search)
    qtbot.addWidget(d)
    return d


def cell(d, row, col):
    return d.table.item(row, col).text()


def test_rows_show_the_pack_folders_and_their_teams(qtbot):
    d = make(qtbot)
    assert d.windowTitle() == "Import kits from Serie A Kitpack.zip"
    assert [[cell(d, r, c) for c in range(1, 5)] for r in range(3)] == [
        ["Serie A/Bologna", "Home, Away, Goalkeeper", "Bologna FC (id 186)", "id and name"],
        ["Serie A/Internazionale", "Home", "Inter Milan (id 119)", "id: named Inter Milan in this game"],
        ["Serie A/Zalgiris", "Home, Away", "—", "none: no team with this id or name"],
    ]
    assert d.summary.text() == "3 team folders: 1 sure, 2 to check."


def test_only_sure_matches_are_ticked(qtbot):
    d = make(qtbot)
    assert [d.table.item(r, 0).checkState() == Qt.Checked for r in range(3)] == [True, False, False]
    assert not d.table.item(2, 0).flags() & Qt.ItemIsUserCheckable  # no team: nothing to tick
    assert d.chosen() == [(MATCHES[0].pack_team, BOLOGNA)]


def test_ticking_a_row_that_needs_checking(qtbot):
    d = make(qtbot)
    d.table.item(1, 0).setCheckState(Qt.Checked)
    assert d.chosen() == [(MATCHES[0].pack_team, BOLOGNA), (MATCHES[1].pack_team, INTER)]


def test_the_add_button_needs_a_ticked_row(qtbot):
    d = make(qtbot)
    add = d.buttons.button(QDialogButtonBox.Ok)
    assert add.text() == "Add to changes" and add.isEnabled()
    d.table.item(0, 0).setCheckState(Qt.Unchecked)
    assert not add.isEnabled()


def test_choose_the_team_by_id(qtbot, monkeypatch):
    d = make(qtbot)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("4300", True))
    d.table.selectRow(2)
    d.choose_button.click()
    assert cell(d, 2, 3) == "Como 1907 (id 4300)" and cell(d, 2, 4) == "chosen"
    assert d.table.item(2, 0).checkState() == Qt.Checked
    assert d.summary.text() == "3 team folders: 2 sure, 1 to check."


def test_choose_the_team_by_name_among_several(qtbot, monkeypatch):
    d = make(qtbot)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("i", True))  # Inter Milan, Real Madrid CF
    asked = []
    monkeypatch.setattr(
        QInputDialog, "getItem", lambda parent, title, label, items, *a, **k: (asked.append(items), items[1], True)[1:]
    )
    d.choose_team(1)
    assert asked == [["Inter Milan (id 119)", "Real Madrid CF (id 500)"]]
    assert cell(d, 1, 3) == "Real Madrid CF (id 500)"


def test_choose_a_team_cancelled_or_not_found(qtbot, monkeypatch):
    d = make(qtbot)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("", False))
    d.choose_team(2)
    assert cell(d, 2, 3) == "—"
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warnings.append(text))
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Zalgiris", True))
    d.choose_team(2)
    assert warnings == ["No team in the game matches “Zalgiris”."] and cell(d, 2, 3) == "—"
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("i", True))
    monkeypatch.setattr(QInputDialog, "getItem", lambda *a, **k: ("", False))
    d.choose_team(2)
    assert cell(d, 2, 3) == "—"


def test_double_click_chooses_the_team(qtbot, monkeypatch):
    d = make(qtbot)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("bologna", True))
    d.table.cellDoubleClicked.emit(2, 3)
    assert cell(d, 2, 3) == "Bologna FC (id 186)"


def test_choose_without_a_selected_row_does_nothing(qtbot, monkeypatch):
    d = make(qtbot)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: (_ for _ in ()).throw(AssertionError("not asked")))
    d.table.clearSelection()
    d.choose_button.click()


def test_folder_at_the_root_of_the_pack(qtbot):
    d = make(qtbot, [Match(PackTeam("", "", ("p1",), None), None, "none", False, "no team with this id or name")])
    assert cell(d, 0, 1) == "(the pack itself)"


def test_every_button_has_a_tooltip(qtbot):
    assert buttons_without_tooltip(make(qtbot)) == []
