"""The logo import dialog: the logos found in a pack, with a small picture of each and the team or competition it goes
to. Sure ones are ticked; the others wait for the user to check them or choose the team or competition (by id or
name)."""

import io

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QInputDialog, QMessageBox

from flkm.catalog import Competition, Team
from flkm.logo_import_dialog import LogoImportDialog
from flkm.logo_pack import LogoFile

BOLOGNA = Team(186, "Bologna FC", "BOL", "Serie A TIM", "Italy", "UEFA")
INTER = Team(119, "Inter Milan", "INT", "Serie A TIM", "Italy", "UEFA")
CUP = Competition(16, "ITALY_D1_CUP", "Coppa Italia", "Italy", "UEFA")
SUPER = Competition(119, "ITALY_SUPER_CUP", "Supercoppa Italiana", "Italy", "UEFA")
FOUND = [
    LogoFile("flag/e_000186_r_l.png", "crest", 186, "Bologna FC", "", "file name", True),
    LogoFile("emb/emb_0016_w_l.png", "emblem", 16, "Coppa Italia", "w", "file name", True),
    LogoFile("Inter.png", "crest", 119, "Inter Milan", "", "name", False, "also Internacional"),
    LogoFile("emb/emb_0999_l.png", "emblem", None, "", "", "file name", False, "no competition with id 999"),
]


def png():
    buf = io.BytesIO()
    Image.new("RGBA", (64, 64), (200, 0, 0, 255)).save(buf, "PNG")
    return buf.getvalue()


def read(path):
    return b"broken" if path == "Inter.png" else png()


def search_teams(text):
    q = text.casefold()
    return [t for t in (BOLOGNA, INTER) if q in t.name.casefold() or q == str(t.id)]


def search_comps(text):
    q = text.casefold()
    return [c for c in (CUP, SUPER) if q in c.name.casefold() or q == str(c.id)]


def make(qtbot, found=FOUND):
    d = LogoImportDialog("logos.zip", found, search_teams, search_comps, read)
    qtbot.addWidget(d)
    return d


def cell(d, row, col):
    return d.table.item(row, col).text()


def test_rows_show_the_logos_and_where_they_go(qtbot):
    d = make(qtbot)
    assert d.windowTitle() == "Import logos from logos.zip"
    assert [[cell(d, r, c) for c in range(2, 5)] for r in range(4)] == [
        ["flag/e_000186_r_l.png", "Crest of Bologna FC (id 186)", "file name"],
        ["emb/emb_0016_w_l.png", "Coppa Italia logo (id 16), White", "file name"],
        ["Inter.png", "Crest of Inter Milan (id 119)", "name: also Internacional"],
        ["emb/emb_0999_l.png", "—", "file name: no competition with id 999"],
    ]
    assert d.summary.text() == "4 logos: 2 sure, 2 to check."
    assert not d.table.item(0, 1).icon().isNull()
    assert d.table.item(2, 1).icon().isNull() and cell(d, 2, 1) == "?"  # not a picture


def test_only_sure_logos_are_ticked_and_the_add_button_needs_one(qtbot):
    d = make(qtbot)
    assert [d.table.item(r, 0).checkState() == Qt.Checked for r in range(4)] == [True, True, False, False]
    assert not d.table.item(3, 0).flags() & Qt.ItemIsUserCheckable  # goes nowhere: nothing to tick
    assert d.chosen() == FOUND[:2]
    d.table.item(2, 0).setCheckState(Qt.Checked)
    assert d.chosen() == FOUND[:3]
    add = d.buttons.button(QDialogButtonBox.Ok)
    assert add.text() == "Add to changes" and add.isEnabled()
    for r in range(3):
        d.table.item(r, 0).setCheckState(Qt.Unchecked)
    assert not add.isEnabled()


def test_choose_a_competition_by_its_id(qtbot, monkeypatch):
    d = make(qtbot)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("16", True))
    d.table.selectRow(3)
    d.choose_button.click()
    assert cell(d, 3, 3) == "Coppa Italia logo (id 16), Normal" and cell(d, 3, 4) == "chosen"
    assert d.table.item(3, 0).checkState() == Qt.Checked and d.summary.text() == "4 logos: 3 sure, 1 to check."


def test_choose_among_teams_and_competitions_with_the_id(qtbot, monkeypatch):
    d = make(qtbot)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("119", True))
    asked = []
    monkeypatch.setattr(
        QInputDialog, "getItem", lambda parent, title, label, items, *a, **k: (asked.append(items), items[1], True)[1:]
    )
    d.choose(2)
    assert asked == [["Crest of Inter Milan (id 119)", "Supercoppa Italiana logo (id 119)"]]
    assert cell(d, 2, 3) == "Supercoppa Italiana logo (id 119), all variants"


def test_choose_cancelled_or_not_found(qtbot, monkeypatch):
    d = make(qtbot)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("", False))
    d.choose(3)
    assert cell(d, 3, 3) == "—"
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda parent, title, text: warnings.append(text))
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Zalgiris", True))
    d.choose(3)
    assert warnings == ["No team or competition in the game matches “Zalgiris”."] and cell(d, 3, 3) == "—"
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("119", True))
    monkeypatch.setattr(QInputDialog, "getItem", lambda *a, **k: ("", False))
    d.choose(3)
    assert cell(d, 3, 3) == "—"


def test_double_click_chooses_and_choose_needs_a_selected_row(qtbot, monkeypatch):
    d = make(qtbot)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("bologna", True))
    d.table.cellDoubleClicked.emit(3, 3)
    assert cell(d, 3, 3) == "Crest of Bologna FC (id 186)"
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: (_ for _ in ()).throw(AssertionError("not asked")))
    d.table.clearSelection()
    d.choose_button.click()
