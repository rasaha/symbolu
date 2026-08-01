"""Declared vs. verified purpose model (§4).

A *claimed* purpose (declared on the event, untrusted) is separated from a
*verified* purpose (corroborated by a trusted provider, §3). A claim never
neutralizes a finding on its own — neutralization requires an independently
verified, scope-matched, in-window authorization from an authority.

Consistency statuses:
  VERIFIED_CONSISTENT   — verified authorization fully covers the assembly scope
  PARTIALLY_CONSISTENT  — verified but some actions fall outside authorized scope
  INCONSISTENT          — verified authorization contradicts the assembly scope
  UNVERIFIED            — a purpose was claimed but no trusted record verifies it
  EXPIRED               — a matching record exists but its window has passed
  AMBIGUOUS             — multiple claims/records that do not agree
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import providers as P
from .providers import AuthorizationQuery, ProviderRegistry

VERIFIED_CONSISTENT = "VERIFIED_CONSISTENT"
PARTIALLY_CONSISTENT = "PARTIALLY_CONSISTENT"
INCONSISTENT = "INCONSISTENT"
UNVERIFIED = "UNVERIFIED"
EXPIRED = "EXPIRED"
AMBIGUOUS = "AMBIGUOUS"
REVOKED = "REVOKED"
SUPERSEDED = "SUPERSEDED"
STALE = "STALE"
INVALID = "INVALID"                    # bad signature / version / unverifiable / modified
PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"

# only VERIFIED_CONSISTENT may neutralize; everything else is fail-safe
NEUTRALIZING = frozenset({VERIFIED_CONSISTENT})

# map a provider verification status to a purpose consistency status
_PROVIDER_TO_PURPOSE = {
    P.EXPIRED: EXPIRED, P.REVOKED: REVOKED, P.SUPERSEDED: SUPERSEDED,
    P.STALE: STALE, P.INVALID_SIGNATURE: INVALID, P.VERSION_MISMATCH: INVALID,
    P.UNVERIFIABLE: INVALID, P.MODIFIED_AFTER_ACTIVITY: INVALID,
    P.NOT_YET_INGESTED: UNVERIFIED, P.NOT_FOUND: UNVERIFIED, P.UNVERIFIED: UNVERIFIED,
}


@dataclass
class AssemblyScope:
    tenant: str
    actors: tuple[str, ...]
    workflow: str
    target_family: str
    operations: tuple[str, ...]
    destinations: tuple[str, ...]
    environment: str
    tools: tuple[str, ...]


@dataclass
class PurposeAssessment:
    declared_purpose: str
    verified_purpose: str
    purpose_consistency_status: str
    purpose_scope_match: dict
    purpose_evidence: list
    in_scope_actions: list
    out_of_scope_actions: list
    explanation: str
    neutralizes: bool = False
    provider_unavailable: bool = False
    scope_mismatch_fields: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "declared_purpose": self.declared_purpose,
            "verified_purpose": self.verified_purpose,
            "purpose_consistency_status": self.purpose_consistency_status,
            "purpose_scope_match": self.purpose_scope_match,
            "scope_mismatch_fields": self.scope_mismatch_fields,
            "purpose_evidence": self.purpose_evidence,
            "in_scope_actions": self.in_scope_actions,
            "out_of_scope_actions": self.out_of_scope_actions,
            "explanation": self.explanation,
            "neutralizes": self.neutralizes,
            "provider_unavailable": self.provider_unavailable,
        }


def _unverified(declared: str, reason: str) -> PurposeAssessment:
    return PurposeAssessment(
        declared_purpose=declared, verified_purpose="",
        purpose_consistency_status=UNVERIFIED if declared else UNVERIFIED,
        purpose_scope_match={}, purpose_evidence=[], in_scope_actions=[],
        out_of_scope_actions=[], explanation=reason, neutralizes=False)


def _classify(auth, eligible, active_policy_version) -> str:
    """Map one provider authorization to a purpose status (fail-safe)."""
    if auth.verification_status != P.VERIFIED:
        return _PROVIDER_TO_PURPOSE.get(auth.verification_status, UNVERIFIED)
    if not eligible:
        return INCONSISTENT
    if not auth.approver_authority:
        return UNVERIFIED                        # authority removed / missing
    if (active_policy_version and auth.policy_version
            and auth.policy_version != active_policy_version):
        return INCONSISTENT
    if auth.fully_scope_matched():
        return VERIFIED_CONSISTENT
    if auth.scope_match.get("tenant") and any(auth.scope_match.values()):
        return PARTIALLY_CONSISTENT
    return INCONSISTENT


def assess(
    claims: list,                 # list[benign.BenignContext] (declared, untrusted)
    scope: AssemblyScope,
    registry: ProviderRegistry | None,
    now: float | None,
    active_policy_version: str | None,
    recipe,
    activity_start: float | None = None,
) -> PurposeAssessment:
    """Assess purpose consistency. Only a verified authorization can neutralize.

    Provider failure (unavailable/stale/revoked/conflicting/…) never silently
    neutralizes; conflicting trusted evidence returns AMBIGUOUS; a scope mismatch
    is reported field by field.
    """
    declared = "; ".join(sorted({c.tag for c in claims if c.tag})) if claims else ""

    if not claims:
        return PurposeAssessment(
            declared_purpose="", verified_purpose="",
            purpose_consistency_status=UNVERIFIED, purpose_scope_match={},
            purpose_evidence=[], in_scope_actions=[],
            out_of_scope_actions=list(scope.operations),
            explanation="no purpose claimed; threat interpretation stands")

    if registry is None or not registry.providers:
        return _unverified(
            declared,
            "purpose claimed but no trusted benign-evidence provider is configured; "
            "self-declared purpose does not neutralize")

    evidence: list = []
    statuses: list[str] = []
    best_auth = None
    provider_unavailable = False
    seen_record_ids: dict[str, int] = {}

    for claim in claims:
        eligible = (not recipe.benign_exclusions) or (claim.tag in recipe.benign_exclusions)
        query = AuthorizationQuery(
            tenant=scope.tenant, actor=scope.actors[0] if scope.actors else "",
            workflow=scope.workflow, target_family=scope.target_family,
            operations=scope.operations, destinations=scope.destinations,
            environment=scope.environment, tools=scope.tools, now=now,
            policy_version=active_policy_version or "",
            claim_tag=claim.tag, claim_record_id=claim.ticket or "",
            activity_start=activity_start)
        result = registry.verify_all(query)
        if result.provider_unavailable:
            provider_unavailable = True
        if not result.authorizations:
            statuses.append(UNVERIFIED)
            evidence.append({"claim_tag": claim.tag, "verification_status": P.NOT_FOUND})
            continue
        for auth in result.authorizations:
            evidence.append(auth.to_dict())
            if auth.record_id:
                seen_record_ids[auth.record_id] = seen_record_ids.get(auth.record_id, 0) + 1
            st = _classify(auth, eligible, active_policy_version)
            statuses.append(st)
            if st == VERIFIED_CONSISTENT and best_auth is None:
                best_auth = auth
            elif st in (PARTIALLY_CONSISTENT,) and best_auth is None:
                best_auth = auth

    # duplicate authorization IDs are a conflict, not corroboration
    duplicate_ids = any(c > 1 for c in seen_record_ids.values())
    status = _combine(statuses, duplicate_ids)

    # provider unavailability is fail-safe: it can only remove, never grant, trust
    if provider_unavailable and status != VERIFIED_CONSISTENT:
        status = PROVIDER_UNAVAILABLE
    elif provider_unavailable and status == VERIFIED_CONSISTENT:
        status = AMBIGUOUS   # a verified record plus an unreachable provider = ambiguous

    scope_match = best_auth.scope_match if best_auth else {}
    mismatch_fields = sorted(k for k, v in scope_match.items() if not v)
    in_scope, out_scope = _partition_actions(scope, best_auth, status)
    verified_purpose = best_auth.tag if (best_auth and status in (
        VERIFIED_CONSISTENT, PARTIALLY_CONSISTENT)) else ""
    return PurposeAssessment(
        declared_purpose=declared, verified_purpose=verified_purpose,
        purpose_consistency_status=status, purpose_scope_match=scope_match,
        purpose_evidence=evidence, in_scope_actions=in_scope,
        out_of_scope_actions=out_scope, explanation=_explain(status, mismatch_fields),
        neutralizes=(status == VERIFIED_CONSISTENT),
        provider_unavailable=provider_unavailable, scope_mismatch_fields=mismatch_fields)


def _combine(statuses: list[str], duplicate_ids: bool = False) -> str:
    if not statuses:
        return UNVERIFIED
    order = {VERIFIED_CONSISTENT: 0, PARTIALLY_CONSISTENT: 1, EXPIRED: 2, STALE: 2,
             REVOKED: 2, SUPERSEDED: 2, INVALID: 2, INCONSISTENT: 3,
             AMBIGUOUS: 4, PROVIDER_UNAVAILABLE: 4, UNVERIFIED: 5}
    distinct = set(statuses)
    # conflicting trusted evidence -> AMBIGUOUS
    conflict = {EXPIRED, REVOKED, SUPERSEDED, STALE, INVALID, INCONSISTENT}
    if VERIFIED_CONSISTENT in distinct and (distinct & conflict):
        return AMBIGUOUS
    if duplicate_ids and VERIFIED_CONSISTENT in distinct:
        return AMBIGUOUS
    return min(statuses, key=lambda s: order.get(s, 9))


def _partition_actions(scope, auth, status):
    if auth is None or status not in (VERIFIED_CONSISTENT, PARTIALLY_CONSISTENT):
        return [], list(scope.operations)
    allowed = auth.detail.get("scope", {}).get("operations", "*")
    if allowed in ("*", None, ""):
        return list(scope.operations), []
    allowed = set(allowed)
    inside = [op for op in scope.operations if op in allowed]
    outside = [op for op in scope.operations if op not in allowed]
    return inside, outside


def _explain(status: str, mismatch_fields=()) -> str:
    base = {
        VERIFIED_CONSISTENT: "verified authorization fully covers the assembly scope",
        PARTIALLY_CONSISTENT: "verified authorization covers only part of the scope; "
                              "out-of-scope actions remain",
        INCONSISTENT: "verified authorization contradicts the assembly scope",
        EXPIRED: "a matching authorization exists but its window has passed",
        REVOKED: "the matching authorization has been revoked",
        SUPERSEDED: "the matching authorization has been superseded",
        STALE: "the matching authorization is stale",
        INVALID: "the authorization failed verification (signature/version/"
                 "unverifiable/modified after activity)",
        PROVIDER_UNAVAILABLE: "a trusted provider was unavailable; cannot verify; "
                              "not neutralized (fail-safe)",
        UNVERIFIED: "purpose claimed but not independently verified",
        AMBIGUOUS: "conflicting purpose evidence; not neutralized",
    }.get(status, status)
    if mismatch_fields and status in (PARTIALLY_CONSISTENT, INCONSISTENT):
        base += " (scope mismatch on: " + ", ".join(mismatch_fields) + ")"
    return base
