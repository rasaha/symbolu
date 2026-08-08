"""Model Authority — binding authorization-decision tests.

These exercise the external Model Authority contract layered over the (unchanged)
eligibility gate + ranking mechanism. Scenario coverage mirrors the refactor's
acceptance criteria:

  A. normal authorization (ALLOW)
  B. no eligible model (DENY)
  C. a mandatory constraint cannot be compensated by a higher score
  D. governed fallback (primary unavailable → next *eligible* model authorized)
  E. invalid fallback (a higher-ranked candidate violating policy is skipped)
  F. HOLD / ESCALATE mapping for indeterminate evidence
  G. backward compatibility of the deprecated Model Selection names
"""
from __future__ import annotations

import ugence_model_selection as ms
from ugence_model_selection.api import (
    AuthorityReasonCode,
    Candidate,
    Evidence,
    EvidenceSource,
    ExecutableRegistry,
    ExecutionGate,
    ModelAuthority,
    ModelAuthorityService,
    ModelAuthorizationDecision,
    ModelAuthorizationDisposition,
    ModelRecord,
    Request,
    Signal,
    fingerprint,
)

NOW = 1000.0


def _ev(ttl: float = 3600.0, source: EvidenceSource = EvidenceSource.LIVE_PROBE) -> Evidence:
    return Evidence(source, NOW, 1.0, ttl_seconds=ttl)


def _fresh_candidate(provider: str = "anthropic", region: str = "us", latency: float = 500.0,
                     *, model_available: bool = True) -> Candidate:
    return Candidate(
        provider, f"{provider}-model", provider, region=region, context_limit=200000,
        structured_output=True, tool_use=True, price_in_per_mtok=3.0, price_out_per_mtok=15.0,
        signals={
            "reachable": Signal(True, _ev()), "authenticated": Signal(True, _ev()),
            "network_allowed": Signal(True, _ev()), "model_available": Signal(model_available, _ev()),
            "billing_active": Signal(True, _ev()), "quota_state": Signal("ok", _ev()),
            "observed_latency_ms": Signal(latency, _ev()), "reliability": Signal(0.99, _ev()),
            "credential_expiry_ts": Signal(NOW + 100000, _ev()),
        },
    )


def _registry(*records: ModelRecord) -> ExecutableRegistry:
    reg = ExecutableRegistry(ExecutionGate())
    for rec in records:
        reg.upsert(rec)
    return reg


# --- A. normal authorization -------------------------------------------------------
def test_allow_authorizes_eligible_model():
    req = Request("A", context_tokens=1000, approved_providers={"anthropic"})
    reg = _registry(ModelRecord("m1", _fresh_candidate(), observed_latency_ms=500.0))
    decision = ModelAuthority().authorize(reg, req, NOW, quality_of=lambda rec: 0.9)

    assert isinstance(decision, ModelAuthorizationDecision)
    assert decision.disposition is ModelAuthorizationDisposition.ALLOW
    assert decision.is_authorized
    assert decision.authorized_model_id == "m1"
    assert decision.authorized_provider_id == "anthropic"
    assert AuthorityReasonCode.AUTHORIZED.value in decision.reason_codes
    assert decision.policy_version == "exec_gate_v1"
    assert decision.decision_id.startswith("mad_")
    assert decision.expires_at == NOW + 3600.0  # evidence-TTL freshness bound


# --- B. no eligible model ----------------------------------------------------------
def test_deny_when_no_eligible_model():
    req = Request("B", context_tokens=1000, approved_providers={"nobody"})
    reg = _registry(ModelRecord("m1", _fresh_candidate(provider="anthropic"), observed_latency_ms=500.0))
    decision = ModelAuthority().authorize(reg, req, NOW, quality_of=lambda rec: 0.9)

    assert decision.disposition is ModelAuthorizationDisposition.DENY
    assert not decision.is_authorized
    assert decision.authorized_model_id is None
    assert decision.authorized_provider_id is None
    assert AuthorityReasonCode.NO_ELIGIBLE_MODEL.value in decision.reason_codes
    assert "PROVIDER_NOT_APPROVED" in decision.reason_codes  # per-condition ReasonCode surfaced


# --- C. mandatory constraint is non-compensatory -----------------------------------
def test_highest_score_cannot_override_mandatory_failure():
    # 'bad' is the best-scoring, lowest-latency candidate but is in a prohibited
    # jurisdiction (mandatory CRITICAL_GOV failure) → it must NOT be authorized.
    req = Request("C", context_tokens=1000, region_allowed={"us"})
    reg = _registry(
        ModelRecord("ok", _fresh_candidate(provider="anthropic", region="us"), observed_latency_ms=500.0),
        ModelRecord("bad", _fresh_candidate(provider="google", region="cn", latency=1.0),
                    observed_latency_ms=1.0),
    )
    decision = ModelAuthority().authorize(
        reg, req, NOW, quality_of=lambda rec: 1.0 if rec.internal_id == "bad" else 0.5)

    assert decision.disposition is ModelAuthorizationDisposition.ALLOW
    assert decision.authorized_model_id == "ok"
    assert "bad" not in decision.fallback_model_ids  # ineligible → never a governed fallback


# --- D. governed fallback ----------------------------------------------------------
def test_governed_fallback_authorizes_next_eligible_model():
    # Primary is unavailable (model_available == False → ineligible); the next *eligible*
    # candidate becomes authorized.
    req = Request("D", context_tokens=1000, approved_providers={"anthropic", "google"})
    primary = ModelRecord("primary", _fresh_candidate(provider="anthropic", model_available=False),
                          observed_latency_ms=500.0)
    secondary = ModelRecord("secondary", _fresh_candidate(provider="google"), observed_latency_ms=800.0)
    reg = _registry(primary, secondary)
    decision = ModelAuthority().authorize(
        reg, req, NOW, quality_of=lambda rec: 1.0 if rec.internal_id == "primary" else 0.5)

    assert decision.disposition is ModelAuthorizationDisposition.ALLOW
    assert decision.authorized_model_id == "secondary"
    assert "primary" not in decision.fallback_model_ids  # unavailable → not a governed fallback


