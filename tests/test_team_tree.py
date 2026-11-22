"""The team list: a tree federation > country > league > team with the number of teams of each group, and a search box
(name or id) that shows only the teams found, opened up when they are few. Choosing a team tells the window which."""

from PySide6.QtCore import Qt

from flkm.catalog import Catalog, Team
from flkm.team_tree import TeamTree

TEAMS = [
    Team(186, "Bologna FC", "BOL", "Italy D1", "Italy", "UEFA"),
    Team(98, "Inter", "INT", "Italy D1", "Italy", "UEFA"),
    Team(12, "Italy", "ITA", None, "Italy", "UEFA"),
    Team(73947, "Aalborg Boldspilklub", "AAL", "1. division", "Denmark", "UEFA"),
    Team(101, "Austin FC", "AUS", "USA D1", "USA", "CONCACAF"),
    Team(900, "Titans Classics", "TIT", None, None, None),
]


def make_tree(qtbot):
    t = TeamTree()
    qtbot.addWidget(t)
    t.set_catalog(Catalog(None, None, TEAMS))
    return t


def texts(item):
    return [item.child(i).text(0) for i in range(item.childCount())]


def top(tree):
    return [tree.tree.topLevelItem(i) for i in range(tree.tree.topLevelItemCount())]


def test_groups_with_their_number_of_teams(qtbot):
    t = make_tree(qtbot)
    assert [i.text(0) for i in top(t)] == ["CONCACAF (1)", "UEFA (4)", "Other (1)"]
    uefa = top(t)[1]
    assert texts(uefa) == ["Denmark (1)", "Italy (3)"]
    assert texts(uefa.child(1)) == ["Italy D1 (2)", "No league (1)"]
    assert texts(uefa.child(1).child(0)) == ["Bologna FC", "Inter"]
    assert texts(top(t)[2]) == ["Unknown country (1)"]
    assert not uefa.isExpanded()


def test_choosing_a_team_tells_its_id(qtbot):
    t = make_tree(qtbot)
    bologna = top(t)[1].child(1).child(0).child(0)
    assert bologna.toolTip(0) == "id 186 · BOL"
    with qtbot.waitSignal(t.team_selected) as sig:
        t.tree.setCurrentItem(bologna)
    assert sig.args == [186]


def test_choosing_a_group_tells_nothing(qtbot):
    t = make_tree(qtbot)
    chosen = []
    t.team_selected.connect(chosen.append)
    t.tree.setCurrentItem(top(t)[1])
    assert chosen == []


def test_search_shows_only_the_teams_found_opened_up(qtbot):
    t = make_tree(qtbot)
    qtbot.keyClicks(t.search, "bolog")
    assert [i.text(0) for i in top(t)] == ["UEFA (1)"]
    assert top(t)[0].isExpanded() and top(t)[0].child(0).child(0).isExpanded()
    t.search.setText("73947")
    assert texts(top(t)[0].child(0).child(0)) == ["Aalborg Boldspilklub"]
    t.search.clear()
    assert len(top(t)) == 3 and not top(t)[1].isExpanded()


def test_search_without_results_says_so(qtbot):
    t = make_tree(qtbot)
    t.search.setText("zzz")
    assert [i.text(0) for i in top(t)] == ["No team found"]
    assert top(t)[0].flags() & Qt.ItemIsSelectable == Qt.NoItemFlags


def test_select_a_team_by_id(qtbot):
    t = make_tree(qtbot)
    with qtbot.waitSignal(t.team_selected) as sig:
        assert t.select_team(73947) is True
    assert sig.args == [73947] and t.tree.currentItem().text(0) == "Aalborg Boldspilklub"
    assert t.tree.currentItem().parent().isExpanded()  # shown, not hidden in a closed group


def test_select_a_team_that_is_not_in_the_tree(qtbot):
    t = make_tree(qtbot)
    t.search.setText("bologna")
    assert t.select_team(73947) is False and t.select_team(5) is False


def test_without_a_catalog_the_tree_is_empty(qtbot):
    t = TeamTree()
    qtbot.addWidget(t)
    t.search.setText("x")
    assert t.tree.topLevelItemCount() == 0
