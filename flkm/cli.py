"""Command line of the exe: opens the main window; `--smoke-test` quits at once (CI checks the bundle starts)."""

import argparse
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from flkm.main_window import APP_NAME, MainWindow


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="FLKitsManager")
    p.add_argument("--smoke-test", action="store_true", help="open the main window and quit at once")
    return p.parse_args(argv)


def main(argv: list[str] | None = None, app: QApplication | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    app = app or QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    if args.smoke_test:
        QTimer.singleShot(0, app.quit)
    code = app.exec()
    window.close()
    return code
