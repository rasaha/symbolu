"""TAP (assertion-governance) integration adapter.

Maps Claim Manifest claims onto the existing assertion-governance contract and
invokes the live TAP provider through its public API. TAP is **not** modified and
no second assertion provider is introduced.

Design boundaries preserved:

* claims cross to TAP by **evidence reference** (ids only, never raw content);
* claim identity, tenant identity, and the change fingerprint are preserved via
  ``source_identity`` / ``correlation_id`` / ``context`` (the neutral contract
  has no tenant/repo field — see the readiness audit's Evidence & TAP mapping);
* per-claim ``evidence_coverage`` is preserved as **descriptive** and never
  treated as aggregate authorization;
* unsupported / indeterminate outcomes are preserved.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

# Neutral contract + TAP provider — public surfaces only.
from governance_providers.api import AssertionGovernanceRequest  # type: ignore
from tap_provider.api import TAPProvider, TapSettings, build_tap_provider  # type: ignore

from ..claims.manifest import ClaimEntry, ClaimManifest
from ..fingerprints import domain_hash


@dataclass(frozen=True)
class TapAssertionResult:
    """Product record of one per-claim TAP assertion result (by reference)."""

    claim_id: str
    claim_type: str
    coverage: str
    evidence_coverage: float
    covered_evidence_refs: Tuple[str, ...]
    unsupported_elements: Tuple[str, ...]
    provider_trace_id: str
    result_fingerprint: str
    request_fingerprint: str

    @property
    def is_supported(self) -> bool:
        return self.coverage == "SUPPORTED"


@dataclass(frozen=True)
class TapEvaluation:
    """The set of per-claim TAP results for a manifest revision."""

    manifest_fingerprint: str
    results: Tuple[TapAssertionResult, ...]

    def result_for(self, claim_id: str) -> Optional[TapAssertionResult]:
        for r in self.results:
            if r.claim_id == claim_id:
                return r
        return None


def default_tap_provider() -> TAPProvider:
    """Build and initialize a deterministic, caller-supplied-evidence TAP provider."""
    provider = build_tap_provider(
        settings=TapSettings(
            provider_id="tap",
            mode="in_process",
            evidence_resolution="caller_supplied",
            fail_safe=True,
        )
    )
    provider.initialize()
    return provider


class TapClaimAdapter:
    """Adapter that evaluates Claim Manifest claims through the TAP provider."""

    def __init__(self, provider: Optional[TAPProvider] = None) -> None:
        self._provider = provider or default_tap_provider()

    def _build_request(
        self, manifest: ClaimManifest, entry: ClaimEntry
    ) -> AssertionGovernanceRequest:
        return AssertionGovernanceRequest(
            assertion=f"claim:{entry.claim_type.value}",
            assertion_type=entry.claim_type.value,
            evidence_refs=tuple(r.evidence_id for r in entry.evidence_refs),
            source_identity=f"tenant:{manifest.tenant_id}",
            policy_refs=(entry.policy_ref,),
            context={
                "tenant_id": manifest.tenant_id,
                "repository": manifest.repository,
                "base_sha": manifest.base_sha,
                "head_sha": manifest.head_sha,
                "claim_id": entry.claim_id,
                "change_fingerprint": manifest.change_fingerprint,
            },
            correlation_id=entry.claim_id,
        )

    @staticmethod
    def _request_fingerprint(request: AssertionGovernanceRequest) -> str:
        return domain_hash(
            "tap_request.v1",
            {
                "assertion": request.assertion,
                "assertion_type": request.assertion_type,
                "evidence_refs": sorted(request.evidence_refs),
                "source_identity": request.source_identity,
                "policy_refs": sorted(request.policy_refs),
                "correlation_id": request.correlation_id,
            },
        )

    def evaluate_claim(
        self, manifest: ClaimManifest, entry: ClaimEntry
    ) -> TapAssertionResult:
        """Invoke TAP for one claim, preserving claim identity and coverage."""
        request = self._build_request(manifest, entry)
        result = self._provider.evaluate(request)
        return TapAssertionResult(
            claim_id=entry.claim_id,
            claim_type=entry.claim_type.value,
            coverage=result.coverage.value,
            evidence_coverage=float(result.evidence_coverage),
            covered_evidence_refs=tuple(result.covered_evidence_refs),
            unsupported_elements=tuple(result.unsupported_elements),
            provider_trace_id=result.provider_trace_id,
            result_fingerprint=result.fingerprint,
            request_fingerprint=self._request_fingerprint(request),
        )

    def evaluate_manifest(self, manifest: ClaimManifest) -> TapEvaluation:
        """Invoke TAP for every claim in the manifest."""
        results = tuple(self.evaluate_claim(manifest, e) for e in manifest.entries)
        return TapEvaluation(
            manifest_fingerprint=manifest.fingerprint,
            results=results,
        )


__all__ = [
    "TapAssertionResult",
    "TapEvaluation",
    "TapClaimAdapter",
    "default_tap_provider",
]