def test_fallback_chain_contains_only_eligible_models():
    req = Request("D2", context_tokens=1000, approved_providers={"anthropic", "google"})
    reg = _registry(
        ModelRecord("a", _fresh_candidate(provider="anthropic"), observed_latency_ms=500.0),
        ModelRecord("b", _fresh_candidate(provider="google"), observed_latency_ms=800.0),
    )
    decision = ModelAuthority().authorize(
        reg, req, NOW, quality_of=lambda rec: 0.9 if rec.internal_id == "a" else 0.8)

    assert decision.authorized_model_id == "a"
    assert decision.fallback_model_ids == ("b",)  # remaining eligible candidate, ranked
    assert AuthorityReasonCode.FALLBACK_AUTHORIZED.value in decision.reason_codes


# --- E. invalid fallback is skipped ------------------------------------------------
def test_policy_violating_fallback_is_never_authorized():
    # Primary unavailable; the highest-scoring remaining candidate violates the region
    # policy; only a lower-ranked *eligible* candidate may be authorized.
    req = Request("E", context_tokens=1000, region_allowed={"us"})
    reg = _registry(
        ModelRecord("primary", _fresh_candidate(provider="anthropic", region="us", model_available=False),
                    observed_latency_ms=100.0),
        ModelRecord("prohibited", _fresh_candidate(provider="google", region="cn", latency=1.0),
                    observed_latency_ms=1.0),
        ModelRecord("eligible", _fresh_candidate(provider="openai", region="us"),
                    observed_latency_ms=900.0),
    )
    decision = ModelAuthority().authorize(reg, req, NOW, quality_of=lambda rec: {
        "primary": 1.0, "prohibited": 0.99, "eligible": 0.4}[rec.internal_id])

    assert decision.disposition is ModelAuthorizationDisposition.ALLOW
    assert decision.authorized_model_id == "eligible"
    assert "prohibited" not in decision.fallback_model_ids
    assert "primary" not in decision.fallback_model_ids


# --- F. HOLD / ESCALATE for indeterminate evidence ---------------------------------
def _indeterminate_candidate(provider: str = "anthropic") -> Candidate:
    cand = _fresh_candidate(provider=provider)
    # credential_expiry unknown → CRITICAL_OP UNKNOWN mapped to INDETERMINATE (not fail-closed).
    del cand.signals["credential_expiry_ts"]
    return cand


def test_hold_when_evidence_is_indeterminate():
    req = Request("F", context_tokens=1000, approved_providers={"anthropic"})
    reg = _registry(ModelRecord("m1", _indeterminate_candidate(), observed_latency_ms=500.0))
    decision = ModelAuthority().authorize(reg, req, NOW, quality_of=lambda rec: 0.9)

    assert decision.disposition is ModelAuthorizationDisposition.HOLD
    assert decision.authorized_model_id is None
    assert AuthorityReasonCode.EXECUTION_WITHHELD.value in decision.reason_codes
    assert AuthorityReasonCode.EVIDENCE_INDETERMINATE.value in decision.reason_codes


def test_escalate_when_configured_for_indeterminate():
    req = Request("F2", context_tokens=1000, approved_providers={"anthropic"})
    reg = _registry(ModelRecord("m1", _indeterminate_candidate(), observed_latency_ms=500.0))
    authority = ModelAuthority(escalate_on_indeterminate=True)
    decision = authority.authorize(reg, req, NOW, quality_of=lambda rec: 0.9)

    assert decision.disposition is ModelAuthorizationDisposition.ESCALATE
    assert decision.authorized_model_id is None
    assert AuthorityReasonCode.HUMAN_REVIEW_REQUIRED.value in decision.reason_codes


# --- G. backward compatibility -----------------------------------------------------
def test_deprecated_model_selection_aliases_resolve():
    from ugence_model_selection.api import (
        ModelAuthorizationPolicy,
        ModelSelectionService,
        ModelSelector,
        PolicyWeights,
    )

    # Deprecated names map onto the canonical Model Authority contract.
    assert ModelSelector is ModelAuthority
    assert ModelSelectionService is ModelAuthority
    assert ModelAuthorityService is ModelAuthority
    assert ModelAuthorizationPolicy is PolicyWeights


def test_legacy_selection_surface_still_public():
    # The pre-existing eligibility/selection API is unchanged and still importable.
    from ugence_model_selection.api import ExecutionGate, Selection, select  # noqa: F401

    assert callable(select)
    for name in ("ModelAuthority", "ModelAuthorizationDecision", "select", "ExecutionGate"):
        assert name in ms.api.__all__


# --- determinism -------------------------------------------------------------------
def test_decision_id_is_deterministic_and_replayable():
    req = Request("H", context_tokens=1000, approved_providers={"anthropic"})
    reg = _registry(ModelRecord("m1", _fresh_candidate(), observed_latency_ms=500.0))
    d1 = ModelAuthority().authorize(reg, req, NOW, quality_of=lambda rec: 0.9)
    d2 = ModelAuthority().authorize(_registry(
        ModelRecord("m1", _fresh_candidate(), observed_latency_ms=500.0)), req, NOW,
        quality_of=lambda rec: 0.9)
    assert d1.decision_id == d2.decision_id
    assert fingerprint(d1.to_dict()) == fingerprint(d2.to_dict())
