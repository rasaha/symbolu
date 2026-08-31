"""Restriction algebra (RA-4.5 §12) — composition may tighten, never enlarge."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from risk_authority.domain import Scope

from ugence_risk_authority_runtime import (
    GovernanceRestrictions,
    RiskAuthorityDisposition,
    RiskAuthorityMachineResult,
    apply_restrictions,
)

NOW = datetime(2026, 8, 10, 12, 0, 0, tzinfo=timezone.utc)

RA_SCOPE = Scope(
    purposes=("CUSTOMER_REFUND_REVIEW",),
    tools_allow=("crm.read", "refund.prepare"),
    tools_deny=("refund.execute",),
    data_allow=("CUSTOMER_PII",),
    destinations=("internal://finance",),
    jurisdictions=("US",),
    max_autonomy_level=2,
    max_transaction_minor_units=500000,
)


def ra(expires_at=None) -> RiskAuthorityMachineResult:
    return RiskAuthorityMachineResult(
        disposition=RiskAuthorityDisposition.ALLOW,
        scope=RA_SCOPE,
        expires_at=expires_at,
    )


def test_amount_stricter_provider_wins():
    eff = apply_restrictions(ra(), [GovernanceRestrictions(max_amount_minor_units=300000)])
    assert eff.max_amount_minor_units == 300000  # $3k < $5k
    assert not eff.is_empty()


def test_amount_broader_provider_cannot_raise_ra_ceiling():
    eff = apply_restrictions(ra(), [GovernanceRestrictions(max_amount_minor_units=1000000)])
    assert eff.max_amount_minor_units == 500000  # RA $5k cap holds


def test_expiry_only_shortens_never_extends():
    ra_exp = NOW + timedelta(hours=1)
    # A later provider expiry cannot extend RA validity (F-B).
    eff = apply_restrictions(
        ra(expires_at=ra_exp),
        [GovernanceRestrictions(expires_at=NOW + timedelta(hours=5))],
    )
    assert eff.expires_at == ra_exp
    # An earlier provider expiry shortens.
    eff2 = apply_restrictions(
        ra(expires_at=ra_exp),
        [GovernanceRestrictions(expires_at=NOW + timedelta(minutes=10))],
    )
    assert eff2.expires_at == NOW + timedelta(minutes=10)


def test_allow_set_intersection_shrinks():
    eff = apply_restrictions(
        ra(),
        [GovernanceRestrictions(allow_intersections={"tools_allow": frozenset({"crm.read"})})],
    )
    assert set(eff.tools_allow) == {"crm.read"}
    assert set(eff.tools_allow) <= set(RA_SCOPE.tools_allow)


def test_deny_set_union_grows_denial():
    eff = apply_restrictions(
        ra(),
        [GovernanceRestrictions(deny_unions={"tools_deny": frozenset({"email.external"})})],
    )
    assert {"refund.execute", "email.external"} <= set(eff.tools_deny)


def test_allow_set_emptied_marks_empty_scope():
    eff = apply_restrictions(
        ra(),
        [GovernanceRestrictions(allow_intersections={"tools_allow": frozenset({"nonexistent.tool"})})],
    )
    assert set(eff.tools_allow) == set()
    assert eff.is_empty()
    assert "tools_allow" in eff.emptied_dimensions


def test_required_approvals_union_strengthens():
    eff = apply_restrictions(
        ra(),
        [
            GovernanceRestrictions(required_approvals=frozenset({"cfo"})),
            GovernanceRestrictions(required_approvals=frozenset({"cfo", "legal"})),
        ],
    )
    assert eff.required_approvals == frozenset({"cfo", "legal"})


def test_no_restriction_preserves_ra_scope_exactly():
    eff = apply_restrictions(ra(), [GovernanceRestrictions()])
    assert set(eff.tools_allow) == set(RA_SCOPE.tools_allow)
    assert eff.max_amount_minor_units == RA_SCOPE.max_transaction_minor_units
    assert not eff.is_empty()


def test_effective_never_wider_than_ra_on_any_dimension():
    # Arbitrary mix of restrictions; effective must stay ⊆ RA on every allow dim.
    eff = apply_restrictions(
        ra(),
        [
            GovernanceRestrictions(
                max_amount_minor_units=250000,
                allow_intersections={"data_allow": frozenset({"CUSTOMER_PII", "EXTRA"})},
            )
        ],
    )
    assert set(eff.purposes) <= set(RA_SCOPE.purposes)
    assert set(eff.tools_allow) <= set(RA_SCOPE.tools_allow)
    assert set(eff.data_allow) <= set(RA_SCOPE.data_allow)  # EXTRA cannot appear
    assert set(eff.destinations) <= set(RA_SCOPE.destinations)
    assert eff.max_amount_minor_units <= RA_SCOPE.max_transaction_minor_units
    # Deny set can only grow (⊇ RA deny).
    assert set(eff.tools_deny) >= set(RA_SCOPE.tools_deny)
