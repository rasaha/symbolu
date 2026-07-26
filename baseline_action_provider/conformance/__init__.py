"""Baseline-action-specific conformance — beyond the shared framework kit."""
from __future__ import annotations

from dataclasses import dataclass, field

from governance_providers.api import (
    ActionGovernanceOutcome, ActionGovernanceRequest, ProviderResultValidationError,
    ProviderTimeoutError, ProviderUnavailableError)

from ..configuration import build_baseline_action_provider
from ..core import (
    BaselineActionConstraint, BaselineActionEngine, BaselineActionObligation, ConstrainedRule)


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class BaselineActionConformanceReport:
    results: list = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failures(self) -> list:
        return [r for r in self.results if not r.passed]

    def summary(self) -> str:
        ok = sum(1 for r in self.results if r.passed)
        return f"baseline-action: {ok}/{len(self.results)} specific checks passed"


def _p(**engine_kw):
    p = build_baseline_action_provider(BaselineActionEngine(**engine_kw))
    p.initialize()
    return p


def run_baseline_action_conformance() -> BaselineActionConformanceReport:
    rep = BaselineActionConformanceReport()

    def check(name, cond, detail=""):
        rep.results.append(CheckResult(name, bool(cond), detail))

    check("allow", _p().authorize(ActionGovernanceRequest("OK")).outcome
          is ActionGovernanceOutcome.AUTHORIZED)
    check("deny", _p(denied=frozenset({"D"})).authorize(ActionGovernanceRequest("D")).outcome
          is ActionGovernanceOutcome.DENIED)
    check("unknown_indeterminate",
          _p(unknown=frozenset({"U"})).authorize(ActionGovernanceRequest("U")).outcome
          is ActionGovernanceOutcome.INDETERMINATE)

    supported = ConstrainedRule(constraints=(BaselineActionConstraint("maximum_amount", "1000"),),
                                obligations=(BaselineActionObligation("logging", "audit"),))
    c = _p(constrained={"C": supported}).authorize(ActionGovernanceRequest("C"))
    check("supported_constraint",
          c.outcome is ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS)
    check("constraint_preserved", "maximum_amount=1000" in c.constraints)

    # a construct outside the limited vocabulary → INDETERMINATE (never AUTHORIZED)
    unsupported = ConstrainedRule(
        constraints=(BaselineActionConstraint("required_approval", "senior"),))
    u = _p(constrained={"C": unsupported}).authorize(ActionGovernanceRequest("C"))
    check("unsupported_construct_indeterminate",
          u.outcome is ActionGovernanceOutcome.INDETERMINATE)
    check("unsupported_never_authorized",
          u.outcome not in (ActionGovernanceOutcome.AUTHORIZED,
                            ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS))

    def expect(fn, exc):
        try:
            fn(); return False
        except exc:
            return True
        except Exception:
            return False
    check("timeout_translation",
          expect(lambda: _p(fail="timeout").authorize(ActionGovernanceRequest("X")),
                 ProviderTimeoutError))
    check("unavailable_translation",
          expect(lambda: _p(fail="unavailable").authorize(ActionGovernanceRequest("X")),
                 ProviderUnavailableError))
    check("malformed_translation",
          expect(lambda: _p(fail="malformed").authorize(ActionGovernanceRequest("X")),
                 ProviderResultValidationError))

    r1 = _p(constrained={"C": supported}).authorize(ActionGovernanceRequest("C"))
    r2 = _p(constrained={"C": supported}).authorize(ActionGovernanceRequest("C"))
    check("deterministic_fingerprint", r1.fingerprint and r1.fingerprint == r2.fingerprint)
    return rep


__all__ = ["BaselineActionConformanceReport", "run_baseline_action_conformance"]
