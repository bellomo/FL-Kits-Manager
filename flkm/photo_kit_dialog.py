"""The Kits from photos dialog: the photos of a team's kits, the kits made from them, and a comparison with the kits the
team wears now before they are added to the changes.

Photos come in every way: Add photos… (files), Add folder…, dragged in from Explorer or a browser, or pasted (Ctrl+V,
a copied file or picture). A photo named as the kit tools name them (home_1.png, back_home.png, away_shorts.png, h1.jpg)
goes to its box; the others go to the box chosen (dropped on, or clicked before pasting) or to the first empty one. A
photo can be dragged to another box (the two swap), replaced by a double click, or removed (right click).
The kits are made in the background (about a minute); nothing is staged before Add to changes. Clear
deletes the team's work folder (the copies of the photos, the logos cut from them, the kits made), after asking.
"""

import io
import shutil
import threading
from collections.abc import Callable
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMimeData, QObject, QPoint, Qt, Signal
from PySide6.QtGui import QDrag, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from flkm import render
from flkm.game.kits import slot_name
from flkm.photokit.photo import EXTENSIONS
from flkm.photokit.team import PARTS, SLOTS, photos_in_folder, place_photos, save_pasted
from flkm.team_page import UNROLLED, to_pixmap

KIT_NAMES = {kit: slot_name(slot) for kit, slot in SLOTS.items()}
PART_NAMES = {"shirt": "Shirt (front)", "back": "Shirt (back)", "shorts": "Shorts", "socks": "Socks"}
CELL_MIME = "application/x-flkm-photo-cell"  # a photo dragged from one box to another
THUMB = 112  # photo boxes, pixels
PICTURE = 300  # width of the kit pictures of the comparison
PHOTO_FILTER = "Photos (" + " ".join(f"*{e}" for e in EXTENSIONS) + ")"
HELP = (
    "One photo per box: the shirt from the front and from the back, the shorts, the socks. Add photos or a folder "
    "(photos named home_1.png, back_home.png, away_shorts.png... go to their box), drag pictures here, or copy one "
    "and paste it (Ctrl+V) into the box you clicked. Drag a photo to another box to move it; right click to remove "
    "it. A kit needs at least the shirt from the front."
)
TONE_NAMES = {"auto": "Auto", "front": "From the front", "back": "From the back"}  # see pattern.read_kit_pattern
TONE_HELP = (
    "Which photo gives the kit's colours when the front and the back photos come from different sites and show the "
    "same colours in two tones. Auto: a back of another colour is kept (a kit really in two colours). From the front "
    "/ From the back: the kit is the colours of that photo, front and back."
)
SELECTED = "border: 2px solid palette(highlight);"
NORMAL = "border: 1px dashed gray;"


def pil_image(image: QImage) -> Image.Image:
    """A QImage (pasted or dropped) as a PIL image."""
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "PNG")
    buf.close()
    return Image.open(io.BytesIO(bytes(data))).convert("RGBA")


def read_mime(mime: QMimeData):
    """What was dropped or pasted: ("cell", (kit, part)) a photo from another box, ("files", [paths]) local files,
    ("image", PIL image) a picture, ("remote", [urls]) web addresses only, or None."""
    if mime.hasFormat(CELL_MIME):
        kit, part = bytes(mime.data(CELL_MIME)).decode().split("/")
        return "cell", (kit, part)
    local = [Path(u.toLocalFile()) for u in mime.urls() if u.isLocalFile()]
    if local:
        return "files", local
    if mime.hasImage():
        return "image", pil_image(QImage(mime.imageData()))
    if mime.urls():
        return "remote", [u.toString() for u in mime.urls()]
    return None


class _Job(QObject):
    done = Signal(object)
    failed = Signal(str)


_jobs: set[_Job] = set()  # jobs running, kept alive until they end


def run_in_thread(work: Callable[[], object], on_done: Callable, on_error: Callable) -> None:
    """Runs work in a thread; on_done(result) or on_error(message) is called in the window's thread."""
    job = _Job()
    _jobs.add(job)
    job.done.connect(on_done)
    job.failed.connect(on_error)
    job.done.connect(lambda _: _jobs.discard(job))
    job.failed.connect(lambda _: _jobs.discard(job))

    def target():
        try:
            job.done.emit(work())
        except Exception as e:  # noqa: BLE001 (any failure of the job is shown to the user)
            job.failed.emit(str(e) or type(e).__name__)

    threading.Thread(target=target, daemon=True).start()


