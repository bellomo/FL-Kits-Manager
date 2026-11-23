"""The deploy history: every deploy, newest first, installed or undone; go back to before one, re-apply an undone one,
clear the ones chosen (a deploy still installed takes the older installed ones with it)."""

from PySide6.QtCore import Qt

from conftest import buttons_without_tooltip
from flkm.deploy import Deployment
from flkm.history_dialog import DeployHistoryDialog, describe, size_text

D4 = Deployment("20261123-180000-000001", 1, 3, items=("Bologna FC: Goalkeeper",), size=2_500_000)
D3 = Deployment("20261123-170000-000001", 1, 2, undone=True, reapply=True, items=("Bologna FC: Home",), size=900)
D2 = Deployment("20261123-160000-000001", 0, 1, size=40)  # a relink
D1 = Deployment("20261122-150000-000001", 2, 4, logos=1, items=("Aalborg: Away", "Aalborg: crest"), size=3000)
OLD = Deployment("20261121-150000-000001", 1, 2, undone=True, items=("Old: Home",))  # recorded before Re-apply


class Calls:
    def __init__(self, deploys, ok=True):
        self.deploys, self.ok, self.log = list(deploys), ok, []

    def load(self):
        return list(self.deploys)

    def go_back(self, deploy_id):
        self.log.append(("go_back", deploy_id))
        return self.ok

    def reapply(self, deploy_id):
        self.log.append(("reapply", deploy_id))
        return self.ok

    def clear(self, ids):
        self.log.append(("clear", ids))
        if self.ok:
            self.deploys = [d for d in self.deploys if d.id not in ids]
        return self.ok


def make(qtbot, deploys=(D4, D3, D2, D1, OLD), ok=True):
    calls = Calls(deploys, ok)
    d = DeployHistoryDialog(calls.load, calls.go_back, calls.reapply, calls.clear)
    qtbot.addWidget(d)
    return d, calls


def row(d, i):
    return d.tree.topLevelItem(i)


def test_describe_and_size():
    assert describe(D1) == "Aalborg: Away, Aalborg: crest"
    assert describe(D2) == "Links to the app's kits written again"
    assert [size_text(n) for n in (40, 2048, 2_500_000)] == ["40 bytes", "2 KB", "2.4 MB"]


def test_the_deploys_newest_first(qtbot):
    d, _ = make(qtbot)
    assert d.tree.topLevelItemCount() == 5
    assert [row(d, 0).text(c) for c in range(4)] == [
        "23/11/2026 18:00",
        "Bologna FC: Goalkeeper",
        "Installed",
        "2.4 MB",
    ]
    assert row(d, 1).text(2) == "Undone"
    assert row(d, 1).foreground(1).color() != row(d, 0).foreground(1).color()  # undone ones in grey
    assert d.total.text() == "The history takes 2.4 MB."


def test_the_buttons_follow_the_deploy_selected(qtbot):
    d, _ = make(qtbot)
    buttons = (d.go_back_button, d.reapply_button)
    assert [b.isEnabled() for b in buttons] == [False, False]
    for i, enabled in ((0, [True, False]), (1, [False, True]), (4, [False, False])):  # installed, undone, old undone
        d.tree.setCurrentItem(row(d, i))
        assert [b.isEnabled() for b in buttons] == enabled


def test_go_back(qtbot):
    d, calls = make(qtbot)
    d.tree.setCurrentItem(row(d, 3))
    d.go_back_button.click()
    assert calls.log == [("go_back", D1.id)]


def test_reapply(qtbot):
    d, calls = make(qtbot)
    d.tree.setCurrentItem(row(d, 1))
    d.reapply_button.click()
    assert calls.log == [("reapply", D3.id)]


def test_a_failed_action_keeps_the_list(qtbot):
    d, calls = make(qtbot, ok=False)
    d.tree.setCurrentItem(row(d, 1))
    d.reapply_button.click()
    assert d.tree.topLevelItemCount() == 5


def ticked(d):
    return [i for i in range(d.tree.topLevelItemCount()) if row(d, i).checkState(0) == Qt.Checked]


def test_ticking_an_installed_deploy_ticks_the_older_installed_ones(qtbot):
    d, _ = make(qtbot)
    assert not d.clear_button.isEnabled()
    row(d, 2).setCheckState(0, Qt.Checked)  # the relink: D1 is older and installed
    assert ticked(d) == [2, 3] and d.clear_button.isEnabled()
    row(d, 1).setCheckState(0, Qt.Checked)  # undone: on its own
    assert ticked(d) == [1, 2, 3]
    row(d, 0).setCheckState(0, Qt.Checked)
    assert ticked(d) == [0, 1, 2, 3]
    row(d, 3).setCheckState(0, Qt.Unchecked)  # unticking an installed one unticks the newer installed ones
    assert ticked(d) == [1]
    row(d, 1).setCheckState(0, Qt.Unchecked)
    assert ticked(d) == [] and not d.clear_button.isEnabled()


def test_clear_history_deletes_the_ticked_deploys(qtbot):
    d, calls = make(qtbot)
    row(d, 4).setCheckState(0, Qt.Checked)
    row(d, 3).setCheckState(0, Qt.Checked)
    d.clear_button.click()
    assert calls.log == [("clear", {D1.id, OLD.id})]
    assert d.tree.topLevelItemCount() == 3 and ticked(d) == [] and not d.clear_button.isEnabled()


def test_an_empty_history(qtbot):
    d, _ = make(qtbot, deploys=())
    assert d.tree.topLevelItemCount() == 0 and d.total.text() == "No deploys recorded."


def test_every_button_has_a_tooltip(qtbot):
    d, _ = make(qtbot)
    assert buttons_without_tooltip(d) == []
