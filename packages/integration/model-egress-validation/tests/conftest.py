"""The suite never opens a socket: refused for every test, not only the ones that think
about it (LP-7 ruling 11)."""

from __future__ import annotations

import socket

import pytest


def _refuse(*args, **kwargs):
    raise AssertionError("the validation suite opened a socket")


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)
    yield
