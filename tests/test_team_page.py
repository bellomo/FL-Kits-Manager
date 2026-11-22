"""The team page: name and details of the team, then one card per kit (slot name, picture, where the kit comes from),
folded or unrolled; a kit that cannot be read says so instead of a picture."""

from dataclasses import dataclass

from PIL import Image
from PySide6.QtGui import QFont

from flkm import render
from flkm.catalog import Team
from flkm.game.ftex import FtexError
from flkm.team_page import TITLE_EXTRA, TeamPage, slot_name

BOLOGNA = Team(186, "Bologna FC", "BOL", "Italy D1", "Italy", "UEFA")


@dataclass
class FakeKit:
    slot: str
    source: str = "Data\\dt34_g4.cpk"
    broken: bool = False

    def picture(self, size):
        self.asked = size
        if self.broken:
            raise FtexError("damaged texture")
        return Image.new("RGB", (size, size), (200, 0, 0))


def make_page(qtbot, view="folded"):
    p = TeamPage(view=view)
    qtbot.addWidget(p)
    return p


def test_slot_names():
    assert [slot_name(s) for s in ("p1", "p2", "p3", "p4", "g1", "g2")] == [
        "Home",
        "Away",
        "Third",
        "Kit 4",
        "Goalkeeper",
        "Goalkeeper 2",
    ]


def test_team_name_and_details(qtbot):
    p = make_page(qtbot)
    p.show_team(BOLOGNA, [])
    assert p.title.text() == "Bologna FC"
    assert p.details.text() == "id 186 · BOL · Italy D1 · Italy · UEFA"
    assert p.empty.isVisibleTo(p) and p.empty.text() == "No kits found for this team."


def test_missing_details_are_left_out(qtbot):
    p = make_page(qtbot)
    p.show_team(Team(900, "Titans Classics", "TIT", None, None, None), [])
    assert p.details.text() == "id 900 · TIT"


def test_one_card_per_kit_folded(qtbot):
    p = make_page(qtbot)
    kits = [FakeKit("p1"), FakeKit("p2", "kitserver: _World\\Bologna")]
    p.show_team(BOLOGNA, kits)
    assert not p.empty.isVisibleTo(p)
    assert [(c.name.text(), c.source.text()) for c in p.cards] == [
        ("Home", "Data\\dt34_g4.cpk"),
        ("Away", "kitserver: _World\\Bologna"),
    ]
    pix = p.cards[0].picture.pixmap()
    assert (pix.width(), pix.height()) == (render.VIEW_W, render.VIEW_H // 2)  # front and back, half size
    assert kits[0].asked == 1024


def test_unrolled_view(qtbot):
    p = make_page(qtbot, view="unrolled")
    kit = FakeKit("p1")
    p.show_team(BOLOGNA, [kit])
    pix = p.cards[0].picture.pixmap()
    assert (pix.width(), pix.height()) == (320, 320) and kit.asked == 512
    assert p.unrolled_button.isChecked() and not p.folded_button.isChecked()


def test_switching_view_redraws_and_tells_the_window(qtbot):
    p = make_page(qtbot)
    p.show_team(BOLOGNA, [FakeKit("p1")])
    with qtbot.waitSignal(p.view_changed) as sig:
        p.unrolled_button.click()
    assert sig.args == ["unrolled"] and p.view == "unrolled"
    assert p.cards[0].picture.pixmap().width() == 320
    p.folded_button.click()
    assert p.cards[0].picture.pixmap().width() == render.VIEW_W


def test_a_kit_that_cannot_be_read_says_so(qtbot):
    p = make_page(qtbot)
    p.show_team(BOLOGNA, [FakeKit("p1", broken=True)])
    assert p.cards[0].picture.text() == "Cannot read this kit: damaged texture"


def test_team_name_stays_larger_than_the_text_when_the_text_size_changes(qtbot):
    p = make_page(qtbot)
    font = QFont(p.font())
    font.setPointSize(20)
    p.setFont(font)
    assert p.title.font().pointSize() == 20 + TITLE_EXTRA and p.title.font().bold()


def test_showing_another_team_replaces_the_cards(qtbot):
    p = make_page(qtbot)
    p.show_team(BOLOGNA, [FakeKit("p1"), FakeKit("p2")])
    p.show_team(BOLOGNA, [FakeKit("g1")])
    assert [c.name.text() for c in p.cards] == ["Goalkeeper"]
