"""
test_permission_overclaim.py — deterministic rules for the Phase 2 overclaim observable.

Covers each of the six violation kinds, the within-grant clean case, inertness on an empty
context, the SAFE/UNSURE/UNSAFE verdict mapping, and the confirm-only (PROVISIONAL) guarantee.
"""

from __future__ import annotations

from agentic.agentic_framework.trust.observables import (
    EvidenceStatus,
    ObservableType,
    Verdict,
)
from agentic.agentic_framework.trust.decision import decide
from agentic.agentic_framework.trust.observables import TrustDecision
from agentic.agentic_framework.trust.permission_overclaim import (
    PermissionContext,
    build_overclaim_observation,
    detect_overclaim,
)


def _kinds(ctx):
    return {v.kind for v in detect_overclaim(ctx)}


# ---- each violation kind ----------------------------------------------------

def test_capability_escalation():
    ctx = PermissionContext(requested_capabilities=frozenset({"delete"}),
                            granted_capabilities=frozenset({"read"}))
    assert "capability_escalation" in _kinds(ctx)


def test_authority_escalation_admin_is_severe():
    ctx = PermissionContext(requested_authority="admin", granted_authority="write")
    assert "authority_escalation_admin" in _kinds(ctx)
    assert build_overclaim_observation(ctx).verdict == Verdict.UNSAFE


def test_authority_escalation_mild():
    ctx = PermissionContext(requested_authority="write", granted_authority="read")
    assert _kinds(ctx) == {"authority_escalation"}
    assert build_overclaim_observation(ctx).verdict == Verdict.UNSURE


def test_scope_escalation_glob():
    ctx = PermissionContext(requested_scopes=("billing/invoices",),
                            granted_scopes=("reports/*",))
    assert "scope_escalation" in _kinds(ctx)
    # within grant via glob → no violation
    ok = PermissionContext(requested_scopes=("reports/q1",), granted_scopes=("reports/*",))
    assert _kinds(ok) == set()


def test_cross_tenant():
    ctx = PermissionContext(requested_tenant="acme",
                            granted_tenants=frozenset({"globex"}))
    assert "cross_tenant" in _kinds(ctx)


def test_policy_bypass():
    ctx = PermissionContext(policy_bypass_requested=True)
    assert "policy_bypass" in _kinds(ctx)


# ---- clean / inert ----------------------------------------------------------

def test_within_grant_is_safe():
    ctx = PermissionContext(requested_capabilities=frozenset({"read"}),
                            granted_capabilities=frozenset({"read", "write"}),
                            requested_authority="read", granted_authority="admin",
                            requested_scopes=("reports/q1",), granted_scopes=("reports/*",),
                            requested_tenant="acme", granted_tenants=frozenset({"acme"}))
    assert detect_overclaim(ctx) == []
    obs = build_overclaim_observation(ctx)
    assert obs is not None and obs.verdict == Verdict.SAFE      # evaluated + cleared


def test_empty_context_is_inert():
    assert build_overclaim_observation(PermissionContext()) is None
    assert build_overclaim_observation(None) is None


# ---- taxonomy + confirm-only guarantee --------------------------------------

def test_observation_is_provisional_validator():
    obs = build_overclaim_observation(
        PermissionContext(policy_bypass_requested=True))
    assert obs.otype == ObservableType.VALIDATOR
    assert obs.evidence == EvidenceStatus.PROVISIONAL
    assert obs.name == "permission_overclaim"
    assert obs.detail["violations"]


def test_provisional_overclaim_only_confirms_never_blocks():
    # Even a SEVERE (UNSAFE-verdict) overclaim is confirm-only while PROVISIONAL.
    obs = build_overclaim_observation(
        PermissionContext(requested_authority="root", granted_authority="read",
                          policy_bypass_requested=True))
    assert obs.verdict == Verdict.UNSAFE
    assert decide([obs]).decision == TrustDecision.CONFIRM     # never BLOCK


def test_promoted_severe_overclaim_would_block():
    # Documents the promotion effect: PROVEN + UNSAFE → BLOCK (not enabled by default).
    obs = build_overclaim_observation(
        PermissionContext(policy_bypass_requested=True),
        evidence=EvidenceStatus.PROVEN)
    assert decide([obs]).decision == TrustDecision.BLOCK
