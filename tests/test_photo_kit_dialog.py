"""The Kits from photos dialog: photos added from files, a folder, dragged in or pasted, one per box (kit x part);
dragged between boxes, replaced or removed; the kits made in the background and shown next to the ones the team wears
now before they are added to the changes."""

import warnings
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QByteArray, QEvent, QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QContextMenuEvent, QDragEnterEvent, QDropEvent, QImage, QMouseEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from conftest import buttons_without_tooltip
from flkm import photo_kit_dialog
from flkm.photo_kit_dialog import CELL_MIME, PhotoCell, PhotoKitDialog, pil_image, read_mime, run_in_thread
from flkm.photokit.team import MadeTeam


def photo(folder: Path, name: str, colour=(200, 30, 30)) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    Image.new("RGB", (60, 80), colour).save(p)
    return p


def qimage() -> QImage:
    image = QImage(20, 10, QImage.Format_RGB32)
    image.fill(Qt.GlobalColor.blue)
    return image


def sync(work, on_done, on_error):
    """runs the job at once, in the test's thread"""
    try:
        on_done(work())
    except Exception as e:  # noqa: BLE001
        on_error(str(e))


def make(qtbot, tmp_path, make_kits=None, current=None, chosen=None, tones=None, **kw):
    work = tmp_path / "work"
    d = PhotoKitDialog("Crotone", work, make_kits or (lambda c, t: None), current or {}, chosen, tones, run=sync, **kw)
    qtbot.addWidget(d)
    return d


def mime_with(urls=(), image=None, cell=None) -> QMimeData:
    m = QMimeData()
    if urls:
        m.setUrls([QUrl.fromLocalFile(str(u)) if isinstance(u, Path) else QUrl(u) for u in urls])
    if image is not None:
        m.setImageData(image)
    if cell:
        m.setData(CELL_MIME, QByteArray("/".join(cell).encode()))
    return m


# --- reading what is dropped or pasted --------------------------------------------------------------------------


def test_pil_image_of_a_qimage():
    im = pil_image(qimage())
    assert im.mode == "RGBA" and im.size == (20, 10) and im.getpixel((5, 5)) == (0, 0, 255, 255)


def test_read_mime(tmp_path):
    p = photo(tmp_path, "a.png")
    assert read_mime(mime_with(cell=("home", "back"))) == ("cell", ("home", "back"))
    assert read_mime(mime_with(urls=[p])) == ("files", [p])
    kind, image = read_mime(mime_with(image=qimage()))
    assert kind == "image" and image.size == (20, 10)
    assert read_mime(mime_with(urls=["https://example.com/kit.png"])) == ("remote", ["https://example.com/kit.png"])
    assert read_mime(QMimeData()) is None


def test_run_in_thread_gives_the_result_or_the_error(qtbot):
    done, failed = [], []
    run_in_thread(lambda: 42, done.append, failed.append)
    qtbot.waitUntil(lambda: done == [42])

    def broken(message):
        def work():
            raise ValueError(message)

        return work

    run_in_thread(broken("no crest"), done.append, failed.append)
    qtbot.waitUntil(lambda: failed == ["no crest"])
    run_in_thread(broken(""), done.append, failed.append)
    qtbot.waitUntil(lambda: failed == ["no crest", "ValueError"])
    qtbot.waitUntil(lambda: not photo_kit_dialog._jobs)


# --- one box --------------------------------------------------------------------------------------------------------


def cell_widget(qtbot, cell=("home", "shirt")):
    c = PhotoCell(cell)
    qtbot.addWidget(c)
    return c


def test_a_box_shows_its_photo_or_how_to_add_one(qtbot, tmp_path):
    c = cell_widget(qtbot)
    assert c.picture.text() == "Drop, paste\nor double-click" and c.path is None
    p = photo(tmp_path, "home_1.png")
    c.show_photo(p)
    assert c.picture.text() == "" and not c.picture.pixmap().isNull() and c.toolTip() == str(p)
    assert c.picture.pixmap().height() <= photo_kit_dialog.THUMB
    bad = tmp_path / "broken.png"
    bad.write_bytes(b"not a picture")
    c.show_photo(bad)
    assert c.picture.text() == "Cannot read\nbroken.png"
    c.show_photo(None)
    assert c.toolTip() == "Drop or paste a photo here, or double-click to choose one" and c.picture.pixmap().isNull()


