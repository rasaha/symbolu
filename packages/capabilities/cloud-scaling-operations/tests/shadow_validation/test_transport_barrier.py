"""Read-only transport barrier: only GET/HEAD/WATCH/LIST may transmit; writes blocked."""
from __future__ import annotations

import pytest

from shadow_validation.transport import (
    ReadOnlyTransportBarrier, ReadOnlyHTTPClient, ReadOnlyViolation,
    ALLOWED_METHODS, BLOCKED_METHODS, Destination,
)


def _barrier():
    return ReadOnlyTransportBarrier(clock=lambda: 1000.0)


@pytest.mark.parametrize("method", sorted(ALLOWED_METHODS))
def test_read_methods_allowed(method):
    b = _barrier()
    d = b.guard(method, "https://k8s.local/api", destination=Destination.KUBERNETES,
                call_site="t")
    assert d.allowed and d.blocked_reason is None
    assert not b.ledger.transmitted_write_methods()


@pytest.mark.parametrize("method", sorted(BLOCKED_METHODS))
def test_write_methods_blocked_before_transmission(method):
    b = _barrier()
    with pytest.raises(ReadOnlyViolation):
        b.guard(method, "https://k8s.local/api", call_site="t")
    # Blocked attempt is recorded, but never as an allowed transmission.
    assert b.ledger.transmitted_write_methods() == []
    assert b.ledger.entries[-1].blocked is True


def test_lowercase_and_unknown_methods_blocked():
    b = _barrier()
    for m in ("post", "patch", "delete", "frobnicate", ""):
        with pytest.raises(ReadOnlyViolation):
            b.guard(m, "https://svc.local", call_site="t")


def test_readonly_http_client_blocks_writes_without_touching_transport():
    b = _barrier()
    calls = {"n": 0}

    def transport(method, url, headers, timeout):
        calls["n"] += 1
        return (200, "ok")

    client = ReadOnlyHTTPClient(transport, b)
    assert client.get("https://svc.local/x")[0] == 200
    assert calls["n"] == 1
    with pytest.raises(ReadOnlyViolation):
        client.request("POST", "https://svc.local/mutate")
    assert calls["n"] == 1  # transport never called for the write
    assert not hasattr(client, "post")


def test_ledger_counts_and_endpoint_redaction():
    b = _barrier()
    b.guard("GET", "https://argo.local/app?token=secret-value&x=1",
            destination=Destination.ARGOCD, call_site="t")
    entry = b.ledger.entries[-1]
    assert "secret-value" not in entry.redacted_endpoint
    assert b.ledger.counts()["GET"]["allowed"] == 1
