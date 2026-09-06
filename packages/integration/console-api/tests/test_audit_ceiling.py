"""CP-4 — the in-memory ceiling is disclosed on every answer.

The store is allowed to stay in memory. What is not allowed is a reader having to infer
that from silence. So the ceiling rides on all five answers as a header, and inside the
three bodies that either describe the service or carry a decision trail.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi", reason="the console API is a FastAPI service")

from ugence_console_api.app import AUDIT_CEILING_HEADER, SERVED_ROUTES, create_app  # noqa: E402
from ugence_console_api.audit import AUDIT_CEILING, AuditStore  # noqa: E402
from ugence_console_api.models import AuditChain, AuditEntry  # noqa: E402


def _client():
    testclient = pytest.importorskip(
        "fastapi.testclient", reason="TestClient needs httpx")
    return testclient.TestClient(create_app(), raise_server_exceptions=False)


def test_the_ceiling_says_the_two_things_that_matter():
    lowered = AUDIT_CEILING.lower()
    assert "one process" in lowered
    assert "lost on restart" in lowered
    assert "not a durable" in lowered


def test_the_header_and_the_body_are_one_constant():
    """The disclosure cannot drift between the two places it appears, because there is
    only one string."""
    from ugence_console_api import models

    assert AUDIT_CEILING is models.AUDIT_CEILING


def test_every_served_answer_carries_the_header():
    client = _client()
    # A GET against each served path, path parameters filled with a value that does not
    # exist: a 404 is still an answer, and CP-4 says *every* answer.
    probes = [
        ("GET", "/health"),
        ("GET", "/v1/audit"),
        ("GET", "/v1/audit/no-such-correlation"),
        ("POST", "/v1/governed-loop/scenario/no-such-scenario"),
        ("POST", "/v1/governed-loop/shadow"),
    ]
    assert len(probes) == len(SERVED_ROUTES)
    for method, path in probes:
        response = client.request(method, path, json={} if method == "POST" else None)
        assert response.headers.get(AUDIT_CEILING_HEADER) == AUDIT_CEILING, path


def test_health_declares_the_ceiling_in_its_body():
    body = _client().get("/health").json()
    assert body["audit_ceiling"] == AUDIT_CEILING


def test_a_reconstructed_chain_declares_the_ceiling_it_was_read_at():
    chain = AuditChain(
        correlation_id="corr-1", cer_id="cer-1", mode="shadow",
        final_disposition="OBSERVED (shadow)",
        entries=[AuditEntry(stage="Record", module="ActionGate",
                            decision="RECORDED", summary="recorded")],
    )
    store = AuditStore()
    store.record(chain)
    assert store.get("corr-1").audit_ceiling == AUDIT_CEILING
    assert chain.model_dump()["audit_ceiling"] == AUDIT_CEILING


def test_the_loop_result_qualifies_its_own_recorded_flag():
    """``recorded: true`` is the claim CP-4 exists to bound, so the bound travels with
    it in the same body."""
    from ugence_console_api.models import GovernedLoopResult

    fields = GovernedLoopResult.model_fields
    assert "audit_ceiling" in fields
    assert fields["audit_ceiling"].default == AUDIT_CEILING


def test_the_ceiling_is_not_optional_anywhere_it_appears():
    """A field a serializer may omit is not a disclosure. Both models emit it with no
    argument supplied."""
    from ugence_console_api.models import AuditChain as Chain

    dumped = Chain(correlation_id="c", cer_id="x", mode="shadow",
                   final_disposition="d", entries=[]).model_dump()
    assert dumped["audit_ceiling"] == AUDIT_CEILING


def test_the_durable_alternative_is_not_quietly_wired_in():
    """CP-4 keeps ``control-plane-root`` for a later ruling. Depending on it now would
    make the disclosure false in the other direction."""
    import ugence_console_api.audit as audit_module

    assert "control_plane_root" not in audit_module.__dict__