def test_a_box_shows_when_it_is_selected(qtbot):
    c = cell_widget(qtbot)
    c.set_selected(True)
    assert "highlight" in c.styleSheet()
    c.set_selected(False)
    assert "dashed" in c.styleSheet()


def mouse(kind, pos, buttons=Qt.LeftButton):
    button = Qt.NoButton if kind == QEvent.MouseMove else Qt.LeftButton
    return QMouseEvent(kind, QPointF(pos), QPointF(pos), button, buttons, Qt.NoModifier)


def test_click_and_double_click(qtbot):
    c = cell_widget(qtbot, ("away", "socks"))
    clicked, chosen = [], []
    c.clicked.connect(clicked.append)
    c.choose_requested.connect(chosen.append)
    c.mousePressEvent(mouse(QEvent.MouseButtonPress, QPoint(5, 5)))
    c.mouseDoubleClickEvent(mouse(QEvent.MouseButtonDblClick, QPoint(5, 5)))
    assert clicked == [("away", "socks")] and chosen == [("away", "socks")]


class FakeDrag:
    started = []

    def __init__(self, source):
        self.source = source

    def setMimeData(self, mime):  # noqa: N802 (Qt name)
        self.mime = mime

    def setPixmap(self, pixmap):  # noqa: N802
        self.pixmap = pixmap

    def exec(self, action):
        FakeDrag.started.append((bytes(self.mime.data(CELL_MIME)).decode(), action))


def test_a_photo_is_dragged_once_the_mouse_moves_far_enough(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(photo_kit_dialog, "QDrag", FakeDrag)
    FakeDrag.started = []
    c = cell_widget(qtbot, ("third", "back"))
    far = QPoint(5 + 3 * QApplication.startDragDistance(), 5)
    c.mouseMoveEvent(mouse(QEvent.MouseMove, far))  # no photo
    c.show_photo(photo(tmp_path, "x.png"))
    c.mouseMoveEvent(mouse(QEvent.MouseMove, far))  # no press first
    c.mousePressEvent(mouse(QEvent.MouseButtonPress, QPoint(5, 5)))
    c.mouseMoveEvent(mouse(QEvent.MouseMove, QPoint(6, 5)))  # too short
    assert FakeDrag.started == []
    c.mouseMoveEvent(mouse(QEvent.MouseMove, far))
    c.mouseMoveEvent(mouse(QEvent.MouseMove, far))  # one drag per press
    assert FakeDrag.started == [("third/back", Qt.MoveAction)]


def test_the_menu_of_a_box(qtbot, tmp_path, monkeypatch):
    c = cell_widget(qtbot)
    chosen, cleared = [], []
    c.choose_requested.connect(chosen.append)
    c.clear_requested.connect(cleared.append)
    menu = c.context_menu()
    choose, remove = menu.actions()
    assert choose.text() == "Choose photo…" and not remove.isEnabled()
    choose.trigger()
    c.show_photo(photo(tmp_path, "x.png"))
    menu = c.context_menu()
    assert menu.actions()[1].isEnabled()
    menu.actions()[1].trigger()
    assert chosen == [("home", "shirt")] and cleared == [("home", "shirt")]
    shown = []

    class Menu:
        def exec(self, pos):
            shown.append(pos)

    monkeypatch.setattr(PhotoCell, "context_menu", lambda self: Menu())
    c.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Mouse, QPoint(3, 4), QPoint(30, 40)))
    assert shown == [QPoint(30, 40)]


def drag_enter(widget, mime):
    with warnings.catch_warnings():  # PySide marks this constructor deprecated, the one Qt 6 has
        warnings.simplefilter("ignore", DeprecationWarning)
        event = QDragEnterEvent(QPoint(5, 5), Qt.CopyAction | Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier)
    event.ignore()
    widget.dragEnterEvent(event)
    return event.isAccepted()


