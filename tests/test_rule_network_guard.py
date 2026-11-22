"""Tests must never reach the network: conftest.py refuses every connection except localhost."""

import socket

import pytest

import conftest


@pytest.mark.parametrize("host", ["example.com", "pypi.org", "8.8.8.8"])
def test_outgoing_connections_refused(host):
    with pytest.raises(conftest.NetworkBlocked):
        socket.create_connection((host, 443), timeout=1)


def test_localhost_allowed():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        with socket.create_connection(server.getsockname(), timeout=1) as client:
            connection, _ = server.accept()
            with connection:
                client.sendall(b"x")
                assert connection.recv(1) == b"x"


def test_dns_lookups_of_outside_hosts_refused():
    with pytest.raises(conftest.NetworkBlocked):
        socket.getaddrinfo("example.com", 443)
    assert socket.getaddrinfo("localhost", 80)
