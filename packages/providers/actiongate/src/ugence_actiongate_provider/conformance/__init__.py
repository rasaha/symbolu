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


#: Neutral ``ActionGovernanceRequest`` field -> native ``ActionGateRequest``
#: field, where the two vocabularies use different names.
NEUTRAL_TO_NATIVE = {
    "requested_parameters": "parameters",
    "actor": "principal",
    "authority_context": "authority",
    "target_resource": "resource",
    "policy_refs": "policy_context",
}

#: Neutral fields ActionGate deliberately does not carry, each with its reason.
#: Empty today. A field belongs here only after an explicit decision, never as a
#: way to quiet the totality check below.
NEUTRAL_NOT_CARRIED: dict = {}


def unmapped_neutral_fields() -> set:
    """Neutral request fields that do not survive ``map_request``.

    Compares a probe request field-by-field against its mapped counterpart, so
    the check is driven by the neutral dataclass rather than by a list someone
    has to remember to update. ``authorization_expired`` was dropped for exactly
    as long as the equivalent assertion was a hand-written field list.
    """
    import dataclasses

    probe = ActionGovernanceRequest(
        action_type="ACT", requested_parameters={"k": "v"}, actor="u",
        authority_context="auth", target_resource="res", policy_refs=("p:1",),
        risk_context={"score": "low"}, evidence_refs=("e1",), decision_refs=("d1",),
        idempotency_key="idem", correlation_id="corr", authorization_expired=True)
    mapped = map_request(probe)

    _MISSING = object()
    unmapped = set()
    for f in dataclasses.fields(ActionGovernanceRequest):
        if f.name in NEUTRAL_NOT_CARRIED:
            continue
        expected = getattr(probe, f.name)
        actual = getattr(mapped, NEUTRAL_TO_NATIVE.get(f.name, f.name), _MISSING)
        if actual is _MISSING:
            unmapped.add(f.name)
            continue
        # Mappings are copied rather than aliased, so compare by value.
        if isinstance(expected, dict):
            actual, expected = dict(actual), dict(expected)
        if actual != expected:
            unmapped.add(f.name)
    return unmapped


def run_actiongate_conformance() -> ActionGateConformanceReport:
    rep = ActionGateConformanceReport()

    def check(name, cond, detail=""):
        rep.results.append(CheckResult(name, bool(cond), detail))

    # request mapping preserves fields
    native = map_request(ActionGovernanceRequest(
        action_type="ACT", requested_parameters={"k": "v"}, actor="u",
        authority_context="auth", target_resource="res", policy_refs=("p:1",),
        decision_refs=("d1",), idempotency_key="idem", correlation_id="corr",
        risk_context={"score": "low"}, evidence_refs=("e1",),
        authorization_expired=True))
    check("request_mapping",
          native.action_type == "ACT" and native.principal == "u"
          and native.authority == "auth" and native.resource == "res"
          and native.policy_context == ("p:1",) and native.decision_refs == ("d1",)
          and native.idempotency_key == "idem" and native.correlation_id == "corr"
          and native.risk_context == {"score": "low"} and native.evidence_refs == ("e1",)
          and native.authorization_expired is True)

    # request mapping is TOTAL over the neutral contract: no field may be
    # silently dropped the way authorization_expired once was. Driven off the
    # dataclass's own fields, so a newly added neutral field fails this check
    # until it is either mapped or explicitly named as not carried.
    check("request_mapping_total", not unmapped_neutral_fields(),
          detail=f"unmapped: {sorted(unmapped_neutral_fields())}")

    # an expired authorization never authorizes, whatever the policy says
    expired = _p().authorize(ActionGovernanceRequest("OK", authorization_expired=True))
    check("expired_outcome", expired.outcome is ActionGovernanceOutcome.EXPIRED)
    check("expired_never_authorizes",
          expired.outcome not in (ActionGovernanceOutcome.AUTHORIZED,
                                  ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS))
    check("expired_carries_no_authority_basis", expired.authority_basis == "")

    # result mapping (every outcome; unknown and expired never authorize)
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
