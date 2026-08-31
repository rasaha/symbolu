"""The concrete adapter onto the shared Ugence Policy Authority.

:class:`PolicyAuthorityReadinessPolicyResolver` is a thin, immutable holder for
the trust configuration a deployment chose — registry, signature verifier,
adapter registry, optional approval verifier, historical-resolution rule — that
forwards to the authority's **public** :func:`resolve_policy` service.

It deliberately reproduces **nothing**: no signature check, no approval check,
no revocation check, no registry lookup, no canonicalization, no digest
recomputation, no lifecycle or effective-period arithmetic. Every one of those
lives in the shared authority and stays there (Policy Authority ADR §5, §10.4;
UVI ADR §21). If this adapter grew such logic it would be a second authority,
which is exactly what P-1 forbids.

Only the authority's public API is imported — never
``ugence_policy_authority.core`` or ``ugence_policy_authority.adapters`` — and an
automated dependency-boundary test enforces that.

Composing this adapter is a **composition-root trust decision**: the keys,
approval boundary, registry contents and historical-resolution posture handed to
it define what "trusted" means for the deployment. This package chooses none of
them and provides no default instance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ugence_policy_authority.api import (
    AdapterRegistry,
    ApprovalVerifier,
    HistoricalResolutionRule,
    PolicyRegistry,
    PolicyResolution,
    PolicySignatureVerifier,
    resolve_policy,
)
from ugence_uvi_policy_contracts.api import PolicyReference

from .errors import ReadinessAssessmentError

__all__ = ["PolicyAuthorityReadinessPolicyResolver"]


@dataclass(frozen=True)
class PolicyAuthorityReadinessPolicyResolver:
    """A :class:`~.protocols.ReadinessPolicyResolver` backed by the shared authority.

    ``historical_resolution`` defaults to the authority's own fail-closed
    ``DENY_ALWAYS``. Even if a deployment deliberately enables
    ``ALLOW_BEFORE_REVOCATION``, readiness orchestration still refuses a
    historical answer: a historical resolution describes the past and never
    implies current validity, so it cannot govern an assessment *at* the
    evaluation instant.
    """

    registry: PolicyRegistry
    signature_verifier: PolicySignatureVerifier
    adapters: AdapterRegistry
    approval_verifier: Optional[ApprovalVerifier] = None
    historical_resolution: HistoricalResolutionRule = HistoricalResolutionRule.DENY_ALWAYS

    def __post_init__(self) -> None:
        if not isinstance(self.adapters, AdapterRegistry):
            raise ReadinessAssessmentError(
                "PolicyAuthorityReadinessPolicyResolver.adapters must be an AdapterRegistry"
            )
        if not isinstance(self.historical_resolution, HistoricalResolutionRule):
            raise ReadinessAssessmentError(
                "PolicyAuthorityReadinessPolicyResolver.historical_resolution must be a "
                "HistoricalResolutionRule"
            )
        for name in ("registry", "signature_verifier"):
            value = getattr(self, name)
            if value is None:
                raise ReadinessAssessmentError(
                    f"PolicyAuthorityReadinessPolicyResolver.{name} is required"
                )

    def resolve_readiness_policy(
        self,
        *,
        reference: PolicyReference,
        expected_tenant_id: str,
        as_of: datetime,
    ) -> PolicyResolution:
        """Forward to the shared authority's single trusted resolution service."""

        if not isinstance(reference, PolicyReference):
            raise ReadinessAssessmentError(
                "PolicyAuthorityReadinessPolicyResolver.reference must be a PolicyReference"
            )
        return resolve_policy(
            reference=reference,
            expected_reference_tenant_id=expected_tenant_id,
            as_of=as_of,
            registry=self.registry,
            signature_verifier=self.signature_verifier,
            adapters=self.adapters,
            approval_verifier=self.approval_verifier,
            historical_resolution=self.historical_resolution,
        )
