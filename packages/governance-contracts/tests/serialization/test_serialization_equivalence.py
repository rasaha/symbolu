"""C3/§12 — serialization & digest equivalence, pinned to the pre-migration
baseline (docs/migrations/governance_contracts/baseline_serialization.json).

Constructs representative instances of every public dataclass contract and
asserts their asdict, canonical JSON, fingerprint, repr, constructor signature,
enum value maps, and error failure-classes are byte-identical to the recorded
baseline — the guard that the physical move changed no contract semantics.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import pathlib

import ugence_governance_contracts as A
from ugence_governance_contracts.contracts.base import BaseProvider  # noqa: F401

_BASELINE = json.loads(
    (pathlib.Path(__file__).resolve().parent / "frozen_contract_fixtures.json").read_text()
)


def _fingerprint(payload):
    import hashlib
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _instances():
    return {
        "ActionGovernanceRequest": A.ActionGovernanceRequest(
            action_type="deploy", requested_parameters={"ns": "prod"},
            actor="agent://x", correlation_id="c1", policy_refs=("p1",)),
        "ActionGovernanceResult": A.ActionGovernanceResult(
            outcome=A.ActionGovernanceOutcome.AUTHORIZED, constraints=("c",), fingerprint="fp"),
        "AssertionGovernanceRequest": A.AssertionGovernanceRequest(
            assertion="rev up", evidence_refs=("e1",), correlation_id="c2"),
        "AssertionGovernanceResult": A.AssertionGovernanceResult(
            coverage=A.AssertionCoverage.SUPPORTED, evidence_coverage=1.0,
            covered_evidence_refs=("e1",)),
        "ExecutionDispatchRequest": A.ExecutionDispatchRequest(
            action_type="do", parameters={"k": "v"}, idempotency_key="i1", correlation_id="c3"),
        "ExecutionDispatchResult": A.ExecutionDispatchResult(accepted=True, external_request_id="r1"),
        "ExecutionObservation": A.ExecutionObservation(
            business_outcome=A.ExecutionBusinessOutcome.SUCCEEDED, final=True),
        "ProviderCapabilities": A.ProviderCapabilities(
            kind=A.ProviderKind.ACTION_GOVERNANCE, features=frozenset({"f1"}), deterministic=True),
        "ProviderCompatibility": A.ProviderCompatibility(contract_version="1.0.0"),
        "ProviderHealth": A.ProviderHealth(
            state=A.ProviderLifecycleState.AVAILABLE, healthy=True, detail="AVAILABLE"),
        "ProviderInvocationRecord": None,  # framework-owned; see note below
    }


def test_dataclass_serialization_matches_baseline():
    insts = _instances()
    for name, base in _BASELINE["instances"].items():
        if name == "ProviderInvocationRecord":
            continue  # framework observability record — stays in governance_providers
        obj = insts[name]
        d = dataclasses.asdict(obj)
        # Baseline was stored as JSON (tuples -> lists); compare JSON-normalized so
        # the canonical serialized representation is what's asserted byte-for-byte.
        assert json.loads(json.dumps(d, default=str)) == base["asdict"], name
        assert json.dumps(d, sort_keys=True, default=str) == base["asdict_json"], name
        assert _fingerprint({k: str(v) for k, v in d.items()}) == base["fingerprint"], name
        assert repr(obj) == base["repr"], name
        assert str(inspect.signature(type(obj))) == base["ctor_sig"], name


def test_enum_value_maps_match_baseline():
    for ename, values in _BASELINE["enums"].items():
        E = getattr(A, ename)
        assert {m.name: m.value for m in E} == values, ename


def test_error_failure_classes_match_baseline():
    for ename, fc in _BASELINE["error_failure_classes"].items():
        assert getattr(A, ename).failure_class.value == fc, ename


def test_round_trip_dict_reconstruction():
    req = A.ActionGovernanceRequest(action_type="deploy", actor="a", policy_refs=("p",))
    d = dataclasses.asdict(req)
    # tuples serialize to lists in asdict; reconstruct faithfully
    rebuilt = A.ActionGovernanceRequest(
        action_type=d["action_type"], actor=d["actor"], policy_refs=tuple(d["policy_refs"]))
    assert rebuilt == req
