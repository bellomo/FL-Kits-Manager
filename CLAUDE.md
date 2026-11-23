# FL Kits Manager: development rules

## Test-driven development (always)

- Every change starts with a test: write the test, run it and see it fail, then write the code until it passes.
  This applies to new features, bug fixes (first a test that reproduces the bug) and refactorings (tests first green,
  then refactor).
- Test requirements and behaviour, not presentation: which kit a team gets and from where, what a match of external
  files to teams gives, what a deploy writes and what an undo restores, the usage estimate shown before a Claude run.
  Widgets are tested for the facts they show and the actions they trigger, not their layout.
- When a request changes existing behaviour, rewrite the test that encoded the old behaviour; don't add a new one
  beside it.
- Tests never touch the real game or the user's data: the autouse `home` fixture sets `FLKM_HOME` to a temporary
  folder, the `game` fixture gives an empty fake game folder. Game files in tests (sider.ini, map.txt, CPK, FTEX) are
  tiny ones the test builds itself. Never commit kits, logos or other game data.
- Claude runs in tests are fakes (a function argument or a fake `claude` command): no test starts the real CLI.
- `tests/conftest.py` blocks every outgoing connection except localhost (the `NETWORK-GUARD` marker) and makes Qt draw
  off screen. Never remove it, never run `pytest --noconftest`.
- Before every commit run the whole suite with coverage. Coverage is 100% of lines and branches: this run fails below
  it (`fail_under` and `branch` in `pyproject.toml`, kept by `tests/test_rule_coverage.py`); a plain `pytest` does not
  measure it. Cover a new line or branch with a test of its behaviour, never with `# pragma: no cover`:

  ```powershell
  .\.venv\Scripts\python -m pytest -q --cov=flkm --cov-report=term-missing
  ```

## Test files

- A test file names what it tests: `tests/test_<module>.py` for `flkm/<module>.py`, `tests/test_<package>_<module>.py`
  for `flkm/<package>/<module>.py`, `tests/test_main.py` for `flkm/__main__.py`. Tests of a repository rule that read
  the code or the settings rather than call a module: `tests/test_rule_<rule>.py`. `tests/test_rule_test_names.py`
  enforces it.
- A test goes in the file of the module whose function it calls. Shared fixtures go in `tests/conftest.py`.

## Lint and format

- Ruff with the rules of `pyproject.toml` (pyflakes, E4, E7, E9, lines of at most 120 characters) and ruff's format
  with double quotes; `tests/test_rule_lint.py` runs both.

## Versions and releases

- Semver `MAJOR.MINOR.PATCH`, the same in `flkm/__init__.py`, `pyproject.toml` and the top entry of `CHANGELOG.md`
  (`tests/test_rule_version.py`). Pushes only run the tests; the exe is built only when the user decides a release:
  a tag `vX.Y.Z` pushed on the chosen commit builds it and publishes `FLKitsManager_vX.Y.Z.zip`
  (`.github/workflows/build.yml`). Never tag or push a tag without the user's go-ahead.

## README

- Before every commit of a code change, check whether [`README.md`](README.md) needs updating (features, install,
  what deploy writes, code layout) and update it in the same commit. Read the passages about what changed and look
  for text the change made wrong, not only for what is missing.

## Other rules

- The app never writes into the game's CPK files. It writes only into its own folders (its livecpk root and kits
  folder) and its marked lines of sider.ini and map.txt, always through a deploy that backs up first and can be undone.
- Core logic (`flkm/` modules without Qt) stays separate from the widgets, so it is tested without a window.
- Claude is optional: every feature that does not need it (view, manual replace, kits from photos the user loads,
  deploy) works without the Claude Code CLI.
- Every button has a tooltip that says what it does (and what it does not touch, when that matters). Each widget's
  test file checks it with `conftest.buttons_without_tooltip`.
