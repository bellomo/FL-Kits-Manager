"""The team page: name and details of the team, the folder of its kits (once, with Open folder), then one card per kit
(slot name, picture, file name in that folder), folded or unrolled; a kit that cannot be read says so instead of a
picture."""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from PySide6.QtGui import QDesktopServices, QFont

from flkm import render
from flkm.catalog import Team
from flkm.game.ftex import FtexError
from flkm.team_page import CREST_SIZE, TITLE_EXTRA, TeamPage, slot_name

BOLOGNA = Team(186, "Bologna FC", "BOL", "Italy D1", "Italy", "UEFA")


TEAM = Path("C:/FL/SiderAddons/content/kits/Serie A/Bologna")


@dataclass
class FakeKit:
    slot: str
    source: str = "kitserver: Serie A\\Bologna"
    broken: bool = False
    folder: Path | None = None
    file_name: str = ""

    def __post_init__(self):
        self.folder = self.folder or TEAM / self.slot
        self.file_name = self.file_name or f"u186{self.slot}.ftex"

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
    kits = [FakeKit("p1"), FakeKit("p2")]
    p.show_team(BOLOGNA, kits)
    assert not p.empty.isVisibleTo(p)
    assert [(c.name.text(), c.source.text()) for c in p.cards] == [
        ("Home", "p1\\u186p1.ftex"),
        ("Away", "p2\\u186p2.ftex"),
    ]
    pix = p.cards[0].picture.pixmap()
    assert (pix.width(), pix.height()) == (render.VIEW_W, render.VIEW_H // 2)  # front and back, half size
    assert kits[0].asked == 1024


def test_the_folder_of_the_kits_is_shown_once_above_them(qtbot):
    p = make_page(qtbot)
    p.show_team(BOLOGNA, [FakeKit("p1"), FakeKit("g1")])
    assert p.folder_row.isVisibleTo(p) and p.folder_label.text() == str(TEAM)
    assert p.cards[1].source.toolTip() == str(TEAM / "g1" / "u186g1.ftex")


def test_kits_in_one_folder_show_only_their_file_names(qtbot):
    p = make_page(qtbot)
    data = Path("C:/FL/Data")
    cpk = [FakeKit(s, "Data\\dt34_g4.cpk", folder=data, file_name=f"dt34_g4.cpk › u0186{s}.ftex") for s in ("p1", "p2")]
    p.show_team(BOLOGNA, cpk)
    assert p.folder_label.text() == str(data)
    assert [c.source.text() for c in p.cards] == ["dt34_g4.cpk › u0186p1.ftex", "dt34_g4.cpk › u0186p2.ftex"]


def test_kits_on_different_drives_show_their_whole_path(qtbot):
    p = make_page(qtbot)
    p.show_team(BOLOGNA, [FakeKit("p1"), FakeKit("p2", folder=Path("D:/kits"))])
    assert not p.folder_row.isVisibleTo(p)
    assert [c.source.text() for c in p.cards] == [str(TEAM / "p1" / "u186p1.ftex"), str(Path("D:/kits/u186p2.ftex"))]


def test_open_folder_opens_the_kits_folder(qtbot, monkeypatch):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()))
    p = make_page(qtbot)
    p.show_team(BOLOGNA, [FakeKit("p1")])
    p.open_folder_button.click()
    assert [Path(u) for u in opened] == [TEAM / "p1"]


def test_no_folder_row_without_kits_of_the_game(qtbot):
    p = make_page(qtbot)
    p.show_team(BOLOGNA, [])
    assert not p.folder_row.isVisibleTo(p)
    p.show_team(BOLOGNA, [], pending={"p1": FakeKit("p1", "New kit from a pack")})  # only kits waiting for Deploy
    assert not p.folder_row.isVisibleTo(p) and p.cards[0].source.text() == "New kit from a pack"


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


def test_each_card_offers_to_replace_its_kit(qtbot):
    p = make_page(qtbot)
    p.show_team(BOLOGNA, [FakeKit("p1"), FakeKit("g1")])
    card = p.cards[1]
    assert card.replace_button.text() == "Replace…" and not card.discard_button.isVisibleTo(card)
    with qtbot.waitSignal(p.replace_requested) as sig:
        card.replace_button.click()
    assert sig.args == ["g1"]


