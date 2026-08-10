"""Scope subset relation + non-compensatory control logic (spec §10, §29)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from risk_authority.domain import (
    ControlResult,
    ControlStatus,
    Scope,
    required_controls_satisfied,
    subset_violations,
    unsatisfied_controls,
)

NOW = datetime(2026, 8, 10, tzinfo=timezone.utc)


def test_equal_scope_is_contained():
    s = Scope(tools_allow=("a", "b"), max_autonomy_level=2)
    assert subset_violations(s, s) == []


def test_narrower_allow_is_contained():
    bound = Scope(tools_allow=("a", "b", "c"))
    candidate = Scope(tools_allow=("a",))
    assert subset_violations(candidate, bound) == []


def test_broader_allow_is_violation():
    bound = Scope(tools_allow=("a",))
    candidate = Scope(tools_allow=("a", "b"))
    assert subset_violations(candidate, bound)


def test_deny_must_be_superset():
    # Bound denies X; a candidate that fails to deny X is broader.
    bound = Scope(tools_deny=("refund.execute",))
    weaker = Scope(tools_deny=())
    assert subset_violations(weaker, bound)
    stronger = Scope(tools_deny=("refund.execute", "email.external"))
    assert subset_violations(stronger, bound) == []


def test_autonomy_ceiling():
    bound = Scope(max_autonomy_level=2)
    assert subset_violations(Scope(max_autonomy_level=3), bound)
    assert subset_violations(Scope(max_autonomy_level=1), bound) == []


def test_amount_ceiling_and_unbounded_bound():
    bound = Scope(max_transaction_minor_units=500000)
    assert subset_violations(Scope(max_transaction_minor_units=600000), bound)
    assert subset_violations(Scope(max_transaction_minor_units=None), bound)  # unbounded broader
    # Unbounded bound contains any candidate.
    assert subset_violations(Scope(max_transaction_minor_units=600000), Scope()) == []


def test_all_pass_is_satisfied():
    required = ("A", "B")
    results = (
        ControlResult("A", ControlStatus.PASS),
        ControlResult("B", ControlStatus.PASS),
    )
    assert required_controls_satisfied(required, results, NOW)


def test_missing_control_fails_non_compensatory():
    required = ("A", "B")
    results = (ControlResult("A", ControlStatus.PASS),)
    failed = unsatisfied_controls(required, results, NOW)
    assert failed == (("B", ControlStatus.MISSING),)


def test_no_pass_compensates_for_stale():
    required = ("A", "B")
    results = (
        ControlResult("A", ControlStatus.PASS),
        ControlResult(
            "B",
            ControlStatus.PASS,
            valid_until=NOW - timedelta(days=1),  # elapsed -> STALE
        ),
    )
    failed = unsatisfied_controls(required, results, NOW)
    assert failed == (("B", ControlStatus.STALE),)
    assert not required_controls_satisfied(required, results, NOW)


def test_unknown_is_not_coerced_to_pass():
    required = ("A",)
    results = (ControlResult("A", ControlStatus.UNKNOWN),)
    assert not required_controls_satisfied(required, results, NOW)


def test_not_applicable_is_satisfying():
    required = ("A",)
    results = (ControlResult("A", ControlStatus.NOT_APPLICABLE),)
    assert required_controls_satisfied(required, results, NOW)
