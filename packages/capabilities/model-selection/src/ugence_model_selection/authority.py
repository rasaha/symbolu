"""Model Authority — the binding model-authorization decision layer.

Model Authority determines which model, *if any*, is authorized to execute a specific
request under the current policy, capability, jurisdiction, security, cost, and runtime
conditions. It is the external contract of this capability: it does not merely recommend
a model, it issues a binding authorization decision.

It is a thin, deterministic layer over the two existing audited stages — it adds no new
selection mathematics:

    Candidate models (ExecutableRegistry)
            ↓
    Mandatory eligibility gates (ExecutionGate)      — fail-closed; never ranks
            ↓
    Eligible model set
            ↓
    Existing ranking / optimization (ModelPolicy.select)   — only over the eligible set
            ↓
    MODEL AUTHORITY (this module)
            ↓
    ModelAuthorizationDecision  →  ALLOW / DENY / HOLD / ESCALATE

Invariants (inherited, made explicit here):

* **Eligibility precedes ranking.** A model is never authorized because it has the highest
  score; it is authorized only if it first passes every mandatory eligibility gate. A
  lower-cost or higher-quality candidate can never override a mandatory policy failure
  (non-compensatory eligibility).
* **Governed fallback.** The fallback chain is composed only of *eligible* candidates in
  ranked order — "authorize the next eligible model", never "try the next ranked model".
* **Machine-readable reasons.** Every decision carries reason codes; free-text is
  supplementary, never the authoritative signal.

Ranking remains an internal optimization mechanism (``ModelPolicy.select``). Authorization
is the external, binding contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Tuple

from .fingerprint import fingerprint
from .gate import ExecutionGate
from .model import Request
from .policy import PolicyWeights, Selection, select
from .reason_codes import ReasonCode
from .registry import ExecutableRegistry, ModelRecord
from .states import EligibilityDecision, EligibilityState


class ModelAuthorizationDisposition(str, Enum):
    """The binding disposition of a model-authorization decision."""

    ALLOW = "ALLOW"          # an eligible model is authorized to execute this request
    DENY = "DENY"            # no model may execute this request (no executable model identified)
    HOLD = "HOLD"            # execution temporarily withheld (evidence indeterminate; re-evaluate)
    ESCALATE = "ESCALATE"    # a higher authority / human / policy workflow is required


class AuthorityReasonCode(str, Enum):
    """Authority-decision-level reason codes.

    These describe the *outcome of the authorization decision itself* and are distinct
    from :class:`ReasonCode`, which normalizes per-condition provider/policy signals. A
    decision's ``reason_codes`` combine an authority-level code with the distinct
    per-condition ``ReasonCode`` values that drove the outcome. Append-only.
    """

    AUTHORIZED = "AUTHORIZED"                        # ALLOW: a model was authorized
    FALLBACK_AUTHORIZED = "FALLBACK_AUTHORIZED"      # ALLOW: a governed fallback chain is available
    NO_ELIGIBLE_MODEL = "NO_ELIGIBLE_MODEL"          # DENY: nothing passed mandatory eligibility
    EXECUTION_WITHHELD = "EXECUTION_WITHHELD"        # HOLD: withheld pending resolution
    EVIDENCE_INDETERMINATE = "EVIDENCE_INDETERMINATE"  # HOLD/ESCALATE: critical evidence unknown/stale
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"  # ESCALATE: routed to a higher authority


@dataclass(frozen=True)
class ModelAuthorizationDecision:
    """A binding, replayable model-authorization decision artifact.

    ``decision_id`` is a stable, deterministic handle (derived from the request, the
    candidate set, and the decision content — no wall clock, no randomness) so a downstream
    runtime can reference *this* authorization. ``expires_at`` is epoch seconds (the
    package convention; never ``datetime``) after which the cited evidence goes stale and
    the decision must be re-evaluated; ``None`` means no freshness bound applies.

    On ``ALLOW`` the decision identifies the authorized model/provider. On ``DENY`` it
    identifies no executable model. ``HOLD`` withholds execution temporarily; ``ESCALATE``
    routes to a higher authority. ``fallback_model_ids`` are governed fallback candidates —
    every one has already passed mandatory eligibility.
    """

    decision_id: str
    disposition: ModelAuthorizationDisposition
    authorized_model_id: Optional[str]
    authorized_provider_id: Optional[str]
    reason_codes: Tuple[str, ...]
    fallback_model_ids: Tuple[str, ...] = ()
    policy_version: Optional[str] = None
    expires_at: Optional[float] = None

    @property
    def is_authorized(self) -> bool:
        return self.disposition is ModelAuthorizationDisposition.ALLOW

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "disposition": self.disposition.value,
            "authorized_model_id": self.authorized_model_id,
            "authorized_provider_id": self.authorized_provider_id,
            "reason_codes": list(self.reason_codes),
            "fallback_model_ids": list(self.fallback_model_ids),
            "policy_version": self.policy_version,
            "expires_at": self.expires_at,
        }


def _distinct(seq) -> Tuple[str, ...]:
    """Order-preserving de-duplication into a tuple of strings."""
    seen: set = set()
    out: List[str] = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return tuple(out)


def _decision_id(req: Request, disposition: ModelAuthorizationDisposition,
                 authorized_model_id: Optional[str], candidate_ids: List[str],
                 policy_version: Optional[str], now: float) -> str:
    """Deterministic, collision-resistant decision handle (no clock, no randomness)."""
    digest = fingerprint({
        "request_id": req.request_id,
        "now": now,
        "disposition": disposition.value,
        "authorized_model_id": authorized_model_id,
        "candidates": sorted(candidate_ids),
        "policy_version": policy_version,
    })
    return f"mad_{digest[:24]}"


class ModelAuthority:
    """Issues binding model-authorization decisions over an approved candidate set.

    Wraps the existing eligibility gate (:class:`ExecutionGate`, via
    :class:`ExecutableRegistry`) and the existing ranking mechanism
    (:func:`policy.select`). It adds no new selection mathematics — it makes the
    eligibility-before-ranking invariant explicit and turns the selection outcome into a
    binding :class:`ModelAuthorizationDecision`.

    ``escalate_on_indeterminate`` controls how genuinely uncertain evidence is dispositioned
    when nothing is currently eligible: the default (``False``) issues ``HOLD`` (re-evaluate
    once evidence refreshes), preserving the historical behavior; ``True`` issues
    ``ESCALATE`` to route the request to a higher authority / human review. Neither path
    introduces a new runtime execution path — the underlying eligibility/ranking behavior is
    unchanged.
    """

    def __init__(self, gate: Optional[ExecutionGate] = None,
                 weights: Optional[PolicyWeights] = None, *,
                 policy_version: Optional[str] = None,
                 escalate_on_indeterminate: bool = False):
        self.gate = gate or ExecutionGate()
        self.weights = weights
        self.policy_version = policy_version or self.gate.config.policy_version
        self.escalate_on_indeterminate = escalate_on_indeterminate

    def authorize(self, registry: ExecutableRegistry, req: Request, now: float,
                  quality_of: Callable[[ModelRecord], float]) -> ModelAuthorizationDecision:
        """Determine which model, if any, is authorized to execute ``req``.

        ``quality_of(rec) -> [0,1]`` is the provider-neutral capability prior consumed by
        the internal ranking; it can never resurrect an ineligible candidate.
        """
        # STAGE 1+2 — mandatory eligibility gates run first; only eligible candidates pass.
        selectable, excluded = registry.evaluate(req, now)
        candidate_ids = [rec.internal_id for rec, _ in selectable] + \
                        [rec.internal_id for rec, _ in excluded]

        # STAGE 3 — existing ranking / optimization, over the eligible set ONLY.
        sel: Selection = select(selectable, req, quality_of, self.weights)

        if sel.selected is not None:
            return self._allow(req, sel, selectable, candidate_ids, now)

        # Nothing is currently eligible → DENY, or HOLD/ESCALATE if the block is purely
        # unresolved evidence (an INDETERMINATE candidate could become authorizable later).
        return self._not_authorized(req, excluded, candidate_ids, now)

    # -- ALLOW ----------------------------------------------------------------------
    def _allow(self, req: Request, sel: Selection,
               selectable: List[Tuple[ModelRecord, EligibilityDecision]],
               candidate_ids: List[str], now: float) -> ModelAuthorizationDecision:
        authorized = sel.selected
        assert authorized is not None
        decisions = {rec.internal_id: dec for rec, dec in selectable}
        # Governed fallback: the remaining ranked candidates — each already eligible.
        fallback = tuple(rec.internal_id for rec, _ in sel.ranked
                         if rec.internal_id != authorized.internal_id)

        auth_dec = decisions.get(authorized.internal_id)
        reasons: List[str] = [AuthorityReasonCode.AUTHORIZED.value]
        if fallback:
            reasons.append(AuthorityReasonCode.FALLBACK_AUTHORIZED.value)
        if auth_dec is not None:
            reasons.extend(r.value for r in auth_dec.reasons)

        expires_at = None
        if auth_dec is not None and auth_dec.ttl_seconds > 0:
            expires_at = now + auth_dec.ttl_seconds

        disposition = ModelAuthorizationDisposition.ALLOW
        return ModelAuthorizationDecision(
            decision_id=_decision_id(req, disposition, authorized.internal_id,
                                     candidate_ids, self.policy_version, now),
            disposition=disposition,
            authorized_model_id=authorized.internal_id,
            authorized_provider_id=authorized.candidate.provider,
            reason_codes=_distinct(reasons),
            fallback_model_ids=fallback,
            policy_version=self.policy_version,
            expires_at=expires_at,
        )

    # -- DENY / HOLD / ESCALATE -----------------------------------------------------
    def _not_authorized(self, req: Request,
                        excluded: List[Tuple[ModelRecord, EligibilityDecision]],
                        candidate_ids: List[str], now: float) -> ModelAuthorizationDecision:
        indeterminate = [(rec, dec) for rec, dec in excluded
                         if dec.state is EligibilityState.INDETERMINATE]

        if indeterminate:
            # Purely-unresolved evidence: the request is not denied outright — it is
            # withheld (or escalated) because a candidate could become authorizable once
            # evidence refreshes.
            if self.escalate_on_indeterminate:
                disposition = ModelAuthorizationDisposition.ESCALATE
                reasons = [AuthorityReasonCode.HUMAN_REVIEW_REQUIRED.value,
                           AuthorityReasonCode.EVIDENCE_INDETERMINATE.value]
            else:
                disposition = ModelAuthorizationDisposition.HOLD
                reasons = [AuthorityReasonCode.EXECUTION_WITHHELD.value,
                           AuthorityReasonCode.EVIDENCE_INDETERMINATE.value]
            ttls = [dec.ttl_seconds for _, dec in indeterminate if dec.ttl_seconds > 0]
            expires_at = now + min(ttls) if ttls else None
            for _, dec in indeterminate:
                reasons.extend(r.value for r in dec.reasons)
            return ModelAuthorizationDecision(
                decision_id=_decision_id(req, disposition, None, candidate_ids,
                                         self.policy_version, now),
                disposition=disposition,
                authorized_model_id=None,
                authorized_provider_id=None,
                reason_codes=_distinct(reasons),
                fallback_model_ids=(),
                policy_version=self.policy_version,
                expires_at=expires_at,
            )

        # Hard denial: no eligible model, and no candidate is merely awaiting evidence.
        disposition = ModelAuthorizationDisposition.DENY
        reasons = [AuthorityReasonCode.NO_ELIGIBLE_MODEL.value]
        for _, dec in excluded:
            reasons.extend(r.value for r in dec.reasons if r is not ReasonCode.OK)
        return ModelAuthorizationDecision(
            decision_id=_decision_id(req, disposition, None, candidate_ids,
                                     self.policy_version, now),
            disposition=disposition,
            authorized_model_id=None,
            authorized_provider_id=None,
            reason_codes=_distinct(reasons),
            fallback_model_ids=(),
            policy_version=self.policy_version,
            expires_at=None,
        )


# --- compatibility / naming-migration aliases --------------------------------------
# The Model Authority names above are the canonical public API. The aliases below map the
# prior "Model Selection" mental model onto it so existing call sites and documentation
# migrate without breakage. They are deprecated: prefer the Model Authority names.
ModelAuthorityService = ModelAuthority          # service-style name
ModelSelector = ModelAuthority                  # deprecated: "selector" → authority
ModelSelectionService = ModelAuthority          # deprecated
ModelAuthorizationPolicy = PolicyWeights        # policy weights govern the internal ranking

__all__ = [
    "ModelAuthorizationDisposition",
    "AuthorityReasonCode",
    "ModelAuthorizationDecision",
    "ModelAuthority",
    "ModelAuthorityService",
    # deprecated compatibility aliases
    "ModelSelector",
    "ModelSelectionService",
    "ModelAuthorizationPolicy",
]
