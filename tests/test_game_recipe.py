"""The Mod Studio recipe of the active world (%APPDATA%/FL26ModStudio/recipes/<world>.json): the country of each league
Mod Studio adds. Without Mod Studio or its recipe there is nothing to read."""

import json

from flkm.game import recipe

RECIPE = {
    "world": "_FL26Megapack",
    "leagues": [
        {"name": "A-League Men", "country": "Australia", "clubs": 12, "club_names": ["Adelaide United"]},
        {"name": "1. division", "country": "Denmark", "clubs": 12},
    ],
    "edits": [],
}


def test_recipe_of_the_world_is_in_mod_studio_appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert recipe.path("_FL26Megapack") == tmp_path / "FL26ModStudio" / "recipes" / "_FL26Megapack.json"


def test_no_world_no_recipe():
    assert recipe.path(None) is None


def test_country_of_each_league(tmp_path):
    p = tmp_path / "w.json"
    p.write_text(json.dumps(RECIPE, indent=1, ensure_ascii=False), encoding="utf-8")
    assert recipe.league_countries(p) == {"A-League Men": "Australia", "1. division": "Denmark"}


def test_compact_json_and_escaped_names(tmp_path):
    p = tmp_path / "w.json"
    lg = [{"name": 'Liga "Pro"', "country": "Côte d'Ivoire"}]
    p.write_text(json.dumps({"leagues": lg}), encoding="utf-8")  # ensure_ascii: ô
    assert recipe.league_countries(p) == {'Liga "Pro"': "Côte d'Ivoire"}


def test_missing_recipe_reads_as_empty(tmp_path):
    assert recipe.league_countries(tmp_path / "none.json") == {}
    assert recipe.league_countries(None) == {}


def test_cups_of_each_league(tmp_path):
    p = tmp_path / "w.json"
    lg = [
        {"name": "A-League Men", "country": "Australia", "clubs": [1, 2], "cup": True, "cup_name": "Australia Cup"},
        {"name": "Bahraini PL", "country": "Bahrain", "cup_name": "King's Cup", "supercup_name": "Bahraini Super Cup"},
        {"name": "1. division", "country": "Denmark"},
    ]
    p.write_text(json.dumps({"leagues": lg, "edits": {"x": {"cup_name": "not a league"}}}, indent=1), encoding="utf-8")
    assert recipe.leagues(p) == [
        recipe.League("A-League Men", "Australia", "Australia Cup", None),
        recipe.League("Bahraini PL", "Bahrain", "King's Cup", "Bahraini Super Cup"),
        recipe.League("1. division", "Denmark", None, None),
    ]
    assert recipe.leagues(None) == []
