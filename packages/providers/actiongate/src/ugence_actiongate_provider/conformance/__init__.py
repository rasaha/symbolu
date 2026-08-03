"""ActionGate-specific conformance — beyond the shared framework kit.

Validates request/result/constraint/obligation/expiry/authority mapping, the
denied and constrained paths, error translation (timeout / unavailable /
malformed), deterministic fingerprints, and repeated-request idempotency.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ugence_governance_provider_framework.api import (
    ActionGovernanceOutcome,
    ActionGovernanceRequest,
    ProviderResultValidationError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

from ..configuration import build_actiongate_provider
from ..core import (
    ActionGateConstraint,
    ActionGateEngine,
    ActionGateObligation,
    ActionGateOutcome,
    ConstrainedRule,
)
from ..mapping import map_request


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ActionGateConformanceReport:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed]

    def summary(self) -> str:
        ok = sum(1 for r in self.results if r.passed)
        return f"actiongate: {ok}/{len(self.results)} specific checks passed"


def _p(**engine_kw):
    p = build_actiongate_provider(ActionGateEngine(**engine_kw))
    p.initialize()
    return p


def run_actiongate_conformance() -> ActionGateConformanceReport:
    rep = ActionGateConformanceReport()

    def check(name, cond, detail=""):
        rep.results.append(CheckResult(name, bool(cond), detail))

    # request mapping preserves fields
    native = map_request(ActionGovernanceRequest(
        action_type="ACT", requested_parameters={"k": "v"}, actor="u",
        authority_context="auth", target_resource="res", policy_refs=("p:1",),
        decision_refs=("d1",), idempotency_key="idem", correlation_id="corr"))
    check("request_mapping",
          native.action_type == "ACT" and native.principal == "u"
          and native.authority == "auth" and native.resource == "res"
          and native.policy_context == ("p:1",) and native.decision_refs == ("d1",)
          and native.idempotency_key == "idem" and native.correlation_id == "corr")

    # result mapping (all four outcomes; unknown never authorizes)
    check("result_allow", _p().authorize(ActionGovernanceRequest("OK")).outcome
          is ActionGovernanceOutcome.AUTHORIZED)
    check("result_denied", _p(denied=frozenset({"D"})).authorize(
        ActionGovernanceRequest("D")).outcome is ActionGovernanceOutcome.DENIED)
    check("result_unknown_indeterminate", _p(unknown=frozenset({"U"})).authorize(
        ActionGovernanceRequest("U")).outcome is ActionGovernanceOutcome.INDETERMINATE)

    rule = ConstrainedRule(
        constraints=(ActionGateConstraint("maximum_amount", "100000"),
                     ActionGateConstraint("required_approval", "senior")),
        obligations=(ActionGateObligation("human_review"),
                     ActionGateObligation("notification", "finance")),
        expiry_seconds=3600)
    constrained = _p(constrained={"C": rule}).authorize(ActionGovernanceRequest("C"))
    check("result_constrained",
          constrained.outcome is ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS)
    check("constraints_preserved",
          "maximum_amount=100000" in constrained.constraints
          and "required_approval=senior" in constrained.constraints)
    check("obligations_preserved",
          "human_review" in constrained.obligations
          and "notification=finance" in constrained.obligations)
    check("expiry_preserved", constrained.expiry is not None)
    check("authority_basis_preserved", bool(constrained.authority_basis))
    check("reason_codes_preserved", bool(constrained.reason_codes))

    # error translation
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

    # deterministic fingerprints (two fresh providers, same request)
    r1 = _p(constrained={"C": rule}).authorize(ActionGovernanceRequest("C"))
    r2 = _p(constrained={"C": rule}).authorize(ActionGovernanceRequest("C"))
    check("deterministic_fingerprint", r1.fingerprint and r1.fingerprint == r2.fingerprint)

    # repeated-request idempotency (same provider, same request → same result)
    prov = _p(constrained={"C": rule})
    a = prov.authorize(ActionGovernanceRequest("C"))
    b = prov.authorize(ActionGovernanceRequest("C"))
    check("repeated_request_idempotency",
          a.fingerprint == b.fingerprint and a.outcome is b.outcome)

    return rep
