"""Mocked-but-structurally-correct simulation producers.

Each producer returns a frozen *structured* simulation evidence envelope
(``action_gate_ref.evidence`` with ``is_simulation=True``) bound to the exact
action hash, producer version, validity interval, current state hash, and
simulation inputs. Simulation is NEVER a bare ``safe: true`` — the content is a
structured predicted-change set. Changing the proposed action changes the action
hash, which the binding check rejects (the evidence no longer applies).
"""

from __future__ import annotations

from ._core import ref_evidence

PRODUCER_VERSION = "sim-ref/1.0.0"

_KIND_CONTENT = {
    "terraform_plan": lambda inp: {
        "producer_version": PRODUCER_VERSION, "engine": "terraform-plan",
        "predicted_changes": [{"resource": inp.get("workspace", "?"), "op": "update"}],
        "affected_resources": [inp.get("workspace", "?")],
        "coverage": "0.95", "destroy_count": "0"},
    "kubernetes_dryrun": lambda inp: {
        "producer_version": PRODUCER_VERSION, "engine": "kubectl-dry-run",
        "predicted_changes": [{"resource": inp.get("name", "?"), "op": inp.get("op", "apply")}],
        "affected_resources": [inp.get("name", "?")], "coverage": "0.9"},
    "iam_delta": lambda inp: {
        "producer_version": PRODUCER_VERSION, "engine": "iam-policy-simulator",
        "permission_delta": {"added": inp.get("added", []), "removed": []},
        "affected_resources": [inp.get("role", "?")], "coverage": "1.0"},
    "fs_diff": lambda inp: {
        "producer_version": PRODUCER_VERSION, "engine": "fs-diff",
        "predicted_changes": [{"resource": inp.get("path", "?"), "op": "write"}],
        "affected_resources": [inp.get("path", "?")], "coverage": "1.0"},
}


def produce(kind: str, *, action_hash: str, state_hash: str, clock,
            inputs: dict | None = None, fidelity: str = "HIGH") -> dict:
    """Produce a bound, structured simulation-evidence envelope."""
    if kind not in _KIND_CONTENT:
        raise ValueError(f"unknown simulation kind {kind!r}")
    content = _KIND_CONTENT[kind](inputs or {})
    content["state_hash"] = state_hash          # bind to approval-time state
    content["simulation_inputs"] = inputs or {}
    return ref_evidence.build_evidence(
        bound_to=action_hash, producer=f"{kind}:{PRODUCER_VERSION}",
        generated_at=clock.now(), valid_until=clock.plus(900),
        evidence_version="1", kind="simulation", fidelity_or_confidence=fidelity,
        is_simulation=True, content=content)


def build_provenance(kind: str, *, action_hash: str, clock) -> dict:
    """Auto-supplied build provenance (e.g. a signed artifact from the registry)."""
    return ref_evidence.build_evidence(
        bound_to=action_hash, producer="artifact-registry/1.0", generated_at=clock.now(),
        valid_until=clock.plus(900), evidence_version="1", kind=kind,
        fidelity_or_confidence="HIGH",
        content={"artifact": "sha256:cafebabe", "signed": "yes", "provenance": "slsa-3"})
