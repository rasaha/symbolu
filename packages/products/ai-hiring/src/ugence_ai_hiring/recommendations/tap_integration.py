"""Assertion-governance (TAP) integration boundary (H2).

Evaluates each material recommendation claim through the **Assertion Governance
Provider contract** — the provider-neutral `AssertionAssessmentIntegration` from
`ugence_governance_provider_framework.api`. It never imports TAP internals; TAP (or any conformant
assertion provider, incl. the framework's deterministic reference provider) is
injected. The provider evaluates *evidentiary support*; it does not decide whether
the candidate should be hired.

Provider failure (unavailable / timeout / malformed result / resolution failure) is
**fail-safe**: the claim's outcome becomes UNEVALUABLE with the error preserved, so
the recommendation can never reach READY_FOR_HUMAN_REVIEW on an unresolved provider
error.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from ugence_governance_provider_framework.api import (
    AssertionAssessmentIntegration,
    AssertionCoverage,
    AssertionGovernanceRequest,
    ProviderError,
)

from ..common import utc_now
from ..domain.base import DomainModel
from .claim import AssertionOutcome, HiringClaim


class ClaimAssertionBinding(DomainModel):
    """The stored provider-evaluation binding for one claim (append-only)."""

    binding_id: str
    tenant_id: str
    recommendation_id: str
    recommendation_version: int
    claim_id: str
    provider_id: str = ""
    coverage: str = ""                        # provider AssertionCoverage value
    outcome: AssertionOutcome = AssertionOutcome.NOT_EVALUATED
    evidence_coverage: float = 0.0
    covered_evidence_refs: tuple[str, ...] = ()
    unsupported_elements: tuple[str, ...] = ()
    explanation_refs: tuple[str, ...] = ()
    provider_trace_id: str = ""
    fingerprint: str = ""
    evaluated: bool = False                   # False iff the provider errored
    error: str = ""
    correlation_id: str = ""
    causation_id: str = ""                    # links to the generating recommendation
    created_at: datetime = Field(default_factory=utc_now)


def _map_outcome(coverage: AssertionCoverage, *, has_contradicting: bool) -> AssertionOutcome:
    if coverage is AssertionCoverage.SUPPORTED:
        return AssertionOutcome.SUPPORTED
    if coverage is AssertionCoverage.CONSTRAINED:
        return AssertionOutcome.PARTIALLY_SUPPORTED
    if coverage is AssertionCoverage.INDETERMINATE:
        return AssertionOutcome.UNEVALUABLE
    # UNSUPPORTED — surface as CONFLICTING when the claim cites contradicting evidence
    return AssertionOutcome.CONFLICTING if has_contradicting else AssertionOutcome.UNSUPPORTED


class ClaimAssertionEvaluator:
    """Evaluates claims via the injected assertion-governance integration."""

    def __init__(
        self, integration: AssertionAssessmentIntegration, *,
        provider_id: str = "", id_factory=None,
    ) -> None:
        self._integration = integration
        self._provider_id = provider_id
        from ugence_decision_authority.api.common import new_id
        self._new_id = id_factory or new_id

    def evaluate(
        self, claim: HiringClaim, *, policy_refs: tuple[str, ...] = (), correlation_id: str = "",
        causation_id: str = "",
    ) -> tuple[HiringClaim, ClaimAssertionBinding]:
        """Return (claim updated with the assertion result, provider binding)."""
        request = AssertionGovernanceRequest(
            assertion=claim.proposition, assertion_type=claim.claim_type.value,
            evidence_refs=claim.supporting_evidence_refs, source_identity=claim.generator_id,
            policy_refs=policy_refs,
            context={"application_id": claim.application_id, "criterion_id": claim.criterion_id},
            correlation_id=correlation_id)

        binding_id = self._new_id("cab")
        has_contradicting = bool(claim.contradicting_evidence_refs)
        try:
            assessment = self._integration.assess(request)
        except ProviderError as exc:  # unavailable / timeout / malformed / resolution
            binding = ClaimAssertionBinding(
                binding_id=binding_id, tenant_id=claim.tenant_id,
                recommendation_id=claim.recommendation_id,
                recommendation_version=claim.recommendation_version, claim_id=claim.claim_id,
                provider_id=self._provider_id, outcome=AssertionOutcome.UNEVALUABLE,
                evaluated=False, error=f"{type(exc).__name__}: {exc}",
                correlation_id=correlation_id, causation_id=causation_id)
            updated = claim.model_copy(update={
                "assertion_outcome": AssertionOutcome.UNEVALUABLE, "assertion_trace_id": "",
                "assertion_evidence_coverage": 0.0})
            return updated, binding

        outcome = _map_outcome(assessment.coverage, has_contradicting=has_contradicting)
        binding = ClaimAssertionBinding(
            binding_id=binding_id, tenant_id=claim.tenant_id,
            recommendation_id=claim.recommendation_id,
            recommendation_version=claim.recommendation_version, claim_id=claim.claim_id,
            provider_id=self._provider_id, coverage=assessment.coverage.value, outcome=outcome,
            evidence_coverage=assessment.evidence_coverage,
            covered_evidence_refs=assessment.covered_evidence_refs,
            unsupported_elements=assessment.unsupported_elements,
            explanation_refs=assessment.explanation_refs,
            provider_trace_id=assessment.provider_trace_id, fingerprint=assessment.fingerprint,
            evaluated=True, correlation_id=correlation_id, causation_id=causation_id)
        updated = claim.model_copy(update={
            "assertion_outcome": outcome, "assertion_trace_id": assessment.provider_trace_id,
            "assertion_evidence_coverage": assessment.evidence_coverage,
            "assertion_explanation_refs": assessment.explanation_refs})
        return updated, binding
