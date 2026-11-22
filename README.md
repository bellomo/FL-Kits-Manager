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

> Status: early development: browsing teams and kits works; replacing and deploying come next. See the
> [roadmap](#roadmap).

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

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<a id="usage"></a>

## 🎮 Usage

<a id="what-the-app-writes"></a>

### ✍️ What the app writes

Every change is first kept in a staging area. **Deploy** installs it into the game:

- only into the app's own folders (its livecpk root and kits folder) and its own marked lines of `sider.ini` and the
  kitserver `map.txt`; the game's CPK files are never touched;
- every file it changes is backed up first, and **Undo last deploy** puts the previous state back;
- the game must be closed.

<a id="claude-optional"></a>

### 🤖 Claude (optional)

With the Claude Code CLI installed and signed in, the app can search the web for kit photos and logos and review the
kits it generates. Before every run it shows the model, the estimated tokens and the estimated share of your usage
limits, and warns you when the run could use up what is left. Without Claude, everything else works.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<a id="roadmap"></a>

## 🗺️ Roadmap

| Milestone | Content |
|---|---|
| M0 | Project skeleton, tests, exe built by GitHub Actions |
| M1 | Read the game: sider.ini, kitserver map, CPK, FTEX textures, team catalog by federation, country and league, which kit each team uses |
| M2 | Team list and team page, kits folded and unrolled |
| M3 | Staging, deploy, undo |
| M4 | Replace kits from a folder or a zip (match by id or name) |
| M5 | Logos: view and replace crests and competition logos |
| M6 | Kits from photos loaded by the user (end-to-end script) |
| M7 | Claude: detection, usage estimate and warning, logos from the web |
| M8 | Kits from photos found and reviewed by Claude |

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
| `flkm/main_window.py` | Main window: game folder, team list, team page |
| `flkm/team_tree.py` | Team list: federation > country > league > team, search by name or id |
| `flkm/team_page.py` | Team page: details and kits, folded or unrolled |
| `flkm/render.py` | Kit pictures from a texture: unrolled, and folded (front and back as in the game) |
| `flkm/settings.py` | Settings (`%APPDATA%\FLKitsManager\settings.json`): game folder, kit view |
| `flkm/__main__.py` | `python -m flkm` and the PyInstaller entry point |
| `flkm/catalog.py` | Team catalog of the installed game: teams by federation, country and league, search, kits of a team |
| `flkm/game/sider_ini.py` | sider.ini: livecpk roots in priority order, Lua modules, Mod Studio world |
| `flkm/game/kitmap.py` | Kitserver map (`content/kits/map.txt`): team id → kit folder, league |
| `flkm/game/cpk.py` | CRI CPK archives, read only |
| `flkm/game/files.py` | Where the game takes a file from: livecpk roots, then `download/`, then `Data/` CPKs |
| `flkm/game/pesdb.py` | Database tables: WESYS unpacking, teams, competitions, competition entries, countries |
| `flkm/game/recipe.py` | Mod Studio recipe of the active world: the country of each league Mod Studio adds |
| `flkm/game/ftex.py` | FTEX textures (DXT1, DXT5, BC7) decoded to images |
| `flkm/game/kits.py` | Which kits a team wears (kitserver folder or game files) |
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
