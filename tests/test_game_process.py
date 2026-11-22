"""Whether the game is running (FL_2027.exe in the Windows task list): the app writes into the game only when it is
closed. When the task list cannot be read the answer is unknown (None)."""

import subprocess
from types import SimpleNamespace

from flkm.game import process


def fake_run(stdout):
    calls = []

    def run(args, **kw):
        calls.append(args)
        return SimpleNamespace(stdout=stdout, returncode=0)

    run.calls = calls
    return run


def test_game_running():
    run = fake_run('"FL_2027.exe","12345","Console","1","1.234.567 K"\r\n')
    assert process.game_running(run=run) is True
    assert run.calls == [["tasklist", "/FI", "IMAGENAME eq FL_2027.exe", "/NH", "/FO", "CSV"]]


def test_game_not_running():
    run = fake_run("INFO: No tasks are running which match the specified criteria.\r\n")
    assert process.game_running(run=run) is False


def test_task_list_that_cannot_be_read_gives_unknown():
    def broken(args, **kw):
        raise OSError("tasklist not found")

    assert process.game_running(run=broken) is None

    def failing(args, **kw):
        raise subprocess.SubprocessError("timeout")

    assert process.game_running(run=failing) is None


def test_real_task_list_does_not_list_a_program_that_is_not_running():
    assert process.game_running("no_such_program_flkm.exe") is False
