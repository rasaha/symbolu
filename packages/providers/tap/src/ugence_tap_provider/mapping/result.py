"""Result mapping: native TapEvaluationResult → neutral AssertionGovernanceResult.

Outcome map (uncertainty is never promoted to support):

    SUPPORTED     → SUPPORTED
    UNSUPPORTED   → UNSUPPORTED
    CONSTRAINED   → CONSTRAINED
    INDETERMINATE → INDETERMINATE
    UNKNOWN / any unmapped → INDETERMINATE   (never SUPPORTED)

Component-level findings that the generic contract exposes directly are mapped
straight through (unsupported components → ``unsupported_elements``; omitted
qualifiers → ``omitted_qualifiers``; constraints/obligations → encoded string
tuples). Findings the generic contract does **not** expose a field for — the
*supported* component breakdown and the native *reason codes* — are retained in
provider-owned ``explanation_refs`` (``supported:<component>`` / ``reason:<code>``)
rather than dropped or forced into a framework change.
"""

from __future__ import annotations

import hashlib
import json

from ugence_governance_provider_framework.api import AssertionCoverage, AssertionGovernanceResult

from ..core import TapEvaluationResult, TapOutcome
from .controls import encode_constraints, encode_obligations

_OUTCOME_MAP = {
    TapOutcome.SUPPORTED: AssertionCoverage.SUPPORTED,
    TapOutcome.UNSUPPORTED: AssertionCoverage.UNSUPPORTED,
    TapOutcome.CONSTRAINED: AssertionCoverage.CONSTRAINED,
    TapOutcome.INDETERMINATE: AssertionCoverage.INDETERMINATE,
    TapOutcome.UNKNOWN: AssertionCoverage.INDETERMINATE,
}

#: The framework mapping-contract version (published in observability).
MAPPING_VERSION = "tap-map-1"


def _explanation_refs(result: TapEvaluationResult) -> tuple[str, ...]:
    refs: list[str] = []
    refs.extend(f"supported:{c}" for c in result.supported_components)
    refs.extend(f"reason:{c}" for c in result.reason_codes)
    return tuple(refs)


def _fingerprint(coverage: AssertionCoverage, ratio: float,
                 covered: tuple[str, ...], unsupported: tuple[str, ...],
                 omitted: tuple[str, ...], constraints: tuple[str, ...],
                 obligations: tuple[str, ...], trace: str) -> str:
    payload = json.dumps({
        "coverage": coverage.value, "ratio": round(ratio, 4),
        "covered": sorted(covered), "unsupported": sorted(unsupported),
        "omitted": sorted(omitted), "constraints": sorted(constraints),
        "obligations": sorted(obligations), "trace": trace,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def map_result(result: TapEvaluationResult) -> AssertionGovernanceResult:
    # Unknown / unmapped native outcome must never be represented as supported.
    coverage = _OUTCOME_MAP.get(result.outcome, AssertionCoverage.INDETERMINATE)
    ratio = 0.0 if result.evidence_coverage is None else float(result.evidence_coverage)
    ratio = max(0.0, min(1.0, ratio))
    constraints = encode_constraints(result.constraints)
    obligations = encode_obligations(result.obligations)
    covered = result.covered_evidence_ids
    fp = _fingerprint(coverage, ratio, covered, result.unsupported_components,
                      result.omitted_qualifiers, constraints, obligations, result.trace_id)
    return AssertionGovernanceResult(
        coverage=coverage,
        evidence_coverage=ratio,
        covered_evidence_refs=covered,
        unsupported_elements=result.unsupported_components,
        omitted_qualifiers=result.omitted_qualifiers,
        constraints=constraints,
        obligations=obligations,
        explanation_refs=_explanation_refs(result),
        provider_trace_id=result.trace_id,
        fingerprint=fp,
    )


def indeterminate_result(*, reason: str, trace_id: str = "") -> AssertionGovernanceResult:
    """A fail-safe INDETERMINATE result for a normalized infrastructure failure.

    Infrastructure failure (timeout / unavailable / malformed / protocol) is never
    represented as SUPPORTED — it becomes INDETERMINATE with the normalized reason
    retained in ``explanation_refs``.
    """
    fp = _fingerprint(AssertionCoverage.INDETERMINATE, 0.0, (), (), (), (), (), trace_id)
    return AssertionGovernanceResult(
        coverage=AssertionCoverage.INDETERMINATE, evidence_coverage=0.0,
        explanation_refs=(f"reason:{reason}",), provider_trace_id=trace_id, fingerprint=fp)
