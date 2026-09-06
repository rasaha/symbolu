"""Truth & Evidence adapter — Truth Assurance Platform (assertion governance).

Wraps the real TAP provider (``build_tap_provider``) through the frozen public
surfaces of the canonical distributions ``ugence-tap-provider`` and
``ugence-governance-provider-framework``. TAP evaluates only whether an assertion is
supported by evidence; it never authorizes actions.

CP-5: the import names the canonical package, not the legacy root ``tap_provider`` /
``governance_providers`` namespaces, for the reason recorded in ``action_control``.

TAP is an EMERGING capability — labelled as such in the console — and this wiring
runs its in-process engine on the request's evidence references.
"""

from __future__ import annotations

from ..models import AssertionRequest, AssertionVerdict

_available = True
_reason = ""
try:  # fail-safe import
    from ugence_governance_provider_framework.api import AssertionGovernanceRequest
    from ugence_tap_provider.configuration import build_tap_provider
    _provider = build_tap_provider()
except Exception as exc:  # noqa: BLE001
    _available = False
    _reason = f"{type(exc).__name__}: {exc}"
    _provider = None


def available() -> tuple[bool, str]:
    return _available, _reason


def evaluate(req: AssertionRequest) -> AssertionVerdict:
    if not _available or _provider is None:
        raise RuntimeError(f"tap unavailable: {_reason}")

    native = AssertionGovernanceRequest(
        assertion=req.assertion,
        assertion_type=req.assertion_type,
        evidence_refs=tuple(req.evidence_refs),
        source_identity=req.source_identity,
        policy_refs=tuple(req.policy_refs),
        correlation_id=req.correlation_id,
    )
    res = _provider.evaluate(native)
    return AssertionVerdict(
        coverage=res.coverage.value,
        evidence_coverage=res.evidence_coverage,
        covered_evidence_refs=list(res.covered_evidence_refs),
        unsupported_elements=list(res.unsupported_elements),
        constraints=list(res.constraints),
        obligations=list(res.obligations),
        provider_trace_id=res.provider_trace_id,
    )
