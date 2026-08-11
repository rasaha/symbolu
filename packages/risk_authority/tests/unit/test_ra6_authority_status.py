"""RA-6 leaf-contract unit tests: freshness policy + signal validation (§3, §13).

These exercise the *pure* leaf additions only — the risk-tiered bounded-staleness
predicate (Policy C), the UNINITIALIZED-is-not-empty rule (R-1/I13), and the
neutral reassessment-signal validation. The stateful runtime (persistence,
writer, cache sync, reassessor) is tested in the status-runtime package.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from risk_authority.domain import (
    AUTHORITY_SIGNAL_SCHEMA_VERSION,
    AuthorityReassessmentSignal,
    RiskClass,
    SignalChangeType,
    SignalTarget,
    SignalTargetType,
)
from risk_authority.services.authority_status import (
    ALLOW,
    ALLOW_WITH_BOUNDED_STALE_STATUS,
    DENY,
    AuthorityStatusSnapshot,
    StalenessPolicy,
    evaluate_status_freshness,
)
from risk_authority.services.revocation import RevocationState

NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
TENANT = "tenant-a"


def _snapshot(*, as_of, tenants=(TENANT,), state=None) -> AuthorityStatusSnapshot:
    return AuthorityStatusSnapshot(
        revocation_state=state or RevocationState(),
        as_of=as_of,
        tenant_ids=frozenset(tenants),
    )


# --------------------------------------------------------------------------- #
# Freshness / Policy C (§3)                                                    #
# --------------------------------------------------------------------------- #
def test_uninitialized_denies_every_tier():
    snap = AuthorityStatusSnapshot.uninitialized()
    policy = StalenessPolicy.fail_closed_defaults()
    for tier in RiskClass:
        status = evaluate_status_freshness(
            snapshot=snap, tenant_id=TENANT, tier=tier, now=NOW, policy=policy
        )
        assert status.outcome == DENY
        assert status.initialized is False


def test_initialized_but_tenant_not_covered_denies():
    # Snapshot synced, but not for THIS tenant → uninitialized-for-tenant (R-1).
    snap = _snapshot(as_of=NOW, tenants=("other-tenant",))
    policy = StalenessPolicy.fail_closed_defaults()
    status = evaluate_status_freshness(
        snapshot=snap, tenant_id=TENANT, tier=RiskClass.LOW, now=NOW, policy=policy
    )
    assert status.outcome == DENY
    assert "uninitialized for tenant" in status.reasons[0]


def test_fresh_low_risk_allows_plain_when_zero_age():
    snap = _snapshot(as_of=NOW)
    policy = StalenessPolicy.fail_closed_defaults()
    status = evaluate_status_freshness(
        snapshot=snap, tenant_id=TENANT, tier=RiskClass.LOW, now=NOW, policy=policy
    )
    assert status.outcome == ALLOW


def test_bounded_stale_low_risk_within_bound_allows_annotated():
    snap = _snapshot(as_of=NOW - timedelta(seconds=100))  # LOW bound is 300
    policy = StalenessPolicy.fail_closed_defaults()
    status = evaluate_status_freshness(
        snapshot=snap, tenant_id=TENANT, tier=RiskClass.LOW, now=NOW, policy=policy
    )
    assert status.outcome == ALLOW_WITH_BOUNDED_STALE_STATUS


def test_low_risk_beyond_bound_denies():
    snap = _snapshot(as_of=NOW - timedelta(seconds=1000))  # > 300
    policy = StalenessPolicy.fail_closed_defaults()
    status = evaluate_status_freshness(
        snapshot=snap, tenant_id=TENANT, tier=RiskClass.LOW, now=NOW, policy=policy
    )
    assert status.outcome == DENY


def test_high_risk_stale_denies_where_low_would_allow():
    # 100s: within LOW's 300 bound, but past HIGH's 30 bound.
    snap = _snapshot(as_of=NOW - timedelta(seconds=100))
    policy = StalenessPolicy.fail_closed_defaults()
    low = evaluate_status_freshness(
        snapshot=snap, tenant_id=TENANT, tier=RiskClass.LOW, now=NOW, policy=policy
    )
    high = evaluate_status_freshness(
        snapshot=snap, tenant_id=TENANT, tier=RiskClass.HIGH, now=NOW, policy=policy
    )
    assert low.outcome == ALLOW_WITH_BOUNDED_STALE_STATUS
    assert high.outcome == DENY


def test_critical_requires_essentially_fresh():
    snap = _snapshot(as_of=NOW - timedelta(seconds=1))
    policy = StalenessPolicy.fail_closed_defaults()
    status = evaluate_status_freshness(
        snapshot=snap, tenant_id=TENANT, tier=RiskClass.CRITICAL, now=NOW, policy=policy
    )
    assert status.outcome == DENY  # CRITICAL default bound is 0s


def test_unknown_tier_fails_closed_as_critical():
    snap = _snapshot(as_of=NOW - timedelta(seconds=1))
    policy = StalenessPolicy.fail_closed_defaults()
    status = evaluate_status_freshness(
        snapshot=snap, tenant_id=TENANT, tier=None, now=NOW, policy=policy
    )
    assert status.outcome == DENY


def test_platform_ceiling_caps_tenant_config():
    # A tenant tries to widen LOW staleness to 10_000s; ceiling is 600.
    policy = StalenessPolicy(
        max_staleness_seconds={RiskClass.LOW: 10_000.0},
        platform_ceiling_seconds=600.0,
    )
    assert policy.bound_for(RiskClass.LOW) == 600.0
    snap = _snapshot(as_of=NOW - timedelta(seconds=800))
    status = evaluate_status_freshness(
        snapshot=snap, tenant_id=TENANT, tier=RiskClass.LOW, now=NOW, policy=policy
    )
    assert status.outcome == DENY  # 800 > 600 ceiling


def test_future_snapshot_clock_skew_treated_as_zero_age():
    snap = _snapshot(as_of=NOW + timedelta(seconds=50))
    policy = StalenessPolicy.fail_closed_defaults()
    status = evaluate_status_freshness(
        snapshot=snap, tenant_id=TENANT, tier=RiskClass.CRITICAL, now=NOW, policy=policy
    )
    assert status.outcome == ALLOW  # effective age clamped to 0


# --------------------------------------------------------------------------- #
# Reassessment signal validation (§13)                                        #
# --------------------------------------------------------------------------- #
def _signal(**over) -> AuthorityReassessmentSignal:
    base = dict(
        schema_version=AUTHORITY_SIGNAL_SCHEMA_VERSION,
        event_id="evt-1",
        tenant_id=TENANT,
        target=SignalTarget(SignalTargetType.ENVELOPE, "env-1"),
        change_type=SignalChangeType.EVIDENCE_INVALIDATED,
        source="evidence-assurance",
        source_version="1.0",
        observed_at=NOW,
        reason="evidence retracted",
        correlation_id="corr-1",
    )
    base.update(over)
    return AuthorityReassessmentSignal(**base)


def test_valid_signal_has_no_errors():
    assert _signal().validation_errors() == ()


def test_signal_has_no_authority_fields():
    # Structural guarantee (I2): the type simply has no ALLOW/scope/token field.
    fields = set(_signal().__dataclass_fields__)
    for forbidden in ("allow", "decision", "scope", "authority", "grant", "token"):
        assert forbidden not in fields


def test_unsupported_schema_version_rejected():
    errs = _signal(schema_version="999").validation_errors()
    assert any("schema_version" in e for e in errs)


def test_missing_required_fields_rejected():
    assert any("event_id" in e for e in _signal(event_id="").validation_errors())
    assert any("tenant_id" in e for e in _signal(tenant_id="").validation_errors())
    assert any("correlation_id" in e for e in _signal(correlation_id="").validation_errors())
    assert any("source" in e for e in _signal(source="").validation_errors())


def test_non_tenant_target_requires_target_id():
    bad = _signal(target=SignalTarget(SignalTargetType.SUBJECT, ""))
    assert any("target_id" in e for e in bad.validation_errors())


def test_tenant_target_allows_empty_target_id():
    ok = _signal(target=SignalTarget(SignalTargetType.TENANT, ""))
    assert ok.validation_errors() == ()
