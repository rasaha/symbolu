"""Phase 5A holds no clock — proven by import graph, AST and API shape.

The package must not import a wall clock, read ambient time, accept a ``now`` or an
``evaluation_time``, generate a trusted timestamp, or decide current validity or freshness.
It may carry already-bound timestamp facts forward, and it labels them as facts.
"""

from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

import ugence_cloud_scaling_authorization_contracts as pkg
from ugence_cloud_scaling_authorization_contracts import (
    CapacityAuthorizationCandidate,
    ProducerAttestationEvidence,
    build_capacity_authorization_candidate,
    reconcile_phase4,
)

SRC = pathlib.Path(pkg.__file__).resolve().parent
SOURCES = sorted(SRC.rglob("*.py"))


def test_no_clock_module_is_imported():
    forbidden_roots = {"time", "calendar", "sched"}
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden_roots, (
                        f"{path.name} imports {alias.name}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                root = node.module.split(".")[0]
                assert root not in forbidden_roots, f"{path.name} imports {node.module}"
                if node.module == "datetime":
                    # ``datetime`` itself is allowed for typing and tz normalization, but
                    # importing the clock-bearing names is not.
                    for alias in node.names:
                        assert alias.name in {"datetime", "timezone", "timedelta"}, (
                            f"{path.name} imports datetime.{alias.name}"
                        )


def test_no_ambient_now_is_read():
    forbidden_attrs = {"now", "utcnow", "today", "fromtimestamp", "monotonic", "time"}
    for path in SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in forbidden_attrs, (
                    f"{path.name} calls .{node.func.attr}(), reading ambient time"
                )


def test_no_public_callable_accepts_a_clock_or_evaluation_time():
    for name in pkg.__all__:
        obj = getattr(pkg, name)
        if not callable(obj):
            continue
        try:
            params = set(inspect.signature(obj).parameters)
        except (TypeError, ValueError):  # pragma: no cover - non-introspectable
            continue
        for forbidden in ("now", "clock", "evaluation_time", "current_time", "as_of"):
            assert forbidden not in params, f"{name} accepts {forbidden}"


def test_builder_and_reconciler_accept_no_time_parameter():
    for fn in (build_capacity_authorization_candidate, reconcile_phase4):
        params = set(inspect.signature(fn).parameters)
        assert not params & {"now", "clock", "evaluation_time", "as_of"}


def test_carried_timestamps_are_named_as_facts():
    """Every carried timestamp field says it is an unevaluated fact."""

    fields = CapacityAuthorizationCandidate.__dataclass_fields__
    timestamp_fields = [
        n for n, f in fields.items() if "datetime" in str(f.type).lower()
    ]
    assert timestamp_fields, "the candidate should carry validity facts"
    for name in timestamp_fields:
        assert name.endswith("_fact"), (
            f"{name} carries a timestamp but is not labelled as an unevaluated fact"
        )


def test_no_field_or_property_claims_current_validity():
    fields = set(CapacityAuthorizationCandidate.__dataclass_fields__)
    attrs = set(dir(CapacityAuthorizationCandidate))
    for forbidden in (
        "is_valid", "valid_now", "is_current", "is_fresh", "expired", "is_expired",
        "not_before", "time_remaining",
    ):
        assert forbidden not in fields and forbidden not in attrs


def test_a_long_expired_decision_still_builds_a_candidate(projection, decision, attestation,
                                                          target_scope, policy_binding):
    """Freshness is Phase 5B's: Phase 5A neither enforces nor claims it.

    This is the positive proof that no clock is consulted — an attestation stamped far in
    the past is carried forward as a fact, not rejected as stale, because Phase 5A has no
    clock with which to call it stale.
    """

    from datetime import timedelta

    ancient = attestation.issued_at - timedelta(days=3650)
    from conftest import build_attestation

    old = build_attestation(
        recommendation_digest=projection.recommendation_digest, issued_at=ancient
    )
    candidate = build_capacity_authorization_candidate(
        projection=projection, decision=decision, producer_attestation=old,
        policy_binding=policy_binding, target_scope=target_scope,
    )
    assert candidate.attestation_issued_at_fact == ancient
    # And it still grants nothing — carrying an old fact is not endorsing it.
    assert candidate.grants_authority is False
