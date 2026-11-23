"""Finding Claude Code (the claude CLI): the one the user chose, else on PATH, else where its installers put it, else
the one inside the Claude desktop app (the newest version). A candidate counts only when it answers --version. The
real CLI is never run by the tests."""

import subprocess

from flkm import claude

FIND = claude.find  # the real one: conftest's no_claude replaces it in every test


class FakeRun:
    """answers --version for the paths given, fails for the others"""

    def __init__(self, versions=None, fail=None):
        self.versions, self.fail, self.calls = versions or {}, fail, []

    def __call__(self, args, **kw):
        self.calls.append((args, kw))
        if self.fail:
            raise self.fail
        path = str(args[0])
        if path not in self.versions:
            return subprocess.CompletedProcess(args, 1, "", "not claude")
        return subprocess.CompletedProcess(args, 0, self.versions[path], "")


def touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def env_for(tmp_path):
    return {
        "USERPROFILE": str(tmp_path / "user"),
        "APPDATA": str(tmp_path / "roaming"),
        "LOCALAPPDATA": str(tmp_path / "local"),
    }


def desktop(tmp_path, version, build="abc"):
    return touch(tmp_path / "local" / "Claude-Data" / "claude_x1" / "claude-code" / version / build / "claude.exe")


def test_version_of_the_cli():
    run = FakeRun({"C:/c/claude.exe": "2.1.330 (Claude Code)\n"})
    assert claude.version("C:/c/claude.exe", run=run) == "2.1.330"
    args, kw = run.calls[0]
    assert args == ["C:/c/claude.exe", "--version"] and kw["timeout"] > 0 and kw["capture_output"]


def test_no_version_when_it_fails_or_says_something_else():
    assert claude.version("x", run=FakeRun()) is None  # exit code 1
    assert claude.version("x", run=FakeRun({"x": "hello"})) is None
    assert claude.version("x", run=FakeRun(fail=OSError("no such file"))) is None
    assert claude.version("x", run=FakeRun(fail=subprocess.TimeoutExpired("x", 15))) is None


def test_candidates_in_order(tmp_path):
    chosen = touch(tmp_path / "mine" / "claude.exe")
    on_path = touch(tmp_path / "bin" / "claude.cmd")
    installer = touch(tmp_path / "user" / ".local" / "bin" / "claude.exe")
    npm = touch(tmp_path / "roaming" / "npm" / "claude.cmd")
    old = desktop(tmp_path, "2.1.9")
    new = desktop(tmp_path, "2.1.330")
    found = claude.candidates(str(chosen), env=env_for(tmp_path), which=lambda name: str(on_path))
    assert found == [
        (chosen, "chosen"),
        (on_path, "PATH"),
        (installer, "installer"),
        (npm, "npm"),
        (new, "desktop app"),
        (old, "desktop app"),
    ]


def test_candidates_leave_out_what_is_not_there(tmp_path):
    assert claude.candidates(str(tmp_path / "gone.exe"), env=env_for(tmp_path), which=lambda name: None) == []
    assert claude.candidates(None, env={}, which=lambda name: None) == []


def test_find_takes_the_first_that_answers(tmp_path):
    installer = touch(tmp_path / "user" / ".local" / "bin" / "claude.exe")
    new = desktop(tmp_path, "2.1.330")
    run = FakeRun({str(new): "2.1.330 (Claude Code)"})  # the installer's copy is broken
    cli = FIND(None, run=run, env=env_for(tmp_path), which=lambda name: None)
    assert cli == claude.Cli(new, "2.1.330", "desktop app")
    assert [c[0][0] for c in run.calls] == [str(installer), str(new)]


def test_find_nothing(tmp_path):
    assert FIND(None, run=FakeRun(), env=env_for(tmp_path), which=lambda name: None) is None


def test_check_a_file_the_user_chose(tmp_path):
    exe = touch(tmp_path / "claude.exe")
    assert claude.check(exe, run=FakeRun({str(exe): "2.0.1 (Claude Code)"})) == claude.Cli(exe, "2.0.1", "chosen")
    assert claude.check(exe, run=FakeRun()) is None


def test_describe():
    assert claude.describe(None) == "Claude Code not found"
    assert claude.describe(claude.Cli(claude.Path("c.exe"), "2.1.3", "desktop app")) == "Claude Code 2.1.3"