def drop(widget, mime):
    event = QDropEvent(QPointF(5, 5), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    widget.dropEvent(event)
    return event


def test_a_box_takes_photos_pictures_and_other_boxes(qtbot, tmp_path):
    c = cell_widget(qtbot, ("gk", "shorts"))
    p = photo(tmp_path, "a.png")
    assert drag_enter(c, mime_with(urls=[p]))
    assert drag_enter(c, mime_with(image=qimage()))
    assert drag_enter(c, mime_with(cell=("home", "shirt")))
    text = QMimeData()
    text.setText("hello")
    assert not drag_enter(c, text)
    dropped = []
    c.dropped.connect(lambda cell, what: dropped.append((cell, what)))
    drop(c, mime_with(urls=[p]))
    assert dropped == [(("gk", "shorts"), ("files", [p]))]


# --- the photos page ------------------------------------------------------------------------------------------------


def test_the_dialog_starts_with_the_photos_given(qtbot, tmp_path):
    p = photo(tmp_path, "home_1.png")
    d = make(qtbot, tmp_path, chosen={("home", "shirt"): p})
    assert d.windowTitle() == "Kits from photos: Crotone"
    assert d.cells[("home", "shirt")].path == p and d.make_button.isEnabled()
    assert d.status.text() == "Kits to make: Home."
    assert len(d.cells) == 16 and d.stack.currentIndex() == 0


def test_no_kit_to_make_without_a_shirt_photo(qtbot, tmp_path):
    d = make(qtbot, tmp_path, chosen={("home", "back"): photo(tmp_path, "b.png")})
    assert not d.make_button.isEnabled()
    assert d.status.text() == "Add the shirt photo of at least one kit."


def test_add_files_by_name_then_in_the_empty_boxes(qtbot, tmp_path):
    d = make(qtbot, tmp_path)
    away = photo(tmp_path, "away_1.png")
    other = photo(tmp_path, "IMG_001.jpg")
    notes = tmp_path / "notes.txt"
    notes.write_text("x")
    d.add_files([away, other, notes])
    assert d.chosen == {("away", "shirt"): away, ("home", "shirt"): other}
    assert d.status.text() == "Not a photo (PNG, JPEG or WebP): notes.txt."
    d.add_files([photo(tmp_path, "gk_socks.png")])
    assert d.status.text() == "Kits to make: Home, Away."


def test_a_photo_given_a_box_goes_there_whatever_its_name(qtbot, tmp_path):
    d = make(qtbot, tmp_path)
    away = photo(tmp_path, "away_1.png")
    d.add_files([away], ("third", "socks"))
    assert d.chosen == {("third", "socks"): away}


def test_photos_with_no_empty_box_left(qtbot, tmp_path):
    d = make(qtbot, tmp_path)
    d.add_files([photo(tmp_path, f"p{n:02}.png") for n in range(18)])
    assert len(d.chosen) == 16
    assert d.status.text() == "No empty box for: p16.png, p17.png."


def test_a_pasted_picture_is_saved_in_the_work_folder(qtbot, tmp_path):
    d = make(qtbot, tmp_path)
    d.add_image(Image.new("RGB", (30, 30), "red"), ("away", "back"))
    assert d.chosen == {("away", "back"): tmp_path / "work" / "pasted" / "pasted_1.png"}
    assert d.chosen[("away", "back")].is_file()


def test_select_one_box_at_a_time(qtbot, tmp_path):
    d = make(qtbot, tmp_path)
    d.select(("home", "back"))
    d.select(("gk", "socks"))
    assert d.selected == ("gk", "socks")
    assert "highlight" in d.cells[("gk", "socks")].styleSheet()
    assert "dashed" in d.cells[("home", "back")].styleSheet()
    d.cells[("away", "shorts")].clicked.emit(("away", "shorts"))
    assert d.selected == ("away", "shorts")


def test_drop_each_kind(qtbot, tmp_path):
    d = make(qtbot, tmp_path)
    p = photo(tmp_path, "x.png")
    d.drop(("home", "socks"), ("files", [p]))
    d.drop(("home", "shorts"), ("image", Image.new("RGB", (9, 9))))
    assert set(d.chosen) == {("home", "socks"), ("home", "shorts")}
    d.drop(("home", "socks"), ("cell", ("home", "shorts")))  # swapped
    assert d.chosen[("home", "shorts")] == p
    d.drop(None, ("remote", ["https://example.com/a.png"]))
    assert d.status.text().startswith("A web address, not a picture")
    before = dict(d.chosen)
    d.drop(("away", "shirt"), None)
    assert d.chosen == before


def test_move_a_photo_to_another_box(qtbot, tmp_path):
    a, b = photo(tmp_path, "a.png"), photo(tmp_path, "b.png")
    d = make(qtbot, tmp_path, chosen={("home", "shirt"): a, ("away", "shirt"): b})
    d.move(("home", "shirt"), ("away", "shirt"))
    assert d.chosen == {("away", "shirt"): a, ("home", "shirt"): b}
    d.move(("home", "shirt"), ("third", "shirt"))  # to an empty box
    assert d.chosen == {("away", "shirt"): a, ("third", "shirt"): b}
    d.move(("gk", "shirt"), ("away", "shirt"))  # from an empty box: the photo moves the other way
    assert d.chosen == {("gk", "shirt"): a, ("third", "shirt"): b}
    d.move(("gk", "shirt"), ("gk", "shirt"))
    d.move(("gk", "shirt"), None)  # dropped on the window, not on a box
    assert d.chosen == {("gk", "shirt"): a, ("third", "shirt"): b}


def test_remove_one_photo_or_all(qtbot, tmp_path):
    a, b = photo(tmp_path, "a.png"), photo(tmp_path, "b.png")
    d = make(qtbot, tmp_path, chosen={("home", "shirt"): a, ("away", "shirt"): b})
    d.cells[("home", "shirt")].clear_requested.emit(("home", "shirt"))
    assert d.chosen == {("away", "shirt"): b}
    d.empty_button.click()
    assert d.chosen == {} and d.cells[("away", "shirt")].path is None


def test_paste_into_the_box_clicked(qtbot, tmp_path):
    d = make(qtbot, tmp_path)
    QApplication.clipboard().clear()
    d.paste_button.click()
    assert d.status.text() == "Nothing to paste: copy a picture or a photo file first."
    d.select(("away", "socks"))
    QApplication.clipboard().setImage(qimage())
    d.paste()
    assert d.chosen == {("away", "socks"): tmp_path / "work" / "pasted" / "pasted_1.png"}
    p = photo(tmp_path, "home_1.png")
    QApplication.clipboard().setMimeData(mime_with(urls=[p]))
    d.paste()
    assert d.chosen[("away", "socks")] == p  # a single photo goes to the box clicked
    QApplication.clipboard().clear()


def test_photos_dropped_on_the_window(qtbot, tmp_path):
    d = make(qtbot, tmp_path)
    p = photo(tmp_path, "back_away.png")
    assert drag_enter(d, mime_with(urls=[p]))
    assert drag_enter(d, mime_with(image=qimage()))
    assert not drag_enter(d, mime_with(cell=("home", "shirt")))
    drop(d, mime_with(urls=[p]))
    assert d.chosen == {("away", "back"): p}


def test_choose_files_a_folder_or_a_photo_for_a_box(qtbot, tmp_path, monkeypatch):
    d = make(qtbot, tmp_path)
    shots = tmp_path / "shots"
    home, away = photo(shots, "home_1.png"), photo(shots, "away_1.png")
    (shots / "readme.txt").write_text("x")
    answers = {"files": ([], ""), "folder": "", "file": ("", "")}
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *a: answers["files"])
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a: answers["folder"])
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: answers["file"])
    d.add_files_button.click()
    d.add_folder_button.click()
    d.choose_for(("gk", "shirt"))
    assert d.chosen == {}
    answers.update(files=([str(home)], "Photos"), folder=str(shots), file=(str(away), "Photos"))
    d.add_files_button.click()
    assert d.chosen == {("home", "shirt"): home}
    d.remove(("home", "shirt"))
    d.add_folder_button.click()
    assert d.chosen == {("home", "shirt"): home, ("away", "shirt"): away}
    d.cells[("gk", "shirt")].choose_requested.emit(("gk", "shirt"))
    assert d.chosen[("gk", "shirt")] == away