class PhotoCell(QFrame):
    """One box: the photo of a part of a kit, a drop target, a drag source."""

    dropped = Signal(object, object)  # cell, read_mime(...) result
    clicked = Signal(object)
    choose_requested = Signal(object)
    clear_requested = Signal(object)

    def __init__(self, cell: tuple[str, str], parent: QWidget | None = None):
        super().__init__(parent)
        self.cell = cell
        self.path: Path | None = None
        self._press: QPoint | None = None
        self.setAcceptDrops(True)
        self.setFixedSize(THUMB + 8, THUMB + 8)
        self.picture = QLabel(alignment=Qt.AlignCenter)
        self.picture.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self.picture)
        self.set_selected(False)
        self.show_photo(None)

    def set_selected(self, on: bool) -> None:
        self.setStyleSheet(f"PhotoCell {{ {SELECTED if on else NORMAL} }}")

    def show_photo(self, path: Path | None) -> None:
        self.path = path
        self.setToolTip(str(path) if path else "Drop or paste a photo here, or double-click to choose one")
        if path is None:
            self.picture.setPixmap(QPixmap())
            self.picture.setText("Drop, paste\nor double-click")
            self.picture.setStyleSheet("color: gray")
            return
        try:
            with Image.open(path) as im:
                thumb = im.convert("RGBA")
        except OSError:
            self.picture.setText(f"Cannot read\n{path.name}")
            return
        thumb.thumbnail((THUMB, THUMB))
        self.picture.setText("")
        self.picture.setPixmap(to_pixmap(thumb, alpha=True))

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt name)
        self._press = event.position().toPoint()
        self.clicked.emit(self.cell)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.choose_requested.emit(self.cell)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self.path is None or self._press is None:
            return
        if (event.position().toPoint() - self._press).manhattanLength() < QApplication.startDragDistance():
            return
        self._press = None
        mime = QMimeData()
        mime.setData(CELL_MIME, QByteArray("/".join(self.cell).encode()))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.picture.pixmap())
        drag.exec(Qt.MoveAction)

    def context_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction("Choose photo…", lambda: self.choose_requested.emit(self.cell))
        remove = menu.addAction("Remove photo", lambda: self.clear_requested.emit(self.cell))
        remove.setEnabled(self.path is not None)
        return menu

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        self.context_menu().exec(event.globalPos())

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        mime = event.mimeData()
        if mime.hasFormat(CELL_MIME) or mime.hasUrls() or mime.hasImage():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        self.dropped.emit(self.cell, read_mime(event.mimeData()))
        event.acceptProposedAction()


