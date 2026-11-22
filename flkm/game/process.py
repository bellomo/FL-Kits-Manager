"""Whether the game is running: the app writes into the game folder only while the game is closed."""

import subprocess

GAME_EXE = "FL_2027.exe"


def game_running(exe: str = GAME_EXE, run=subprocess.run) -> bool | None:
    """True or False from the Windows task list; None when the task list cannot be read"""
    try:
        out = run(
            ["tasklist", "/FI", f"IMAGENAME eq {exe}", "/NH", "/FO", "CSV"],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return f'"{exe.lower()}"' in out.stdout.lower()
