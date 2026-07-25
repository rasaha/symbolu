"""Baseline-assertion-specific conformance — beyond the shared framework kit."""
from __future__ import annotations

from dataclasses import dataclass, field

from governance_providers.api import AssertionCoverage, AssertionGovernanceRequest

from ..configuration import build_baseline_assertion_provider
from ..core import BaselineAssertionEngine, BaselineAssertionOutcome, BaselineRule


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class BaselineAssertionConformanceReport:
    results: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failures(self) -> list:
        return [r for r in self.results if not r.passed]

    def summary(self) -> str:
        ok = sum(1 for r in self.results if r.passed)
        return f"baseline-assertion: {ok}/{len(self.results)} specific checks passed"


def _p(**engine_kw):
    p = build_baseline_assertion_provider(BaselineAssertionEngine(**engine_kw))
    p.initialize()
    return p


def run_baseline_assertion_conformance() -> BaselineAssertionConformanceReport:
    rep = BaselineAssertionConformanceReport()

    def check(name, cond, detail=""):
        rep.results.append(CheckResult(name, bool(cond), detail))

    check("supported_on_evidence",
          _p().evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",))).coverage
          is AssertionCoverage.SUPPORTED)
    check("missing_evidence_indeterminate",
          _p().evaluate(AssertionGovernanceRequest("A", evidence_refs=())).coverage
          is AssertionCoverage.INDETERMINATE)
    check("contradiction_unsupported",
          _p().evaluate(AssertionGovernanceRequest(
              "A", evidence_refs=("e1",), context={"stance:e1": "contradicts"})).coverage
          is AssertionCoverage.UNSUPPORTED)
    # a capability-requiring assertion authored as INDETERMINATE stays fail-safe
    rule = BaselineRule(outcome=BaselineAssertionOutcome.INDETERMINATE,
                        reason_codes=("insufficient_capability",))
    r = _p(rules={"Q": rule}).evaluate(AssertionGovernanceRequest("Q", evidence_refs=("e1",)))
    check("capability_limited_indeterminate", r.coverage is AssertionCoverage.INDETERMINATE)
    check("never_constrained",
          r.coverage is not AssertionCoverage.CONSTRAINED)     # baseline emits no CONSTRAINED

    for mode, need_indeterminate in (("timeout", True), ("unavailable", True), ("malformed", True)):
        res = _p(fail=mode).evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
        check(f"failsafe_{mode}", res.coverage is AssertionCoverage.INDETERMINATE)

    r1 = _p().evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
    r2 = _p().evaluate(AssertionGovernanceRequest("A", evidence_refs=("e1",)))
    check("deterministic_fingerprint", r1.fingerprint and r1.fingerprint == r2.fingerprint)

    req = AssertionGovernanceRequest("A", evidence_refs=("e1",))
    original = AssertionGovernanceRequest("A", evidence_refs=("e1",))
    _p().evaluate(req)
    check("input_immutability", req == original)
    return rep


__all__ = ["BaselineAssertionConformanceReport", "run_baseline_assertion_conformance"]