def test_a_kit_waiting_for_deploy_is_shown_instead_of_the_current_one(qtbot):
    p = make_page(qtbot)
    new = FakeKit("p1", "New kit, not deployed yet: C:\\kits\\home.ftex")
    p.show_team(BOLOGNA, [FakeKit("p1"), FakeKit("p2")], pending={"p1": new})
    card = p.cards[0]
    assert card.pending and card.kit is new and new.asked == 1024
    assert card.name.text() == "Home · new" and card.source.text() == new.source
    assert card.discard_button.isVisibleTo(card) and card.discard_button.text() == "Keep the current kit"
    assert not p.cards[1].pending and p.cards[1].name.text() == "Away"
    with qtbot.waitSignal(p.discard_requested) as sig:
        card.discard_button.click()
    assert sig.args == ["p1"]


def test_a_new_kit_the_team_did_not_have_gets_its_own_card(qtbot):
    p = make_page(qtbot)
    third, gk = FakeKit("p3", "New kit from a pack"), FakeKit("g1", "New kit from a pack")
    p.show_team(BOLOGNA, [FakeKit("p1")], pending={"g1": gk, "p3": third})
    assert [(c.name.text(), c.pending) for c in p.cards] == [
        ("Home", False),
        ("Third · new", True),
        ("Goalkeeper · new", True),
    ]
    assert p.cards[1].discard_button.text() == "Don't add this kit"
    assert not p.empty.isVisibleTo(p)
    with qtbot.waitSignal(p.discard_requested) as sig:
        p.cards[2].discard_button.click()
    assert sig.args == ["g1"]


def test_showing_another_team_replaces_the_cards(qtbot):
    p = make_page(qtbot)
    p.show_team(BOLOGNA, [FakeKit("p1"), FakeKit("p2")])
    p.show_team(BOLOGNA, [FakeKit("g1")])
    assert [c.name.text() for c in p.cards] == ["Goalkeeper"]


# --- crest -----------------------------------------------------------------------------------------------------------


def test_the_crest_next_to_the_team_name(qtbot):
    p = make_page(qtbot)
    p.show_team(BOLOGNA, [])
    p.show_crest(Image.new("RGBA", (512, 512), (200, 0, 0, 255)), "e_000186_r_ll.png · livecpk\\_World")
    pix = p.crest.pixmap()
    assert (pix.width(), pix.height()) == (CREST_SIZE, CREST_SIZE)
    assert p.crest_source.text() == "e_000186_r_ll.png · livecpk\\_World"
    assert p.replace_crest_button.text() == "Replace crest…" and not p.keep_crest_button.isVisibleTo(p)
    with qtbot.waitSignal(p.crest_replace_requested):
        p.replace_crest_button.click()


def test_a_team_without_a_crest(qtbot):
    p = make_page(qtbot)
    p.show_crest(None, "")
    assert p.crest.text() == "No crest" and p.crest_source.text() == ""


def test_a_crest_waiting_for_deploy(qtbot):
    p = make_page(qtbot)
    p.show_crest(Image.new("RGBA", (100, 50)), "New crest, not deployed yet: bologna.png", pending=True)
    assert p.keep_crest_button.isVisibleTo(p) and p.keep_crest_button.text() == "Keep the current crest"
    assert "d9822b" in p.crest_source.styleSheet()
    with qtbot.waitSignal(p.crest_discard_requested):
        p.keep_crest_button.click()
    p.show_crest(None, "")
    assert not p.keep_crest_button.isVisibleTo(p) and "gray" in p.crest_source.styleSheet()


def test_the_folder_of_the_crest_is_shown_above_the_kits_folder_with_its_own_open_folder(qtbot, monkeypatch):
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()))
    p = make_page(qtbot)
    flags = Path("C:/FL/livecpk/_World/common/render/symbol/flag")
    p.show_crest(Image.new("RGBA", (256, 256)), "e_000186_r_l.png", folder=flags)
    assert p.crest_source.text() == "e_000186_r_l.png"
    assert p.crest_folder_row.isVisibleTo(p) and p.crest_folder_label.text() == str(flags)
    assert p.crest_folder_label.toolTip() == str(flags)
    p.open_crest_folder_button.click()
    assert [Path(u) for u in opened] == [flags]
    layout = p.layout()
    assert layout.indexOf(p.crest_folder_row) == layout.indexOf(p.folder_row) - 1
    p.show_crest(None, "No crest in the game files")  # no file: no folder
    assert not p.crest_folder_row.isVisibleTo(p)
