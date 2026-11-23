"""One build command for everyone: scripts/build.ps1 builds the one-folder exe and smoke-tests it. The local
post-commit hook (scripts/hooks, enabled with `git config core.hooksPath scripts/hooks`) runs it after every commit,
in the background; the release workflow runs the same script."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build.ps1"


def test_build_script_makes_the_one_folder_exe_and_smoke_tests_it():
    text = BUILD.read_text(encoding="utf-8")
    assert "--onedir" in text and "--onefile" not in text
    assert "--name FLKitsManager" in text
    assert "--smoke-test" in text


def test_the_exe_has_the_app_icon_and_the_windows_too():
    text = BUILD.read_text(encoding="utf-8")
    assert r'--icon "$root\flkm\flkm.ico"' in text
    assert r'--add-data "$root\flkm\flkm.ico;flkm"' in text


def test_post_commit_hook_runs_the_build_script_in_the_background():
    hook = (ROOT / "scripts" / "hooks" / "post-commit").read_text(encoding="utf-8")
    assert hook.startswith("#!/bin/sh")
    assert "scripts/build.ps1" in hook
    assert hook.rstrip().endswith("&")  # the commit does not wait for the build


def test_release_workflow_uses_the_same_build_script():
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    assert "scripts/build.ps1" in workflow
    assert "pyinstaller " not in workflow  # no second copy of the build command
