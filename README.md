<a id="readme-top"></a>

<div align="center">
  <img src="docs/images/flkm-logo.svg" alt="FL Kits Manager logo: a striped football shirt on a green pitch disc" width="96" height="96">
  <h1>FL Kits Manager</h1>
  <p><i>Every team, every kit, in one place.</i> ⚽</p>
  <p>
    <a href="#getting-started">Getting started</a>
    &middot;
    <a href="#usage">Usage</a>
    &middot;
    <a href="#development">Development</a>
  </p>
</div>

<details>
<summary>Table of contents</summary>

1. [About](#about)
2. [Getting started](#getting-started)
   - [Prerequisites](#prerequisites)
   - [Install](#install)
3. [Usage](#usage)
   - [What the app writes](#what-the-app-writes)
   - [Claude (optional)](#claude-optional)
4. [Roadmap](#roadmap)
5. [Development](#development)
   - [Code layout](#code-layout)
   - [Build and release](#build-and-release)
6. [License](#license)

</details>

<a id="about"></a>

## 📖 About

A Windows app to manage the kits and logos installed in **SP Football Life 2027**:

- **Browse** the teams by federation, country and league, and see each team's kits folded (as in the game) or
  unrolled (the texture).
- **Replace** kits from a folder or a zip of external files, matched to teams by id or by name.
- **Generate** kits from photos: the photos you load go through an end-to-end script (no AI needed); with Claude Code,
  the app can also find the photos and review the result.
- **Logos**: see, replace or find on the web the crests of the teams and the logos of the competitions.
- **Deploy** the changes into the game in one step, with a backup and an undo.

The app ships no kits and no logos: it reads what is installed in your game and edits it.

> Status: early development: browsing teams and kits, importing whole kits from kit packs (folder or zip), replacing
> a kit's texture with an `.ftex`, `.png` or `.dds` file, team crests and competition logos, Deploy and Undo work;
> kits from photos come next. See the [roadmap](#roadmap).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<a id="getting-started"></a>

## 🚀 Getting started

<a id="prerequisites"></a>

### 🧰 Prerequisites

- Windows 10 or 11 with SP Football Life 2027 and Sider.
- Optional: [Claude Code](https://docs.claude.com/en/docs/claude-code) signed in with your Claude subscription, for the
  features that search the web or review generated kits.

No Python is needed: the exe contains everything.

<a id="install"></a>

### 📦 Install

1. Download `FLKitsManager_v<version>.zip` from the [releases](https://github.com/bellomo/FL-Kits-Manager/releases).
2. Unzip it anywhere and start `FLKitsManager\FLKitsManager.exe`.
3. The exe is not signed: on the first start Windows SmartScreen may say "Windows protected your PC"; choose
   "More info" → "Run anyway".
4. Choose the game folder (the one with `SiderAddons`); the app remembers it. `FLKitsManager.exe --game <folder>`
   opens a folder directly.
5. View → Larger text / Smaller text (Ctrl++ / Ctrl+-) changes the text size; Ctrl+0 goes back to the system's.
6. After changing the game (kits, `map.txt`, the Mod Studio world), File → Reload (F5) reads it again.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<a id="usage"></a>

## 🎮 Usage

<a id="what-the-app-writes"></a>

### ✍️ What the app writes

**Kit packs.** Fans share kits as kit packs: a folder or a zip with one kitserver folder per team, which has one
folder per kit (`p1`, `p2`, ... players, `g1`, ... goalkeepers) with `config.txt`, the kit's texture and the textures of
its numbers and names, often with the `map.txt` lines to copy. Changes → **Import kits and logos (folder)…** or **(zip)…**
reads it and matches each team folder with a game team: by the id of the pack's map lines, checked by name (ids
change between patches), or by name alone. A dialog shows every team folder; sure matches are ticked, the others say
why they need checking, and **Choose team…** picks the team by id or name. The ticked teams' kits wait for Deploy,
each replacing the team's kit of the same kind. A team whose kits come from the game files gets a kitserver folder
with only the pack's kits. A password-protected zip has to be extracted first, then imported as a folder.

**Replace…** on a kit chooses a new texture for it: an `.ftex` file, or a `.png` or `.dds` image (square, 256, 512,
1024, 2048 or 4096 pixels; the game's kits are 2048), which the app turns into an FTEX texture with every mip, keeping
the header of the kit it replaces. Only the texture changes: the kit's settings, numbers and names stay. The change
is not written to the game yet: the kit shows
as *new* (in orange) and the status bar counts the kits waiting; **Keep the current kit** or Changes → Discard all
changes drops them. Changes → **Deploy to the game** (Ctrl+D) installs them:

- a team with a kitserver folder: the folder is copied once to `content\kits\FLKitsManager\<id> <name>` with the new
  texture, and a marked block at the end of `map.txt` points the team there (Mod Studio's own folders and lines are
  not changed);
- a team whose kits come from the game files: the texture goes to `livecpk\FLKitsManager`, which is put first in
  `sider.ini`;
- `map.txt` and `sider.ini` get a `<file>.bak-<date>` copy before their first change of the day; the game's CPK files
  are never touched;
- every file a deploy writes is recorded (with a copy of what was there) in `%APPDATA%\FLKitsManager\deploys`, and
  Changes → **Undo last deploy** puts it back, one deploy at a time;
- the game must be closed (the app checks; when it cannot tell, it asks).

**Logos.** The team page shows the team's crest next to its name; **Replace crest…** takes a picture (PNG, DDS,
JPEG or WebP; one that is not square is centred on a transparent square) and makes the three sizes the game uses
(128, 256 and 512 pixels, `common\render\symbol\flag\e_<id>_r*.png`). The **Competitions** tab lists the game's
competitions by federation and country; a competition's page shows the three variants of its logo (normal, dark for
light backgrounds, white for dark backgrounds; `common\render\symbol\emblemLc\emb_<id>*.png`, 256 and 512 pixels) on
a light and a dark background. **Replace logo…** uses one picture for all three variants, **Replace…** under a
variant changes only that one. Logos wait for Deploy like kits, then go to `livecpk\FLKitsManager`, which comes
before the other roots in `sider.ini`; Undo puts them back.

**Logo packs.** The same **Import kits and logos** reads the logos in a pack (alone or with kits): pictures named as
the game names them, wherever they are (`e_000186_r_l.png` is a team's crest, `emb_0016_w_ll.png` the white variant
of a competition's logo; the largest size of each is used), and other pictures (PNG, DDS, JPEG, WebP) named after a
team or a competition (`Bologna.png`, `Coppa Italia.jpg`). A dialog shows each logo with a small picture and where it
goes; sure ones are ticked, the others say why they need checking, and **Choose…** gives a logo to a team or a
competition by id or name. A competition's logo replaces only the variants the pack has; a picture named after the
competition is used for all three. Pictures in kit folders are not logos.

A Mod Studio Build rewrites `map.txt` and can drop the app's block (another tool can do the same to `sider.ini`): the
app then shows a bar with **Re-apply**, also in Changes → Re-apply links to the app's kits.

<a id="claude-optional"></a>

### 🤖 Claude (optional)

With the Claude Code CLI installed and signed in, the app can search the web for kit photos and logos and review the
kits it generates. Before every run it shows the model, the estimated tokens and the estimated share of your usage
limits, and warns you when the run could use up what is left. Without Claude, everything else works.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<a id="roadmap"></a>

## 🗺️ Roadmap

| Milestone | Content | Done |
|---|---|---|
| M0 | Project skeleton, tests, exe built by GitHub Actions | ✅ [`3f7e7a6`](https://github.com/bellomo/FL-Kits-Manager/commit/3f7e7a6) |
| M1 | Read the game: sider.ini, kitserver map, CPK, FTEX textures, team catalog by federation, country and league, which kit each team uses | ✅ [`de8cefa`](https://github.com/bellomo/FL-Kits-Manager/commit/de8cefa) |
| M2 | Team list and team page, kits folded and unrolled | ✅ [`39314f2`](https://github.com/bellomo/FL-Kits-Manager/commit/39314f2) |
| M3 | Staging, deploy, undo | ✅ [`6b99c15`](https://github.com/bellomo/FL-Kits-Manager/commit/6b99c15) |
| M4 | Import whole kits from kit packs, folder or zip (match by id and name); PNG and DDS images | ✅ [`2103776`](https://github.com/bellomo/FL-Kits-Manager/commit/2103776), [`0e554a2`](https://github.com/bellomo/FL-Kits-Manager/commit/0e554a2) |
| M5 | Logos: view and replace crests and competition logos | ✅ [`942d72e`](https://github.com/bellomo/FL-Kits-Manager/commit/942d72e) |
| M6 | Kits from photos loaded by the user (end-to-end script) | |
| M7 | Claude: detection, usage estimate and warning, logos from the web | |
| M8 | Kits from photos found and reviewed by Claude | |
| M9 | Release 0.1.0: tag `v0.1.0`, exe zip `FLKitsManager_v0.1.0.zip` on the GitHub releases page | |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<a id="development"></a>

## 🛠️ Development

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -e . -r requirements-dev.txt
.\.venv\Scripts\python -m pytest -q --cov=flkm --cov-report=term-missing
.\.venv\Scripts\python -m flkm
```

Development rules (test-driven, 100% line and branch coverage, no network in tests, test file names, ruff) are in
[`CLAUDE.md`](CLAUDE.md).

<a id="code-layout"></a>

### 🗂️ Code layout

| Path | Content |
|---|---|
| `flkm/cli.py` | Command line of the exe (`--game <folder>`, `--smoke-test`) |
| `flkm/main_window.py` | Main window: game folder, team list, team page, Changes menu (Deploy, Undo, Re-apply) |
| `flkm/team_tree.py` | Team list: federation > country > league > team, search by name or id |
| `flkm/team_page.py` | Team page: crest, details and kits, folded or unrolled, Replace… and kits waiting for Deploy |
| `flkm/competition_tree.py` | Competition list: federation > country > competition, search by name, code or id |
| `flkm/competition_page.py` | Competition page: the three variants of its logo on light and dark, Replace logo… |
| `flkm/import_dialog.py` | Import dialog: the pack's team folders, the game team of each one, Choose team… |
| `flkm/logo_import_dialog.py` | Logo import dialog: the pack's logos, a picture of each, where it goes, Choose… |
| `flkm/pack.py` | Kit packs (folder or zip): team folders, their kits, map lines; matching with the game's teams |
| `flkm/logo_pack.py` | Logos in a pack: by game file name or by team or competition name; the files of the chosen ones |
| `flkm/staging.py` | Kits chosen to replace the game's (textures or whole kits), kept until Deploy (`%APPDATA%\FLKitsManager\staging`) |
| `flkm/deploy.py` | Deploy, Undo, Re-apply links, status of the app's links, deploy history |
| `flkm/render.py` | Kit pictures from a texture: unrolled, and folded (front and back as in the game) |
| `flkm/settings.py` | Settings (`%APPDATA%\FLKitsManager\settings.json`): game folder, kit view, text size |
| `flkm/__main__.py` | `python -m flkm` and the PyInstaller entry point |
| `flkm/catalog.py` | Team catalog of the installed game: teams by federation, country and league, search, kits of a team |
| `flkm/game/sider_ini.py` | sider.ini: livecpk roots in priority order, Lua modules, Mod Studio world; the app's root |
| `flkm/game/kitmap.py` | Kitserver map (`content/kits/map.txt`): team id → kit folder, league; the app's block |
| `flkm/game/process.py` | Whether the game is running |
| `flkm/game/cpk.py` | CRI CPK archives, read only |
| `flkm/game/files.py` | Where the game takes a file from: livecpk roots, then `download/`, then `Data/` CPKs |
| `flkm/game/pesdb.py` | Database tables: WESYS unpacking, teams, competitions and their names, entries, countries |
| `flkm/game/recipe.py` | Mod Studio recipe of the active world: the country of each league Mod Studio adds |
| `flkm/game/ftex.py` | FTEX textures (DXT1, DXT5, BC7) decoded to images |
| `flkm/game/ftex_write.py` | FTEX textures written from blocks, images (DXT5 with mips) and DDS files; kit textures |
| `flkm/game/kits.py` | Which kits a team wears (kitserver folder or game files) |
| `flkm/game/logos.py` | Team crests and competition logos: their game files, the one the game uses, new ones from a picture |
| `tests/` | One test file per module, `test_rule_*.py` for repository rules |
| `scripts/build.ps1` | Builds the one-folder exe and smoke-tests it (local hook and release) |
| `scripts/hooks/post-commit` | Local build after every commit |
| `.github/workflows/build.yml` | Tests on every push, exe and release on tags |

<a id="build-and-release"></a>

### 📦 Build and release

GitHub Actions runs the tests on every push and pull request. The exe (PyInstaller, one folder) is built only for a
release, on the commit we choose: set the version (`flkm/__init__.py`, `pyproject.toml`, `CHANGELOG.md`), then tag
that commit and push the tag; the workflow publishes `FLKitsManager_vX.Y.Z.zip` as a release:

```powershell
git tag v0.1.0 <commit>
git push origin v0.1.0
```

Locally the exe is rebuilt after every commit, so each commit can be tried at once: the post-commit hook in
`scripts/hooks` runs `scripts/build.ps1` in the background (the commit does not wait), which builds
`dist\FLKitsManager\FLKitsManager.exe` and smoke-tests it; the log is `build\last-build.log` (close the app first, a
running exe cannot be replaced). Enable the hook once per clone, or build by hand:

```powershell
git config core.hooksPath scripts/hooks
.\scripts\build.ps1
```

<a id="license"></a>

## 📄 License

[PolyForm Noncommercial 1.0.0](LICENSE): the source is public and you may use, change and share it for any
noncommercial purpose (personal use, hobby, study, non-profit organisations), keeping the `Required Notice` line.
Commercial use, such as selling the app or using it for profit, is not allowed. This makes the project source
available rather than open source in the OSI sense.

<p align="right">(<a href="#readme-top">back to top</a>)</p>
