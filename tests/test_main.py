import runpy

import pytest

from flkm import cli


def test_python_m_flkm_runs_the_cli(monkeypatch):
    called = []
    monkeypatch.setattr(cli, "main", lambda argv=None: called.append(argv) or 0)
    with pytest.raises(SystemExit) as e:
        runpy.run_module("flkm", run_name="__main__")
    assert e.value.code == 0 and called == [None]