class PhotoKitDialog(QDialog):
    def __init__(
        self,
        team_name: str,
        folder: Path,
        make: Callable[[dict, dict], object],
        current: dict,
        chosen: dict | None = None,
        tones: dict | None = None,
        run: Callable = run_in_thread,
        parent: QWidget | None = None,
        view: str = "folded",
        made=None,
    ):
        """folder: the team's work folder (pasted pictures go there); make(chosen, tones) -> MadeTeam, run in the
        background by run(work, on_done, on_error); current: slot -> view ("folded" or "unrolled") -> picture of the
        kit the team wears now (raises ValueError or OSError when it cannot be read); view: how the kits
        are shown first; made: the kits made last time (team.made_before), to view without making them again; chosen:
        (kit, part) -> photo to start with; tones: kit -> "front" or "back", the photo that gives its colours."""
        super().__init__(parent)
        self.setWindowTitle(f"Kits from photos: {team_name}")
        self.resize(820, 760)
        self.setAcceptDrops(True)
        self.folder = Path(folder)
        self.make = make
        self.run = run
        self.current = current
        self.chosen: dict = {}
        self.selected: tuple[str, str] | None = None
        self.made = None
        self.view = view

        self.stack = QStackedWidget()
        self.stack.addWidget(self._photos_page())
        self.stack.addWidget(self._result_page())
        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)
        QShortcut(QKeySequence.Paste, self, activated=self.paste)
        self.set_chosen(dict(chosen or {}))
        for kit, tone in (tones or {}).items():
            box = self.tone_boxes[kit]
            box.setCurrentIndex(box.findData(tone))
        if made is not None:
            self.show_result(made)
            self.stack.setCurrentIndex(0)  # the photos first; View kits shows them

    # --- the photos ---------------------------------------------------------------------------------------------

    def _photos_page(self) -> QWidget:
        page = QWidget()
        help_text = QLabel(HELP)
        help_text.setWordWrap(True)
        self.add_files_button = QPushButton("Add photos…")
        self.add_files_button.setToolTip("Choose photo files: named ones go to their box, the others to empty boxes")
        self.add_folder_button = QPushButton("Add folder…")
        self.add_folder_button.setToolTip(
            "Add every photo of a folder: named ones go to their box, the others to the empty boxes"
        )
        self.paste_button = QPushButton("Paste")
        self.paste_button.setToolTip("Paste a copied picture or file into the box you clicked (Ctrl+V)")
        self.empty_button = QPushButton("Remove all")
        self.empty_button.setToolTip(
            "Empty the boxes; the copies of the photos the app keeps for this team stay until Clear or the next "
            "Make kits"
        )
        self.clear_button = QPushButton("Clear")
        self.clear_button.setToolTip(
            "Delete the copies of the photos the app keeps for this team, the pictures pasted, the logos cut from them "
            "and the kits made (after asking; it cannot be undone). Your own photo files are not touched."
        )
        self.add_files_button.clicked.connect(self.choose_files)
        self.add_folder_button.clicked.connect(self.choose_folder)
        self.paste_button.clicked.connect(self.paste)
        self.empty_button.clicked.connect(lambda: self.set_chosen({}))
        self.clear_button.clicked.connect(self.clear)
        tools = QHBoxLayout()
        for b in (self.add_files_button, self.add_folder_button, self.paste_button, self.empty_button):
            tools.addWidget(b)
        tools.addStretch()
        tools.addWidget(self.clear_button)
        grid = QGridLayout()
        for col, part in enumerate(PARTS, 1):
            grid.addWidget(QLabel(PART_NAMES[part], alignment=Qt.AlignCenter), 0, col)
        self.cells: dict[tuple[str, str], PhotoCell] = {}
        for row, kit in enumerate(SLOTS, 1):
            grid.addWidget(QLabel(KIT_NAMES[kit]), row, 0)
            for col, part in enumerate(PARTS, 1):
                cell = PhotoCell((kit, part))
                cell.clicked.connect(self.select)
                cell.dropped.connect(self.drop)
                cell.choose_requested.connect(self.choose_for)
                cell.clear_requested.connect(self.remove)
                self.cells[(kit, part)] = cell
                grid.addWidget(cell, row, col)
        grid.addWidget(QLabel("Colours", alignment=Qt.AlignCenter), 0, len(PARTS) + 1)
        self.tone_boxes: dict[str, QComboBox] = {}
        for row, kit in enumerate(SLOTS, 1):
            box = QComboBox()
            for tone, name in TONE_NAMES.items():
                box.addItem(name, tone)
            box.setToolTip(TONE_HELP)
            self.tone_boxes[kit] = box
            grid.addWidget(box, row, len(PARTS) + 1)
        grid.setColumnStretch(len(PARTS) + 2, 1)  # the boxes stay together on the left
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.view_kits_button = QPushButton("View kits")
        self.view_kits_button.setToolTip(
            "See the kits made last, without making them again (Make kits again after changing the photos)"
        )
        self.view_kits_button.setEnabled(False)
        self.view_kits_button.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.make_button = QPushButton("Make kits")
        self.make_button.setToolTip("Make the kits from the photos (about a minute) and compare them with the ones now")
        self.make_button.setDefault(True)
        self.make_button.clicked.connect(self.make_kits)
        cancel = QPushButton("Cancel")
        cancel.setToolTip("Close without adding any kit (the photos stay for next time)")
        cancel.clicked.connect(self.reject)
        bottom = QHBoxLayout()
        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.view_kits_button)
        bottom.addWidget(self.make_button)
        bottom.addWidget(cancel)
        layout = QVBoxLayout(page)
        layout.addWidget(help_text)
        layout.addLayout(tools)
        layout.addLayout(grid)
        layout.addStretch()
        layout.addLayout(bottom)
        return page

    def set_chosen(self, chosen: dict) -> None:
        self.chosen = chosen
        for cell, box in self.cells.items():
            if box.path != chosen.get(cell):
                box.show_photo(chosen.get(cell))
        shirts = [KIT_NAMES[k] for k in SLOTS if (k, "shirt") in chosen]
        self.make_button.setEnabled(bool(shirts))
        self.set_status(f"Kits to make: {', '.join(shirts)}." if shirts else "Add the shirt photo of at least one kit.")

    def tones(self) -> dict[str, str]:
        """kit -> "front" or "back" for the kits whose colours come from one photo (the others: auto)."""
        tones = {kit: box.currentData() for kit, box in self.tone_boxes.items()}
        return {kit: tone for kit, tone in tones.items() if tone != "auto"}

    def set_status(self, text: str) -> None:
        self.status.setText(text)

    def select(self, cell: tuple[str, str]) -> None:
        if self.selected:
            self.cells[self.selected].set_selected(False)
        self.selected = cell
        self.cells[cell].set_selected(True)

    def add_files(self, paths: list, cell: tuple[str, str] | None = None) -> None:
        """Adds photos: one photo given a box goes there, the others by name or to the first empty boxes."""
        photos = [Path(p) for p in paths if Path(p).suffix.lower() in EXTENSIONS]
        skipped = [Path(p).name for p in paths if Path(p).suffix.lower() not in EXTENSIONS]
        if cell and len(photos) == 1:
            chosen, left = {**self.chosen, cell: photos[0]}, []
        else:
            chosen, left = place_photos(photos, self.chosen)
        self.set_chosen(chosen)
        notes = []
        if skipped:
            notes.append(f"Not a photo (PNG, JPEG or WebP): {', '.join(skipped)}.")
        if left:
            notes.append(f"No empty box for: {', '.join(p.name for p in left)}.")
        if notes:
            self.set_status(" ".join(notes))

    def add_image(self, image: Image.Image, cell: tuple[str, str] | None = None) -> None:
        """A pasted or dropped picture: saved in the work folder, then added like a file."""
        self.add_files([save_pasted(image, self.folder)], cell)

    def drop(self, cell, what) -> None:
        kind, value = what if what else (None, None)
        if kind == "cell":
            self.move(value, cell)
        elif kind == "files":
            self.add_files(value, cell)
        elif kind == "image":
            self.add_image(value, cell)
        elif kind == "remote":
            self.set_status("A web address, not a picture: save the picture first, or copy it and paste it here.")

    def move(self, source: tuple[str, str], target: tuple[str, str] | None) -> None:
        """Moves a photo to another box; the photo there goes to the box it came from."""
        if target is None or source == target:
            return
        chosen = dict(self.chosen)
        a, b = chosen.pop(source, None), chosen.pop(target, None)
        if a:
            chosen[target] = a
        if b:
            chosen[source] = b
        self.set_chosen(chosen)

    def remove(self, cell: tuple[str, str]) -> None:
        self.set_chosen({k: v for k, v in self.chosen.items() if k != cell})

    def clear(self) -> None:
        """Deletes the team's work folder (the photos copied there, pasted pictures, logos cut, kits made) after
        asking; the user's own photo files elsewhere stay."""
        question = (
            "Delete the photos the app keeps for this team, with the logos cut from them and the kits made?\n\n"
            f"{self.folder}\n\nYour own photo files elsewhere are not touched. This cannot be undone."
        )
        if QMessageBox.question(self, "Clear", question) != QMessageBox.Yes:
            return
        shutil.rmtree(self.folder, ignore_errors=True)
        self.set_chosen({})
        self.made = None
        self.view_kits_button.setEnabled(False)
        self.set_status("The photos kept for this team were deleted.")

    def paste(self) -> None:
        mime = QApplication.clipboard().mimeData()  # None when the clipboard is empty
        what = read_mime(mime) if mime is not None else None
        if what is None:
            self.set_status("Nothing to paste: copy a picture or a photo file first.")
            return
        self.drop(self.selected, what)

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt name)
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        self.drop(None, read_mime(event.mimeData()))
        event.acceptProposedAction()

    def choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Photos of the kits", "", PHOTO_FILTER)
        if paths:
            self.add_files(paths)

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Folder with the photos of the kits")
        if folder:
            self.add_files(photos_in_folder(folder))

    def choose_for(self, cell: tuple[str, str]) -> None:
        kit, part = cell
        path, _ = QFileDialog.getOpenFileName(self, f"{KIT_NAMES[kit]}: {PART_NAMES[part]}", "", PHOTO_FILTER)
        if path:
            self.add_files([path], cell)

    # --- making the kits ----------------------------------------------------------------------------------------

    def make_kits(self) -> None:
        self.make_button.setEnabled(False)
        self.set_status("Making the kits from the photos… (about a minute)")
        chosen, tones = dict(self.chosen), self.tones()
        self.run(lambda: self.make(chosen, tones), self.show_result, self.make_failed)

    def make_failed(self, message: str) -> None:
        self.make_button.setEnabled(True)
        self.set_status(f"The kits could not be made: {message}")

    # --- the result ---------------------------------------------------------------------------------------------

    def _result_page(self) -> QWidget:
        page = QWidget()
        self.result_title = QLabel()
        self.result_grid = QGridLayout()
        self.result_grid.setColumnStretch(3, 1)
        self.result_grid.setRowStretch(len(SLOTS) + 1, 1)
        inner = QWidget()
        inner.setLayout(self.result_grid)
        scroll = QScrollArea(widgetResizable=True)
        scroll.setWidget(inner)
        self.notes = QLabel()
        self.notes.setWordWrap(True)
        self.notes.setStyleSheet("color: gray")
        self.view_photos_button = QPushButton("View photos")
        self.view_photos_button.setToolTip(
            "See the photos again, to change them and make the kits again (View kits comes back here)"
        )
        self.folded_button = QPushButton("Folded", checkable=True)
        self.folded_button.setToolTip("Show each kit folded, front and back, as in the game")
        self.unrolled_button = QPushButton("Unrolled", checkable=True)
        self.unrolled_button.setToolTip("Show each kit's texture as it is, unrolled")
        group = QButtonGroup(page)
        for b in (self.folded_button, self.unrolled_button):
            group.addButton(b)
        (self.folded_button if self.view == "folded" else self.unrolled_button).setChecked(True)
        self.folded_button.clicked.connect(lambda: self.set_view("folded"))
        self.unrolled_button.clicked.connect(lambda: self.set_view("unrolled"))
        top = QHBoxLayout()
        top.addWidget(self.result_title, 1)
        top.addWidget(self.folded_button)
        top.addWidget(self.unrolled_button)
        self.add_button = QPushButton("Add to changes")
        self.add_button.setToolTip("Add the new kits to the changes (installed by Deploy)")
        self.add_button.setDefault(True)
        cancel = QPushButton("Cancel")
        cancel.setToolTip("Close without adding the new kits (the photos stay for next time)")
        self.view_photos_button.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.add_button.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        bottom = QHBoxLayout()
        bottom.addWidget(self.view_photos_button)
        bottom.addStretch()
        bottom.addWidget(self.add_button)
        bottom.addWidget(cancel)
        layout = QVBoxLayout(page)
        layout.addLayout(top)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.notes)
        layout.addLayout(bottom)
        return page

    def _now(self, slot: str) -> QLabel:
        """the kit the team wears now, in the view chosen"""
        if slot not in self.current:
            return self._text("No kit now")
        try:
            return self._picture(self.current[slot](self.view))
        except (ValueError, OSError):  # damaged texture or archive
            return self._text("Cannot read the kit now")

    def _new(self, png: Path) -> QLabel:
        with Image.open(png) as im:
            rgb = im.convert("RGB")
        return self._picture(render.folded(rgb) if self.view == "folded" else render.unrolled(rgb, UNROLLED))

    def _text(self, text: str) -> QLabel:
        label = QLabel(text, alignment=Qt.AlignCenter)
        label.setStyleSheet("color: gray")
        return label

    def _picture(self, image: Image.Image) -> QLabel:
        label = QLabel(alignment=Qt.AlignCenter)
        image = image.copy()
        image.thumbnail((PICTURE, PICTURE * 2))
        label.setPixmap(to_pixmap(image))
        return label

    def set_view(self, view: str) -> None:
        self.view = view
        self.draw_kits()

    def draw_kits(self) -> None:
        """the kits now and the kits made, side by side, in the view chosen"""
        while self.result_grid.count():
            old = self.result_grid.takeAt(0).widget()
            old.hide()  # at once: deleteLater waits for the event loop
            old.deleteLater()
        for col, text in enumerate(("", "Current", "New"), 0):
            self.result_grid.addWidget(QLabel(f"<b>{text}</b>", alignment=Qt.AlignCenter), 0, col)
        for row, (slot, png) in enumerate(self.made.textures.items(), 1):
            self.result_grid.addWidget(QLabel(slot_name(slot)), row, 0)
            self.result_grid.addWidget(self._now(slot), row, 1)
            self.result_grid.addWidget(self._new(png), row, 2)

    def show_result(self, made) -> None:
        self.made = made
        self.make_button.setEnabled(True)
        self.view_kits_button.setEnabled(True)
        self.draw_kits()
        made_names = ", ".join(slot_name(s) for s in made.textures)
        self.result_title.setText(f"Kits made: {made_names}. Add them to the changes to install them with Deploy.")
        missing = ", ".join(KIT_NAMES[k] for k in made.missing)
        notes = list(made.notes) + ([f"No shirt photo: {missing}."] if missing else [])
        self.notes.setText("\n".join(notes))
        self.set_status("")
        self.stack.setCurrentIndex(1)