# --- making the kits and the result ---------------------------------------------------------------------------------


def texture(folder: Path, name: str, colour) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    Image.new("RGB", (512, 512), colour).save(p)
    return p


def made_team(tmp_path, slots=("p1", "p2"), missing=(), notes=("maker: maker_1 (new in the cache)",)):
    textures = {s: texture(tmp_path / "work", f"{s}.png", (20 * n, 0, 0)) for n, s in enumerate(slots)}
    return MadeTeam(tmp_path / "work", textures, "maker_1", True, list(missing), list(notes))


def test_make_kits_shows_them_next_to_the_kits_now(qtbot, tmp_path):
    asked = []
    result = made_team(tmp_path, missing=["third", "gk"])

    def make_kits(chosen, tones):
        asked.append((chosen, tones))
        return result

    p = photo(tmp_path, "home_1.png")
    current = {"p1": lambda view: Image.new("RGB", (400, 600), "blue")}
    d = make(qtbot, tmp_path, make_kits, current, {("home", "shirt"): p})
    d.make_button.click()
    assert asked == [({("home", "shirt"): p}, {})]
    assert d.made is result and d.stack.currentIndex() == 1 and d.make_button.isEnabled()
    assert d.result_title.text() == "Kits made: Home, Away. Add them to the changes to install them with Deploy."
    assert d.notes.text() == "maker: maker_1 (new in the cache)\nNo shirt photo: Third, Goalkeeper."
    texts = [d.result_grid.itemAt(i).widget().text() for i in range(d.result_grid.count())]
    assert texts[:3] == ["<b></b>", "<b>Current</b>", "<b>New</b>"]
    assert "Home" in texts and "Away" in texts and "No kit now" in texts
    pictures = [d.result_grid.itemAt(i).widget() for i in range(d.result_grid.count())]
    assert sum(1 for w in pictures if not w.pixmap().isNull()) == 3  # Home now, Home new, Away new
    assert max(w.pixmap().width() for w in pictures) <= photo_kit_dialog.PICTURE
    assert d.view_photos_button.text() == "View photos"
    d.view_photos_button.click()
    assert d.stack.currentIndex() == 0


