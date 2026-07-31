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

from .providers import AuthorizationQuery, ProviderRegistry

VERIFIED_CONSISTENT = "VERIFIED_CONSISTENT"
PARTIALLY_CONSISTENT = "PARTIALLY_CONSISTENT"
INCONSISTENT = "INCONSISTENT"
UNVERIFIED = "UNVERIFIED"
EXPIRED = "EXPIRED"
AMBIGUOUS = "AMBIGUOUS"


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

    def to_dict(self) -> dict:
        return {
            "declared_purpose": self.declared_purpose,
            "verified_purpose": self.verified_purpose,
            "purpose_consistency_status": self.purpose_consistency_status,
            "purpose_scope_match": self.purpose_scope_match,
            "purpose_evidence": self.purpose_evidence,
            "in_scope_actions": self.in_scope_actions,
            "out_of_scope_actions": self.out_of_scope_actions,
            "explanation": self.explanation,
            "neutralizes": self.neutralizes,
        }


def _unverified(declared: str, reason: str) -> PurposeAssessment:
    return PurposeAssessment(
        declared_purpose=declared, verified_purpose="",
        purpose_consistency_status=UNVERIFIED if declared else UNVERIFIED,
        purpose_scope_match={}, purpose_evidence=[], in_scope_actions=[],
        out_of_scope_actions=[], explanation=reason, neutralizes=False)


def assess(
    claims: list,                 # list[benign.BenignContext] (declared, untrusted)
    scope: AssemblyScope,
    registry: ProviderRegistry | None,
    now: float | None,
    active_policy_version: str | None,
    recipe,
) -> PurposeAssessment:
    """Assess purpose consistency. Only a verified authorization can neutralize."""
    declared = "; ".join(sorted({c.tag for c in claims if c.tag})) if claims else ""

    if not claims:
        return PurposeAssessment(
            declared_purpose="", verified_purpose="",
            purpose_consistency_status=UNVERIFIED, purpose_scope_match={},
            purpose_evidence=[], in_scope_actions=[],
            out_of_scope_actions=list(scope.operations),
            explanation="no purpose claimed; threat interpretation stands",
            neutralizes=False)

    if registry is None or not registry.providers:
        return _unverified(
            declared,
            "purpose claimed but no trusted benign-evidence provider is configured; "
            "self-declared purpose does not neutralize")

    evidence: list = []
    statuses: list[str] = []
    best_auth = None
    for claim in claims:
        # only recipe-accepted benign tags are eligible to qualify this recipe
        eligible = (not recipe.benign_exclusions) or (claim.tag in recipe.benign_exclusions)
        query = AuthorizationQuery(
            tenant=scope.tenant, actor=scope.actors[0] if scope.actors else "",
            workflow=scope.workflow, target_family=scope.target_family,
            operations=scope.operations, destinations=scope.destinations,
            environment=scope.environment, tools=scope.tools, now=now,
            policy_version=active_policy_version or "",
            claim_tag=claim.tag, claim_record_id=claim.ticket or "")
        auth = registry.verify(query)
        if auth is None:
            statuses.append(UNVERIFIED)
            evidence.append({"claim_tag": claim.tag, "verification_status": "NOT_FOUND"})
            continue
        evidence.append(auth.to_dict())
        if not eligible:
            statuses.append(INCONSISTENT)
            continue
        if not auth.time_window_match:
            statuses.append(EXPIRED)
            continue
        if not auth.approver_authority:
            statuses.append(UNVERIFIED)
            continue
        if (active_policy_version and auth.policy_version
                and auth.policy_version != active_policy_version):
            statuses.append(INCONSISTENT)
            continue
        if auth.fully_scope_matched():
            statuses.append(VERIFIED_CONSISTENT)
            best_auth = auth
        elif auth.scope_match.get("tenant") and any(auth.scope_match.values()):
            statuses.append(PARTIALLY_CONSISTENT)
            best_auth = best_auth or auth
        else:
            statuses.append(INCONSISTENT)

    status = _combine(statuses)
    scope_match = best_auth.scope_match if best_auth else {}
    in_scope, out_scope = _partition_actions(scope, best_auth, status)
    verified_purpose = ""
    if status in (VERIFIED_CONSISTENT, PARTIALLY_CONSISTENT) and best_auth:
        verified_purpose = best_auth.tag
    neutralizes = status == VERIFIED_CONSISTENT
    return PurposeAssessment(
        declared_purpose=declared, verified_purpose=verified_purpose,
        purpose_consistency_status=status, purpose_scope_match=scope_match,
        purpose_evidence=evidence, in_scope_actions=in_scope,
        out_of_scope_actions=out_scope,
        explanation=_explain(status), neutralizes=neutralizes)


def _combine(statuses: list[str]) -> str:
    if not statuses:
        return UNVERIFIED
    order = {VERIFIED_CONSISTENT: 0, PARTIALLY_CONSISTENT: 1, EXPIRED: 2,
             INCONSISTENT: 3, AMBIGUOUS: 4, UNVERIFIED: 5}
    distinct = set(statuses)
    if len(distinct) > 1 and VERIFIED_CONSISTENT in distinct and \
            (INCONSISTENT in distinct or EXPIRED in distinct):
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


def _explain(status: str) -> str:
    return {
        VERIFIED_CONSISTENT: "verified authorization fully covers the assembly scope",
        PARTIALLY_CONSISTENT: "verified authorization covers only part of the scope; "
                              "out-of-scope actions remain",
        INCONSISTENT: "verified authorization contradicts the assembly scope",
        EXPIRED: "a matching authorization exists but its window has passed",
        UNVERIFIED: "purpose claimed but not independently verified",
        AMBIGUOUS: "conflicting purpose evidence; not neutralized",
    }.get(status, status)
