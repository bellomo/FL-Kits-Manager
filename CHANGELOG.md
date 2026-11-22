# Changelog

Versions follow semver (`MAJOR.MINOR.PATCH`); the release zip is `FLKitsManager_v<version>.zip`.

## 0.1.0

- Project skeleton: empty main window, `--smoke-test`, tests with 100% line and branch coverage, ruff, Windows exe
  built by GitHub Actions for tagged releases (PyInstaller, one folder); pushes run the tests only.
- Local exe after every commit (post-commit hook, `scripts/build.ps1`, the same script as the release).
- License: PolyForm Noncommercial 1.0.0 (no commercial use).
- Reading the game (no GUI yet): sider.ini, kitserver map, CPK archives, Team.bin, FTEX textures (DXT1, DXT5, BC7),
  the kits of each team and the team catalog.
- Team catalog by federation, country and league: leagues from the competition tables, named as the game shows them
  (CompetitionRegulation.bin for the game's leagues, the kitserver map for the ones Mod Studio adds), countries from the league code or the Mod Studio recipe, national teams by name,
  federations from Country.bin.
- Window: choose the game folder (remembered, or `--game`), team list by federation, country and league with search,
  team page with each kit folded (front and back as in the game) or unrolled, and where it comes from.
- View menu: larger, smaller or default text size (Ctrl++, Ctrl+-, Ctrl+0), remembered.
- File → Reload (F5): reads the game again after it changed, keeping the search and the open team.
- Replace… on each kit (`.ftex` textures): the new kit waits for Deploy, shown in orange on the team page and counted
  in the status bar; Keep the current kit / Discard all changes.
- Changes → Deploy to the game (Ctrl+D): kitserver teams get a copy of their folder in
  `content\kits\FLKitsManager` and a marked block at the end of `map.txt`; teams with kits from the game files get the
  texture in `livecpk\FLKitsManager`, put first in `sider.ini`; `.bak-<date>` copies of `map.txt` and `sider.ini`;
  nothing is written while the game runs.
- Changes → Undo last deploy: puts back every file the last deploy wrote, one deploy at a time.
- A bar (and Changes → Re-apply links) when a Mod Studio Build or another tool removed the app's block in `map.txt` or
  its root in `sider.ini`.
