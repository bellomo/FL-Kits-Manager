"""Shared test set-up: no network, Qt without a screen, a temporary data folder and a fake game folder (never the
real game, never the user's settings)."""

import os
import socket

import pytest

# Qt draws off screen in tests (CI has no display); set before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# NETWORK-GUARD: all outgoing connections except localhost are refused in tests.
# Installed when pytest loads this file, before any test module is imported.
class NetworkBlocked(OSError):
    pass


_LOCAL_NAMES = {"localhost", "127.0.0.1", "::1", None}
_AF_UNIX = getattr(socket, "AF_UNIX", None)


def _is_local_host(host) -> bool:
    host = host.decode() if isinstance(host, bytes) else host
    return host in _LOCAL_NAMES or str(host).startswith("127.")


def _guard(original):
    def guarded(self, address, *args, **kwargs):
        if self.family != _AF_UNIX and not _is_local_host(address[0]):
            raise NetworkBlocked(f"network access blocked in tests: {address}")
        return original(self, address, *args, **kwargs)

    return guarded


_getaddrinfo = socket.getaddrinfo


def _guarded_getaddrinfo(host, *args, **kwargs):
    if not _is_local_host(host):
        raise NetworkBlocked(f"network access blocked in tests: {host}")
    return _getaddrinfo(host, *args, **kwargs)


socket.socket.connect = _guard(socket.socket.connect)
socket.socket.connect_ex = _guard(socket.socket.connect_ex)
socket.getaddrinfo = _guarded_getaddrinfo


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    """a temporary app data folder for every test: the user's real settings and staging are never touched"""
    h = tmp_path / "flkm_home"
    monkeypatch.setenv("FLKM_HOME", str(h))
    return h


@pytest.fixture
def game(tmp_path):
    """an empty fake game folder; tests add the files they need (sider.ini, map.txt, tiny CPK/FTEX)"""
    g = tmp_path / "game"
    (g / "SiderAddons").mkdir(parents=True)
    return g
