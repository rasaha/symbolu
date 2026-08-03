"""TAP-specific conformance — beyond the shared framework kit.

Validates native request mapping, evidence provenance, each outcome mapping
(SUPPORTED / UNSUPPORTED / CONSTRAINED / INDETERMINATE), partial support,
unsupported components, omitted qualifiers, evidence coverage, constraints,
obligations, explanation references, error translation + fail-safe behavior
(malformed / unknown / timeout / unavailable), deterministic fingerprints, input
immutability, and repeated-request idempotency.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ugence_governance_provider_framework.api import (
    AssertionCoverage,
    AssertionGovernanceRequest,
    ProviderResultValidationError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

from ..configuration import build_tap_provider
from ..core import (
    TapConstraint,
    TapEngine,
    TapObligation,
    TapOutcome,
    TapRule,
)
from ..errors import translate_error
from ..core import TapMalformedResult, TapTimeout, TapUnavailable
from ..mapping import map_request


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class TapConformanceReport:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed]

    def summary(self) -> str:
        ok = sum(1 for r in self.results if r.passed)
        return f"tap: {ok}/{len(self.results)} specific checks passed"


def _p(**engine_kw):
    p = build_tap_provider(TapEngine(**engine_kw))
    p.initialize()
    return p


_SUPPLIER = ("Supplier X reduced costs by 20% and has no compliance incidents")

_CONSTRAINED_RULE = TapRule(
    outcome=TapOutcome.CONSTRAINED, evidence_coverage=0.6,
    supported_components=("cost_reduction",),
    unsupported_components=("magnitude_20pct",),
    omitted_qualifiers=("north_america_segment",),
    constraints=(TapConstraint("required_qualifier", "segment_scope"),
                 TapConstraint("maximum_confidence", "0.7")),
    obligations=(TapObligation("include_uncertainty_disclosure"),
                 TapObligation("retain_source_attribution")),
    reason_codes=("scope_expansion", "certainty_inflation"))

_UNSUPPORTED_RULE = TapRule(
    outcome=TapOutcome.UNSUPPORTED, evidence_coverage=0.0,
    unsupported_components=("no_compliance_incidents",),
    reason_codes=("contradicting_evidence",))


def run_tap_conformance() -> TapConformanceReport:
    rep = TapConformanceReport()

    def check(name, cond, detail=""):
        rep.results.append(CheckResult(name, bool(cond), detail))

    # native request mapping preserves fields + evidence provenance
    native = map_request(AssertionGovernanceRequest(
        assertion="X supports Y", assertion_type="claim",
        evidence_refs=("e1", "e2"), source_identity="src",
        policy_refs=("p:1",), context={"k": "v"}, correlation_id="corr"))
    check("native_request_mapping",
          native.assertion == "X supports Y" and native.assertion_type == "claim"
          and native.policy_references == ("p:1",) and native.correlation_id == "corr"
          and native.source_identity == "src" and len(native.evidence) == 2)
    check("evidence_provenance",
          native.evidence[0].source_reference == "e1"
          and native.evidence[0].provenance == "caller_supplied"
          and bool(native.evidence[0].fingerprint))

    supported = _p().evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
    check("supported_mapping", supported.coverage is AssertionCoverage.SUPPORTED)
    check("evidence_coverage", supported.evidence_coverage == 1.0)

    indeterminate = _p().evaluate(AssertionGovernanceRequest("A", evidence_refs=()))
    check("indeterminate_mapping", indeterminate.coverage is AssertionCoverage.INDETERMINATE)
    check("indeterminate_not_supported",
          indeterminate.coverage is not AssertionCoverage.SUPPORTED)

    unsupported = _p(rules={_SUPPLIER: _UNSUPPORTED_RULE}).evaluate(
        AssertionGovernanceRequest(_SUPPLIER, evidence_refs=("e1",)))
    check("unsupported_mapping", unsupported.coverage is AssertionCoverage.UNSUPPORTED)
    check("unsupported_components",
          "no_compliance_incidents" in unsupported.unsupported_elements)

    constrained = _p(rules={_SUPPLIER: _CONSTRAINED_RULE}).evaluate(
        AssertionGovernanceRequest(_SUPPLIER, evidence_refs=("e1", "e2")))
    check("constrained_mapping", constrained.coverage is AssertionCoverage.CONSTRAINED)
    check("partial_support", 0.0 < constrained.evidence_coverage < 1.0)
    check("omitted_qualifiers", "north_america_segment" in constrained.omitted_qualifiers)
    check("constraints_preserved",
          "required_qualifier=segment_scope" in constrained.constraints
          and "maximum_confidence=0.7" in constrained.constraints)
    check("obligations_preserved",
          "include_uncertainty_disclosure" in constrained.obligations
          and "retain_source_attribution" in constrained.obligations)
    check("explanation_refs",
          any(r.startswith("reason:") for r in constrained.explanation_refs)
          and any(r.startswith("supported:") for r in constrained.explanation_refs))

    # native UNKNOWN outcome → INDETERMINATE (never SUPPORTED)
    unknown = _p(emit_unknown=True).evaluate(
        AssertionGovernanceRequest("A", evidence_refs=("e1",)))
    check("unknown_result_indeterminate", unknown.coverage is AssertionCoverage.INDETERMINATE)

    # error translation (native → classified framework error)
    check("timeout_translation",
          isinstance(translate_error(TapTimeout("t")), ProviderTimeoutError))
    check("unavailable_translation",
          isinstance(translate_error(TapUnavailable("u")), ProviderUnavailableError))
    check("malformed_translation",
          isinstance(translate_error(TapMalformedResult("m")), ProviderResultValidationError))

    # fail-safe evaluation: infrastructure failure → INDETERMINATE, never SUPPORTED
    for mode in ("timeout", "unavailable", "malformed"):
        r = _p(fail=mode).evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
        check(f"failsafe_{mode}", r.coverage is AssertionCoverage.INDETERMINATE)

    # deterministic fingerprints (two fresh providers, same request)
    r1 = _p(rules={_SUPPLIER: _CONSTRAINED_RULE}).evaluate(
        AssertionGovernanceRequest(_SUPPLIER, evidence_refs=("e1", "e2")))
    r2 = _p(rules={_SUPPLIER: _CONSTRAINED_RULE}).evaluate(
        AssertionGovernanceRequest(_SUPPLIER, evidence_refs=("e1", "e2")))
    check("deterministic_fingerprint", r1.fingerprint and r1.fingerprint == r2.fingerprint)

    # input immutability
    req = AssertionGovernanceRequest("A", evidence_refs=("e1",))
    original = AssertionGovernanceRequest("A", evidence_refs=("e1",))
    _p().evaluate(req)
    check("input_immutability", req == original)

    # repeated-request idempotency (same provider, same request → same result)
    prov = _p(rules={_SUPPLIER: _CONSTRAINED_RULE})
    a = prov.evaluate(AssertionGovernanceRequest(_SUPPLIER, evidence_refs=("e1", "e2")))
    b = prov.evaluate(AssertionGovernanceRequest(_SUPPLIER, evidence_refs=("e1", "e2")))
    check("repeated_request_idempotency",
          a.fingerprint == b.fingerprint and a.coverage is b.coverage)

    return rep


__all__ = ["TapConformanceReport", "CheckResult", "run_tap_conformance"]
