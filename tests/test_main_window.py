import flkm
from flkm.main_window import MainWindow


def test_title_has_name_and_version(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    assert w.windowTitle() == f"FL Kits Manager {flkm.__version__}"


def test_window_is_large_enough_for_the_team_list_and_kits(qtbot):
    w = MainWindow()
    qtbot.addWidget(w)
    assert w.minimumWidth() >= 1000 and w.minimumHeight() >= 650
