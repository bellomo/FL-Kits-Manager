"""The competition list: a tree federation > country > competition with the number of competitions of each group
(International for the ones without a country), and a search box (name, code or id). Choosing a competition tells
the window which."""

from flkm.catalog import Catalog, Competition
from flkm.competition_tree import CompetitionTree

COMPS = [
    Competition(10, "ITALY_D1_LEAGUE", "Serie A TIM", "Italy", "UEFA"),
    Competition(16, "ITALY_D1_CUP", "Coppa Italia", "Italy", "UEFA"),
    Competition(40, "US_D1_LEAGUE", "Major League Soccer", "USA", "CONCACAF"),
    Competition(2, "UEFA_CHAMPIONS_LEAGUE", "UEFA Champions League", None, None),
]


def make_tree(qtbot):
    t = CompetitionTree()
    qtbot.addWidget(t)
    t.set_catalog(Catalog(None, None, [], COMPS))
    return t


def top(tree):
    return [tree.tree.topLevelItem(i) for i in range(tree.tree.topLevelItemCount())]


def texts(item):
    return [item.child(i).text(0) for i in range(item.childCount())]


def test_groups_with_their_number_of_competitions(qtbot):
    t = make_tree(qtbot)
    assert [i.text(0) for i in top(t)] == ["CONCACAF (1)", "UEFA (2)", "International (1)"]
    assert texts(top(t)[1]) == ["Italy (2)"]
    assert texts(top(t)[1].child(0)) == ["Coppa Italia", "Serie A TIM"]
    assert texts(top(t)[2]) == ["UEFA Champions League"]  # no country level
    assert top(t)[1].child(0).child(0).toolTip(0) == "id 16 · ITALY_D1_CUP"


def test_choosing_a_competition_tells_its_id(qtbot):
    t = make_tree(qtbot)
    chosen = []
    t.competition_selected.connect(chosen.append)
    t.tree.setCurrentItem(top(t)[1])  # a group
    t.tree.setCurrentItem(top(t)[2].child(0))
    assert chosen == [2]


def test_search(qtbot):
    t = make_tree(qtbot)
    t.search.setText("cup")
    assert [i.text(0) for i in top(t)] == ["UEFA (1)"] and top(t)[0].isExpanded()
    t.search.setText("zzz")
    assert [i.text(0) for i in top(t)] == ["No competition found"]


def test_select_a_competition_by_id(qtbot):
    t = make_tree(qtbot)
    assert t.select(40) is True and t.tree.currentItem().text(0) == "Major League Soccer"
    assert t.select(999) is False


def test_without_a_catalog_the_tree_is_empty(qtbot):
    t = CompetitionTree()
    qtbot.addWidget(t)
    t.search.setText("x")
    assert t.tree.topLevelItemCount() == 0