def pictures(d):
    return [w.pixmap() for w in (d.result_grid.itemAt(i).widget() for i in range(d.result_grid.count()))]


def test_the_kits_folded_or_unrolled(qtbot, tmp_path):
    asked = []

    def now(view):
        asked.append(view)
        return Image.new("RGB", (400, 600) if view == "folded" else (320, 320), "blue")

    d = make(
        qtbot, tmp_path, lambda c, t: made_team(tmp_path), {"p1": now}, {("home", "shirt"): photo(tmp_path, "h.png")}
    )
    d.make_kits()
    assert d.folded_button.isChecked() and asked == ["folded"]
    folded = [p.size().toTuple() for p in pictures(d) if not p.isNull()]
    d.unrolled_button.click()
    unrolled = [p.size().toTuple() for p in pictures(d) if not p.isNull()]
    assert asked == ["folded", "unrolled"] and unrolled != folded and (300, 300) in unrolled
    d.folded_button.click()
    assert asked[-1] == "folded" and d.view == "folded"


def test_the_kits_start_in_the_view_given(qtbot, tmp_path):
    d = make(qtbot, tmp_path, view="unrolled")
    assert d.unrolled_button.isChecked() and not d.folded_button.isChecked()


def test_a_kit_now_that_cannot_be_read(qtbot, tmp_path):
    def broken(view):
        raise ValueError("damaged texture")

    d = make(
        qtbot, tmp_path, lambda c, t: made_team(tmp_path), {"p1": broken}, {("home", "shirt"): photo(tmp_path, "h.png")}
    )
    d.make_kits()
    texts = [d.result_grid.itemAt(i).widget().text() for i in range(d.result_grid.count())]
    assert "Cannot read the kit now" in texts


def test_view_kits_shows_the_kits_made_without_making_them_again(qtbot, tmp_path):
    made = []
    chosen = {("home", "shirt"): photo(tmp_path, "h.png")}
    d = make(qtbot, tmp_path, lambda c, t: made.append(1) or made_team(tmp_path), chosen=chosen)
    assert not d.view_kits_button.isEnabled()  # nothing made yet
    d.make_kits()
    d.view_photos_button.click()
    assert d.view_kits_button.isEnabled()
    d.view_kits_button.click()
    assert d.stack.currentIndex() == 1 and made == [1]


def test_the_kits_made_last_time_can_be_viewed(qtbot, tmp_path):
    before = made_team(tmp_path, notes=())
    d = make(qtbot, tmp_path, chosen={("home", "shirt"): photo(tmp_path, "h.png")}, made=before)
    assert d.stack.currentIndex() == 0 and d.view_kits_button.isEnabled() and d.made is before
    d.view_kits_button.click()
    assert d.stack.currentIndex() == 1 and d.result_title.text().startswith("Kits made: Home, Away.")


