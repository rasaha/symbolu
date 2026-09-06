"""End-to-end shadow governed-loop tests.

These exercise the real ActionGate and TAP engines plus the Context Minimization
and operational-clearance adapters through the orchestrator, and assert the
non-compensatory gate behaviour on the three Kubernetes scenarios.
"""

from __future__ import annotations

import pytest

from ugence_console_api.audit import AuditStore
from ugence_console_api import orchestrator, scenarios
from ugence_console_api.capabilities import (
    action_control,
    context_gateway,
    truth_evidence,
)

_MODULES_READY = all([
    action_control.available()[0],
    truth_evidence.available()[0],
    context_gateway.available()[0],
])

pytestmark = pytest.mark.skipif(
    not _MODULES_READY, reason="platform module libraries not importable in this env")


def _run(scenario_id: str):
    audit = AuditStore()
    req = scenarios.SCENARIOS[scenario_id]["request"].model_copy(deep=True)
    req.correlation_id = None
    result = orchestrator.run(req, audit)
    return result, audit


def test_clean_shadow_allow():
    result, audit = _run("k8s_rollout_restart_clean")
    assert result.would_execute is True
    assert result.mode.value == "shadow"
    assert "OBSERVED (shadow)" in result.final_disposition
    # Stages: Gateway, Verify, Authorize, Clear, Record.
    stages = [s.stage for s in result.stages]
    assert stages == ["Gateway", "Verify", "Authorize", "Clear", "Record"]
    # Audit chain reconstructable by correlation id.
    chain = audit.get(result.correlation_id)
    assert chain is not None and chain.cer_id == result.cer_id


def test_operational_hold_blocks_execution():
    result, _ = _run("k8s_delete_during_freeze")
    clear_stage = next(s for s in result.stages if s.stage == "Clear")
    assert clear_stage.decision == "HOLD"
    assert result.would_execute is False  # authorized but not safe now


def test_unsupported_assertion_blocks_execution():
    result, _ = _run("k8s_unsupported_claim")
    verify_stage = next(s for s in result.stages if s.stage == "Verify")
    assert verify_stage.decision != "SUPPORTED"
    assert result.would_execute is False


def test_cer_is_stable_for_same_action():
    a, _ = _run("k8s_rollout_restart_clean")
    b, _ = _run("k8s_rollout_restart_clean")
    # Same canonical action envelope -> same CER identity across runs.
    assert a.cer_id == b.cer_id
