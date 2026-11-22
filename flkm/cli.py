"""Command line of the exe: opens the main window (on the game folder of `--game`, else the remembered one);
`--smoke-test` quits at once (CI checks the bundle starts)."""

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from flkm.main_window import APP_NAME, MainWindow


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="FLKitsManager")
    p.add_argument("--smoke-test", action="store_true", help="open the main window and quit at once")
    p.add_argument("--game", help="folder of SP Football Life 2027 (else the one chosen last time)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None, app: QApplication | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    app = app or QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    window = MainWindow(game_dir=Path(args.game) if args.game else None)
    window.show()
    if args.smoke_test:
        QTimer.singleShot(0, app.quit)
    code = app.exec()
    window.close()
    return code
