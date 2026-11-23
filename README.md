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
   - [View kits and logos](#view)
   - [Replace one kit or logo](#replace-one)
   - [Kits from photos](#kits-from-photos)
   - [Replace many: import kits and logos](#replace-many)
   - [Deploy and what the app writes](#what-the-app-writes)
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
- **Replace** one kit, crest or competition logo with a file of your choice, or many at once from a folder or a zip
  (kits and logos matched to teams and competitions by id or by name).
- **Generate** kits from photos: the photos you load go through an end-to-end script (no AI needed); with Claude Code,
  the app can also find the photos and review the result.
- **Logos**: see and replace the crests of the teams and the logos of the competitions (finding them on the web with
  Claude comes later).
- **Deploy** the changes into the game in one step, with a backup and an undo.

The app ships no kits and no logos: it reads what is installed in your game and edits it.

> Status: early development: browsing teams and kits, importing kits and logos from packs (folder or zip), replacing
> a kit's texture with an `.ftex`, `.png` or `.dds` file, team crests and competition logos, kits from your own
> photos, Deploy and Undo work; Claude (finding photos and logos on the web) comes next. See the [roadmap](#roadmap).

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

<a id="view"></a>

### 👀 View kits and logos

**Teams.** The **Teams** tab lists every team of the game by federation, country and league (national teams under
their country, as *National team*); type a name or an id to search. A team's page shows:

- its crest, with the file it comes from, and its id, league, country and federation;
- every kit it wears (Home, Away, Third, goalkeepers...), **Folded** as the game shows it (front and back) or
  **Unrolled** (the whole texture);
- where the files are: *Crest in* and *Kits in* give the folder once, each with **Open folder**; under each kit
  is only its file name (`<cpk> › <file>` for one inside a game archive).

**Competitions.** The **Competitions** tab lists the game's competitions by federation and country (continental and
world competitions under *International*); the ones Mod Studio adds are named as Mod Studio named them. A
competition's page shows its logo in the three variants the game uses, each on a light and a dark background:
*Normal*, *Dark* (for light backgrounds) and *White* (for dark backgrounds). Some of the game's own logos come in
only some of them; a missing one shows *Not in the game files*. *Logo in* gives the folder, with **Open folder**.

Nothing is changed while you look: the app reads the game as Sider shows it (the livecpk folders of `sider.ini` first,
then the update and base archives).

<a id="replace-one"></a>

### 🔁 Replace one kit or logo

- **A kit:** **Replace…** under the kit takes an `.ftex` texture, or a `.png` or `.dds` image (square, 256 to 4096
  pixels; the game's kits are 2048), made into an FTEX texture that keeps the settings of the kit it replaces. Only
  the texture changes: the kit's numbers and names stay.
- **A crest:** **Replace crest…** on the team page takes a picture (PNG, DDS, JPEG or WebP; one that is not square is
  centred on transparency) and makes the game's three sizes, 128, 256 and 512 pixels.
  Some clubs have a dark and a white version of their crest in the game (most of them instead of the plain one:
  LASK, Juventus...): the page shows both, and a new crest replaces every version the club has.
- **A competition's logo:** **Replace logo…** uses one picture for all three variants; **Replace…** under a variant
  changes only that one.

A replacement is not written to the game yet: it shows as *new* (in orange) and the status bar counts what is
waiting. **Keep the current kit** / **Keep the current crest** / **Keep the current logo** drops one, Changes →
**Discard all changes** drops them all.

<a id="kits-from-photos"></a>

### 📸 Kits from photos

**Kits from photos…** on the team page makes the team's kits from photos of the real ones (the club's store photos
work best): one photo per box, for each kit (home, away, third, goalkeeper) the shirt from the front and from the
back, the shorts and the socks. Only the shirt from the front is needed: without its back the kit's back is the front
mirrored (no back sponsor), without shorts they take the shirt's colour, without socks the shorts' colour; the notes
under the new kits say which parts were made this way. A kit without the shirt from the front is not made (the team
keeps the one it has).

**Colours** (one choice per kit): when the front and the back photos come from different sites, the same colours can
look different on them. **Auto** keeps a back that looks of another colour (a kit really in two colours);
**From the front** or **From the back** makes the whole kit in the colours of that photo. The choice is remembered for
the next time.

A back photo with a player's name and number works too: the game puts them on for each player, so they are left out
of the kit (not taken for stripes or sponsors); the notes say so.

Photos come in every way:

- **Add photos…** or **Add folder…**: photos named like `home_1.png`, `back_home.png`, `away_shorts.png` go to their
  box, the others to the first empty boxes;
- **drag** pictures from Explorer or a browser onto a box (or anywhere in the window);
- **copy** a picture or a photo file and **paste** it (Ctrl+V or **Paste**) into the box you clicked;
- drag a photo to another box to move it (the two swap), double-click a box to choose its photo, right click to
  remove it.

**Make kits** reads the colours, logos and stripes on the photos (about a minute) and shows each new kit next to the
one the team wears now, **Folded** or **Unrolled** (the same choice as on the team page). **View photos** goes back to
the photos and **View kits** comes back to the kits made last, without making them again; the kits made last time
are there to view when the dialog opens again. The crest comes from the game (or the new crest waiting for Deploy); the kit maker's logo is
cut from the photos and kept in `%APPDATA%\FLKitsManager\makers`, so the next teams of the same maker get it even
when their photos hide it. **Add to changes** stages the kits like **Replace…**: they wait for Deploy. The photos stay
in the team's work folder (`%APPDATA%\FLKitsManager\photokits\<team id>`), and the dialog opens with them next time.

To undo a try: **Cancel** before Add to changes stages nothing; after it, **Keep the current kit** or Changes →
**Discard all changes**. **Clear** deletes the team's work folder (the copies of the photos, the
pictures pasted, the logos cut from them, the kits made) after asking: it cannot be undone, and your own photo files
are not touched. The makers' logos stay in their cache for the next teams.

<a id="replace-many"></a>

### 📦 Replace many: import kits and logos

Kits and logos are often shared as packs: a folder or a zip. Changes → **Import kits and logos (folder)…** or
**(zip)…** reads one and finds out where each thing goes; a dialog lists what was found, with the sure ones ticked and
the others (in orange) saying why they need checking. Untick what you do not want, then **Add to changes**: all of it
waits for Deploy, like a single replacement.

- **Kits:** a kitserver folder per team, with a folder per kit (`p1`, `p2`, ... players; `g1`, ... goalkeepers) and
  its `config.txt` and textures, often with the `map.txt` lines to copy. Each team folder is matched with a game team
  by the id of those lines, checked by name (ids change between patches), or by name alone; **Choose team…** picks
  the team by id or name. Each kit of the pack replaces the team's kit of the same kind; the team's other kits stay.
- **Logos:** pictures named as the game names them, wherever they are in the pack (`e_000186_r_l.png` is a team's
  crest, `emb_0016_w_ll.png` the white variant of a competition's logo; the largest size of each is used), and
  pictures named after a team or a competition (`Bologna.png`, `Coppa Italia.jpg`). The dialog shows a small picture
  of each; **Choose…** gives a logo to a team or a competition by id or name. A competition's logo replaces only the
  variants the pack has; a picture named after the competition is used for all three.

A pack can have kits, logos or both: the kit dialog comes first, then the logo dialog. A password-protected zip has
to be extracted first, then imported as a folder.

<a id="what-the-app-writes"></a>

### ✍️ Deploy and what the app writes

Changes → **Deploy to the game** (Ctrl+D) installs everything that is waiting, after showing the list:

- a kit of a team with a kitserver folder: the folder is copied once to `content\kits\FLKitsManager\<id> <name>`
  with the new kit, and a marked block at the end of `map.txt` points the team there (Mod Studio's own folders and
  lines are not changed);
- a kit of a team whose kits come from the game files, and every crest and logo: the files go to
  `livecpk\FLKitsManager`, which is put first in `sider.ini`;
- `map.txt` and `sider.ini` get a `<file>.bak-<date>` copy before their first change of the day; the game's CPK files
  are never touched;
- every file a deploy writes is recorded (with a copy of what was there, and the kits and logos it installed) in
  `%APPDATA%\FLKitsManager\deploys`, and Changes → **Undo last deploy** puts it back; before putting back a file, the
  app checks that no other tool (a Mod Studio Build, say) changed it since, and asks when one did;
- Changes → **Deploy history…** lists every deploy, newest first, installed or undone:
  - **Go back to before this…** undoes a deploy and every newer one still installed, newest first;
  - **Re-apply** puts the kits and logos of an undone deploy back among the changes waiting for Deploy;
  - **Clear history…** deletes the records of the deploys you tick (they can no longer be undone or re-applied; the
    game files are not touched). Ticking a deploy still installed ticks the older installed ones too: going back to
    them needs it;
- the game must be closed (the app checks; when it cannot tell, it asks). Restart the game to see the changes.

A Mod Studio Build rewrites `map.txt` and can drop the app's block (another tool can do the same to `sider.ini`): the
app then shows a bar with **Re-apply**, also in Changes → Re-apply links to the app's kits.

<a id="claude-optional"></a>

### 🤖 Claude (optional)

With the Claude Code CLI installed and signed in, the app can search the web for kit photos and logos and review the
kits it generates. Before every run it shows the model, the estimated tokens and the estimated share of your usage
limits, and warns you when the run could use up what is left. Without Claude, everything else works.

The status bar says whether the app found Claude Code. It looks for it on `PATH`, where its installers put it
(`%USERPROFILE%\.local\bin`, `%APPDATA%\npm`) and inside the Claude desktop app (the newest version); a program
counts only when `claude --version` answers. **Claude → Choose Claude Code…** picks the program by hand (remembered),
**Look for Claude Code again** forgets it and looks again. Next to the version it shows your plan (Pro, Max...) or
"not signed in".

Before every Claude run a window shows what it will do, the model (you can choose another), the tokens it should
use (a first guess, then the median of your last runs of the same kind), what the app used in the last 5 hours
and 7 days, and the usage limits Claude Code reported at the end of the last run (5-hour and 7-day windows, how
much is used and when they reset), with a warning when one is close. Claude runs only after **Run**. A run has no
saved session, only the tools its task needs (nothing else is allowed), a time limit and a spending cap.
**Claude → Check usage limits…**
makes a tiny run (a one-word answer with Haiku) just to read the limits. The runs are logged in
`%APPDATA%\FLKitsManager\claude_runs.jsonl` (time, kind, model, tokens; no answers, nothing personal).

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
| M6 | Kits from photos loaded by the user (end-to-end script) | ✅ [`bbadf03`](https://github.com/bellomo/FL-Kits-Manager/commit/bbadf03), [`48e61f6`](https://github.com/bellomo/FL-Kits-Manager/commit/48e61f6), [`fce889d`](https://github.com/bellomo/FL-Kits-Manager/commit/fce889d) |
| M7 | Claude: detection, usage estimate and warning | |
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
| `flkm/icon.py` | The app icon `flkm/flkm.ico` (exe and windows), made from `docs/images/flkm-logo.svg` with `python -m flkm.icon` |
| `flkm/main_window.py` | Main window: game folder, team list, team page, Changes menu (Deploy, Undo, history, Re-apply) |
| `flkm/history_dialog.py` | Deploy history: every deploy, Go back to before this…, Re-apply, Clear history… |
| `flkm/team_tree.py` | Team list: federation > country > league > team, search by name or id |
| `flkm/team_page.py` | Team page: crest, details and kits, folded or unrolled, Replace…, Kits from photos… and kits waiting for Deploy |
| `flkm/competition_tree.py` | Competition list: federation > country > competition, search by name, code or id |
| `flkm/competition_page.py` | Competition page: the three variants of its logo on light and dark, Replace logo… |
| `flkm/photo_kit_dialog.py` | Kits from photos dialog: photos added, dropped or pasted in boxes, kits made in the background, current and new |
| `flkm/import_dialog.py` | Import dialog: the pack's team folders, the game team of each one, Choose team… |
| `flkm/logo_import_dialog.py` | Logo import dialog: the pack's logos, a picture of each, where it goes, Choose… |
| `flkm/pack.py` | Kit packs (folder or zip): team folders, their kits, map lines; matching with the game's teams |
| `flkm/logo_pack.py` | Logos in a pack: by game file name or by team or competition name; the files of the chosen ones |
| `flkm/staging.py` | Kits chosen to replace the game's (textures or whole kits), kept until Deploy (`%APPDATA%\FLKitsManager\staging`) |
| `flkm/deploy.py` | Deploy, Undo (back to any deploy, checking for files changed since), Re-apply an undone deploy, clear the history, Re-apply links, status of the app's links |
| `flkm/claude.py` | Claude Code (the claude CLI): where it is looked for, its version |
| `flkm/claude_run.py` | A Claude run (`claude -p`, stream-json): answer, tokens, usage limits; the run log and estimates |
| `flkm/claude_dialog.py` | The window before every Claude run: model, estimate, usage, limits, Run |
| `flkm/render.py` | Kit pictures from a texture: unrolled, and folded (front and back as in the game) |
| `flkm/settings.py` | Settings (`%APPDATA%\FLKitsManager\settings.json`): game folder, kit view, text size, Claude Code chosen |
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
| `flkm/photokit/photo.py` | Kits from photos: what a photo shows (from its file name), where the garment is on it |
| `flkm/photokit/colour.py` | Hex colours, colours measured on a photo (body, sleeves, collar), contrast |
| `flkm/photokit/logo.py` | Logos on a shirt photo (maker, crest, sponsors): found, cut out with their colours, measured |
| `flkm/photokit/pattern.py` | Stripes, panels and blocks of a shirt from its photos, as rectangles of the texture |
| `flkm/photokit/draft.py` | A team's `team.json` drafted from its photos: colours, logo positions, pattern |
| `flkm/photokit/spec.py` | `team.json` expanded into one texture spec per kit: where each logo goes |
| `flkm/photokit/texture.py` | A 2048x2048 kit texture painted from a spec (zones in `kit_zones.png`) |
| `flkm/photokit/build.py` | The textures of a team folder in one call |
| `flkm/photokit/maker.py` | Makers' logos cut from photos, kept in `%APPDATA%\FLKitsManager\makers` and recognised by shape |
| `flkm/photokit/team.py` | A team from its photos: crest from the game, maker from the cache, textures staged for Deploy |
| `tests/` | One test file per module, `test_rule_*.py` for repository rules |
| `tests/fake_claude.py` | A fake Claude Code for the tests: it answers what the real one answers |
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