def test_making_again_replaces_the_result(qtbot, tmp_path):
    results = [made_team(tmp_path), made_team(tmp_path, slots=("p1",), notes=())]
    d = make(qtbot, tmp_path, lambda c, t: results.pop(0), chosen={("home", "shirt"): photo(tmp_path, "h.png")})
    d.make_kits()
    d.make_kits()
    qtbot.wait(10)  # the old pictures are deleted later
    assert d.result_title.text().startswith("Kits made: Home.")
    assert d.notes.text() == ""
    assert d.result_grid.count() == 3 + 3


def test_a_failure_is_shown_and_the_photos_stay(qtbot, tmp_path):
    def broken(chosen, tones):
        raise RuntimeError("the game has no crest for team 1")

    d = make(qtbot, tmp_path, broken, chosen={("home", "shirt"): photo(tmp_path, "h.png")})
    d.make_kits()
    assert d.status.text() == "The kits could not be made: the game has no crest for team 1"
    assert d.stack.currentIndex() == 0 and d.make_button.isEnabled() and d.made is None


def test_add_to_changes_accepts_cancel_rejects(qtbot, tmp_path):
    d = make(qtbot, tmp_path, lambda c, t: made_team(tmp_path), chosen={("home", "shirt"): photo(tmp_path, "h.png")})
    d.make_kits()
    d.add_button.click()
    assert d.result() == PhotoKitDialog.Accepted
    d = make(qtbot, tmp_path)
    d.reject()
    assert d.result() == PhotoKitDialog.Rejected


def test_the_kits_are_made_in_a_thread_by_default(qtbot, tmp_path):
    d = PhotoKitDialog(
        "Crotone", tmp_path, lambda c, t: made_team(tmp_path), {}, {("home", "shirt"): tmp_path / "h.png"}
    )
    qtbot.addWidget(d)
    d.make_kits()
    assert not d.make_button.isEnabled()
    assert d.status.text() == "Making the kits from the photos… (about a minute)"
    qtbot.waitUntil(lambda: d.stack.currentIndex() == 1)


def test_clear_deletes_the_work_folder_after_asking(qtbot, tmp_path, monkeypatch):
    own = photo(tmp_path / "mine", "home_1.png")  # the user's own photo, outside the work folder
    kept = photo(tmp_path / "work" / "ref", "away_1.png")
    d = make(qtbot, tmp_path, chosen={("home", "shirt"): own, ("away", "shirt"): kept})
    asked, answer = [], [QMessageBox.No]
    monkeypatch.setattr(QMessageBox, "question", lambda parent, title, text, *a: asked.append(text) or answer[0])
    d.clear_button.click()
    assert kept.is_file() and len(d.chosen) == 2
    assert str(tmp_path / "work") in asked[0] and "cannot be undone" in asked[0]
    answer[0] = QMessageBox.Yes
    d.clear_button.click()
    assert not (tmp_path / "work").exists() and own.is_file()
    assert d.chosen == {} and d.status.text() == "The photos kept for this team were deleted."
    d.clear_button.click()  # nothing left to delete
    assert d.chosen == {} and d.made is None and not d.view_kits_button.isEnabled()


def test_every_button_has_a_tooltip(qtbot, tmp_path):
    d = make(qtbot, tmp_path)
    assert buttons_without_tooltip(d) == []
    assert all(box.toolTip() for box in d.cells.values())  # the boxes too, before they have a photo


def test_each_kit_takes_its_colours_from_the_front_or_the_back_photo(qtbot, tmp_path):
    asked = []
    chosen = {("away", "shirt"): photo(tmp_path, "a.png")}
    d = make(
        qtbot, tmp_path, lambda c, t: asked.append(t) or made_team(tmp_path), chosen=chosen, tones={"away": "back"}
    )
    assert [d.tone_boxes[k].currentText() for k in ("home", "away")] == ["Auto", "From the back"]
    assert all(box.toolTip() for box in d.tone_boxes.values())
    d.tone_boxes["home"].setCurrentIndex(1)
    assert d.tones() == {"home": "front", "away": "back"}
    d.make_kits()
    d.tone_boxes["away"].setCurrentIndex(0)
    d.make_kits()
    assert asked == [{"home": "front", "away": "back"}, {"home": "front"}]
