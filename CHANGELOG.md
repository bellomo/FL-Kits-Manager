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
