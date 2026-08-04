"""Mutation canaries: every mutation entrypoint is blocked under shadow configuration."""
from __future__ import annotations

from shadow_mutation_canaries import run_mutation_canaries


def test_all_canaries_blocked_and_zero_transmissions():
    res = run_mutation_canaries()
    assert res["all_blocked"] is True, [c for c in res["canaries"] if not c["passed"]]
    assert res["transmitted_write_methods"] == []
    assert res["real_network_transmissions"] == 0


def test_every_required_entrypoint_covered():
    res = run_mutation_canaries()
    names = " ".join(c["entrypoint"] for c in res["canaries"]).lower()
    for required in ("controlledscalingexecutor", "kubernetesscalingexecutor",
                     "gateexecutor", "gateactuator", "recommendengine",
                     "productionorchestrator", "rollbackcoordinator",
                     "admission-policy", "webhook", "metricsexporter",
                     "otelexporter", "readonlyhttpclient"):
        assert required in names, f"missing canary for {required}"


def test_canary_records_are_all_proposed_or_blocked():
    res = run_mutation_canaries()
    for c in res["canaries"]:
        assert c["transport_write_calls"] == 0, c
        assert c["fallback_bypass"] is False, c


def test_gate_executor_canary_never_leaks_token():
    res = run_mutation_canaries()
    gate = [c for c in res["canaries"] if c["entrypoint"].startswith("GateExecutor")][0]
    assert "super-secret-token" not in gate["detail"]
