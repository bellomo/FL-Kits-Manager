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
- Logos (M5): the team page shows the team's crest with Replace crest… (a PNG, DDS, JPEG or WebP picture made into
  the game's three sizes, 128, 256 and 512); a Competitions tab lists the game's competitions by federation and
  country, and each competition page shows its logo's three variants (normal, dark, white) on light and dark
  backgrounds, with Replace logo… for all of them or Replace… for one. Logos wait for Deploy like kits and go to
  `livecpk\FLKitsManager`; Undo puts them back. The competitions Mod Studio adds are named too: its cups and
  supercups by the recipe of their league, every competition of a Mod Studio league (league cup, play-offs) in the
  country of its league, the others (e.g. FL_UECL, UEFA Conference League) by
  the name Mod Studio writes in their regulation records.
- Logo packs: Import kits and logos (folder or zip) also reads the logos in a pack: pictures named as the game names
  them (the largest size of each) and pictures named after a team or a competition. A dialog shows each logo with a
  small picture and where it goes, ticks the sure ones and lets the user choose the team or competition of the
  others; the chosen logos wait for Deploy.
- Team page: the folder of the team's kits once at the top, with Open folder; each kit shows only its file name in
  that folder (`<cpk> › <file>` for a kit inside a game archive). Above it, the folder of the crest the same way
  (Crest in…, with its own Open folder); the crest shows only its file name. The competition page does the same
  for its logo (Logo in…, Open folder; each variant shows its file name in that folder).
- National teams show under their country as "National team" instead of "No league".
- View menu: larger, smaller or default text size (Ctrl++, Ctrl+-, Ctrl+0), remembered.
- File → Reload (F5): reads the game again after it changed, keeping the search and the open team.
- Replace… on each kit (`.ftex` textures): the new kit waits for Deploy, shown in orange on the team page and counted
  in the status bar; Keep the current kit / Discard all changes.
- Changes → Deploy to the game (Ctrl+D): kitserver teams get a copy of their folder in
  `content\kits\FLKitsManager` and a marked block at the end of `map.txt`; teams with kits from the game files get the
  texture in `livecpk\FLKitsManager`, put first in `sider.ini`; `.bak-<date>` copies of `map.txt` and `sider.ini`;
  nothing is written while the game runs.
- Changes → Undo last deploy: puts back every file the last deploy wrote, one deploy at a time.
- Changes → Import kit pack (folder or zip): whole kitserver kits (config.txt, texture, numbers and names) from the
  packs fans share; each team folder is matched with a game team by the pack's map id checked by name, or by name;
  a dialog shows the matches, ticks the sure ones and lets the user choose the team by id or name. Kits the team did
  not have show as new cards; a team with kits from the game files gets a kitserver folder with the pack's kits.
- Replace… also takes `.png` and `.dds` images (square, 256 to 4096 pixels): they become an FTEX texture (DXT5 with
  every mip, or the DDS's own blocks when it has every mip) with the header of the kit they replace.
- A bar (and Changes → Re-apply links) when a Mod Studio Build or another tool removed the app's block in `map.txt` or
  its root in `sider.ini`.
- Kits from photos (M6, no window yet): the photo-to-texture steps of the Kits_foto tools moved into `flkm/photokit`
  (photo, colour, logo, pattern, draft, spec, texture, build), with tests on generated photos; numpy is now a
  dependency.
