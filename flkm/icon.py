"""The app's icon: flkm.ico, made from the logo docs/images/flkm-logo.svg (run `python -m flkm.icon` after changing
the logo). It is the icon of the exe (scripts/build.ps1, --icon) and of the app's windows (cli.py)."""

from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ICON = Path(__file__).with_name("flkm.ico")
LOGO = Path(__file__).resolve().parents[1] / "docs" / "images" / "flkm-logo.svg"
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]  # the sizes Windows shows


def render_svg(svg: Path, size: int) -> Image.Image:
    """The SVG drawn on a transparent size x size picture."""
    image = QImage(size, size, QImage.Format_RGBA8888)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    QSvgRenderer(str(svg)).render(painter)
    painter.end()
    return Image.frombytes("RGBA", (size, size), bytes(image.constBits()))


def write_icon(svg: Path, ico: Path) -> None:
    """An .ico with every size in SIZES, from the SVG drawn at 256 pixels."""
    render_svg(svg, 256).save(ico, sizes=SIZES)


def app_icon() -> QIcon:
    return QIcon(str(ICON))


if __name__ == "__main__":
    write_icon(LOGO, ICON)
    print(f"written {ICON}")
