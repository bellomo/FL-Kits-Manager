"""Entry point: `--smoke-test` opens the main window and quits with exit code 0 (CI runs the built exe with it to
prove the bundle starts)."""

import sys

from PySide6.QtCore import QTimer

from flkm import cli
from flkm.main_window import MainWindow


def test_no_arguments_opens_the_window_without_quitting():
    assert cli.parse_args([]).smoke_test is False


def test_smoke_test_flag():
    assert cli.parse_args(["--smoke-test"]).smoke_test is True


def test_game_folder_option():
    assert cli.parse_args([]).game is None
    assert cli.parse_args(["--game", "D:\\FL27"]).game == "D:\\FL27"


def test_game_folder_is_opened_in_the_window(qapp, game, monkeypatch):
    opened = []
    monkeypatch.setattr(cli, "MainWindow", lambda game_dir: opened.append(game_dir) or MainWindow())
    assert cli.main(["--smoke-test", "--game", str(game)], app=qapp) == 0
    assert opened == [game]


def test_smoke_test_opens_the_window_and_exits_with_0(qapp):
    assert cli.main(["--smoke-test"], app=qapp) == 0


def test_main_reads_sys_argv_by_default(qapp, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["FLKitsManager.exe", "--smoke-test"])
    assert cli.main(app=qapp) == 0


def test_without_the_flag_the_window_stays_open_until_the_user_quits(qapp):
    QTimer.singleShot(0, qapp.quit)  # the user closing the app
    assert cli.main([], app=qapp) == 0


def test_main_creates_the_application_when_there_is_none(qapp, monkeypatch):
    created = []

    class NoApp:
        @staticmethod
        def instance():
            return None

        def __new__(cls, argv):
            created.append(argv)
            return qapp

    monkeypatch.setattr(cli, "QApplication", NoApp)
    assert cli.main(["--smoke-test"]) == 0
    assert created == [sys.argv[:1]]
