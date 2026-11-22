"""The competition page: name and details, and the three variants of its logo (Normal, Dark for light backgrounds,
White for dark backgrounds), each shown on a light and a dark background with where it is and its own Replace…;
Replace logo… replaces all three with one picture. A logo waiting for Deploy is shown in orange."""

from pathlib import Path

from PIL import Image
from PySide6.QtGui import QDesktopServices

from flkm.catalog import Competition
from flkm.competition_page import LOGO_SIZE, CompetitionPage

CUP = Competition(16, "ITALY_D1_CUP", "Coppa Italia", "Italy", "UEFA")
RED = Image.new("RGBA", (512, 512), (200, 0, 0, 255))


def make_page(qtbot):
    p = CompetitionPage()
    qtbot.addWidget(p)
    return p


def variants(pending=False):
    return {
        "": (RED, "dt15_x64.cpk › emb_0016_ll.png", pending),
        "b": (None, "Not in the game files", False),
        "w": (RED, "emb_0016_w_ll.png", False),
    }


def test_name_details_and_the_three_variants(qtbot):
    p = make_page(qtbot)
    p.show_competition(CUP, variants())
    assert p.title.text() == "Coppa Italia" and p.details.text() == "id 16 · ITALY_D1_CUP · Italy · UEFA"
    assert [c.name.text() for c in p.cards] == [
        "Normal",
        "Dark (for light backgrounds)",
        "White (for dark backgrounds)",
    ]
    normal, dark, _ = p.cards
    assert normal.light.pixmap().width() == LOGO_SIZE and normal.dark.pixmap().width() == LOGO_SIZE
    assert normal.source.text() == "dt15_x64.cpk › emb_0016_ll.png"
    assert dark.light.text() == "No logo" and dark.source.text() == "Not in the game files"
    assert not p.keep_button.isVisibleTo(p)


def test_details_without_country(qtbot):
    p = make_page(qtbot)
    p.show_competition(Competition(2, "UEFA_CHAMPIONS_LEAGUE", "UEFA Champions League", None, None), variants())
    assert p.details.text() == "id 2 · UEFA_CHAMPIONS_LEAGUE"


def test_replace_all_or_one_variant(qtbot):
    p = make_page(qtbot)
    p.show_competition(CUP, variants())
    asked = []
    p.replace_requested.connect(asked.append)
    p.replace_all_button.click()
    p.cards[2].replace_button.click()
    assert asked == ["all", "w"] and p.replace_all_button.text() == "Replace logo…"


def test_a_logo_waiting_for_deploy(qtbot):
    p = make_page(qtbot)
    p.show_competition(CUP, variants(pending=True), pending=True)
    assert p.keep_button.isVisibleTo(p) and p.keep_button.text() == "Keep the current logo"
    assert p.cards[0].name.text() == "Normal · new" and "d9822b" in p.cards[0].source.styleSheet()
    with qtbot.waitSignal(p.discard_requested):
        p.keep_button.click()
    p.show_competition(CUP, variants())  # a second competition replaces the cards
    assert len(p.cards) == 3 and not p.keep_button.isVisibleTo(p)


def test_the_folder_of_the_logo_is_shown_once_above_the_variants(qtbot, monkeypatch):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()))
    p = make_page(qtbot)
    data = Path("C:/FL/Data")
    p.show_competition(CUP, variants(), folder=data)
    assert p.folder_row.isVisibleTo(p) and p.folder_label.text() == str(data) and p.folder_label.toolTip() == str(data)
    p.open_folder_button.click()
    assert [Path(u) for u in opened] == [data]
    p.show_competition(CUP, variants())  # no logo in the game files
    assert not p.folder_row.isVisibleTo(p)
