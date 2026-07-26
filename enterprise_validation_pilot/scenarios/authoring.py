"""Independent ground-truth authoring (Tasks 102/103).

Generates a deterministic, versioned, synthetic-but-realistic dataset of 90
scenarios (3 domains x 30). This module **must not import or call TAP or
ActionGate** — expected outcomes are authored from design intent, never inferred
from provider output. A dependency-boundary test enforces the no-provider rule.

Design-intent spec functions (`_posture_for`, `_ag_outcome_for`, …) encode the
*designed expectation*; the runner implements the same spec independently, so a
divergence is caught by the evaluator rather than hidden.
"""
from __future__ import annotations

from ..schemas.scenario import (
    ActionPolicy, EvidenceSpec, ExecutionSpec, ExpectedOutcome, HumanReviewSpec,
    ProposedActionSpec, Scenario, TapPolicy)
from ..schemas.taxonomy import (
    ActionClass, AssertionClass, ComplianceVerdict, CrossProviderClass,
    ExecutionBehavior, ReconciliationExpectation, RecommendationPosture)

# --- design-intent spec (author's model of a correct system) ----------------

_POSTURE = {
    "SUPPORTED": RecommendationPosture.ADVANCE.value,
    "CONSTRAINED": RecommendationPosture.HOLD.value,
    "UNSUPPORTED": RecommendationPosture.REJECT.value,
    "INDETERMINATE": RecommendationPosture.REQUEST_ADDITIONAL_EVIDENCE.value,
}


def _posture_for(tap_outcome: str) -> str:
    return _POSTURE[tap_outcome]


def _ag_outcome_for(policy: ActionPolicy) -> str:
    if policy.fail is not None or not policy.available:
        return "INDETERMINATE"
    return {
        "allow": "AUTHORIZED",
        "constrained": "AUTHORIZED_WITH_CONSTRAINTS",
        "deny": "DENIED",
        "unknown": "INDETERMINATE",
    }[policy.mode]


# ActionGate's known control types — expected action constraints/obligations are
# rendered exactly as the ActionGate provider renders them (unknown → "ext:").
_AG_KNOWN_CONSTRAINTS = {"maximum_amount", "execution_deadline", "required_approval",
                        "allowed_region", "parameter_restriction", "rate_limit",
                        "single_use"}
_AG_KNOWN_OBLIGATIONS = {"notification", "logging", "human_review"}


def _encode(pairs, known) -> tuple[str, ...]:
    out = []
    for t, v in pairs:
        prefix = "" if t in known else "ext:"
        out.append(f"{prefix}{t}={v}" if v else f"{prefix}{t}")
    return tuple(out)


# --- domain vocabularies ----------------------------------------------------

_DOMAINS = {
    "procurement": dict(
        action_type="PURCHASE_ORDER", target="ERP", domain_id="procurement",
        required=("amount",), amount_param="amount", limit="100000",
        subject="supplier cost claim"),
    "finance_operations": dict(
        action_type="PAYMENT_RELEASE", target="LEDGER", domain_id="finance_operations",
        required=("amount",), amount_param="amount", limit="250000",
        subject="reconciled balance claim"),
    "refund_operations": dict(
        action_type="ISSUE_REFUND", target="BILLING", domain_id="refund_operations",
        required=("amount",), amount_param="amount", limit="5000",
        subject="refund eligibility claim"),
}


def _evidence(domain: str, n: int, provenance: str = "caller_supplied",
              cls: str = "direct", authority: str = "system") -> tuple[EvidenceSpec, ...]:
    return tuple(
        EvidenceSpec(evidence_id=f"{domain[:3]}-ev-{i}", source_type="record",
                     source_reference=f"{domain}/rec/{i}",
                     content=f"governed excerpt {i}", provenance=provenance,
                     evidence_class=cls, authority=authority)
        for i in range(1, n + 1))


# --- TAP policy factories (assertion classes) -------------------------------

def _tap(outcome, *, coverage=None, supported=(), unsupported=(), omitted=(),
         constraints=(), obligations=(), reasons=(), fail=None, emit_unknown=False):
    return TapPolicy(outcome=outcome, evidence_coverage=coverage,
                     supported_components=tuple(supported),
                     unsupported_components=tuple(unsupported),
                     omitted_qualifiers=tuple(omitted), constraints=tuple(constraints),
                     obligations=tuple(obligations), reason_codes=tuple(reasons),
                     fail=fail, emit_unknown=emit_unknown)


_ASSERTION_RECIPES = {
    AssertionClass.FULLY_SUPPORTED: lambda: (
        _tap("SUPPORTED", coverage=1.0, supported=("primary_claim",),
             reasons=("evidence_supports",)), 2),
    AssertionClass.PARTIALLY_SUPPORTED: lambda: (
        _tap("CONSTRAINED", coverage=0.5, supported=("primary_claim",),
             unsupported=("secondary_claim",),
             constraints=(("allowed_scope", "supported_only"),),
             reasons=("partial_support",)), 2),
    AssertionClass.UNSUPPORTED_COMPONENT: lambda: (
        _tap("UNSUPPORTED", coverage=0.3, supported=("primary_claim",),
             unsupported=("compliance_component",), reasons=("unsupported_component",)), 2),
    AssertionClass.CONTRADICTORY_EVIDENCE: lambda: (
        _tap("UNSUPPORTED", coverage=0.0, unsupported=("contradicted_claim",),
             reasons=("contradicting_evidence",)), 2),
    AssertionClass.MISSING_EVIDENCE: lambda: (
        _tap("INDETERMINATE", coverage=0.0, reasons=("missing_evidence",)), 0),
    AssertionClass.OMITTED_QUALIFIER: lambda: (
        _tap("CONSTRAINED", coverage=0.7, supported=("primary_claim",),
             omitted=("scope_qualifier",),
             constraints=(("required_qualifier", "scope_qualifier"),),
             obligations=(("include_uncertainty_disclosure", ""),),
             reasons=("omitted_qualifier",)), 2),
    AssertionClass.SCOPE_EXPANSION: lambda: (
        _tap("CONSTRAINED", coverage=0.6, supported=("segment_claim",),
             omitted=("segment_scope",),
             constraints=(("allowed_scope", "segment_only"),),
             reasons=("scope_expansion",)), 2),
    AssertionClass.CERTAINTY_INFLATION: lambda: (
        _tap("CONSTRAINED", coverage=0.6, supported=("trend_claim",),
             constraints=(("maximum_confidence", "0.7"),),
             obligations=(("include_uncertainty_disclosure", ""),),
             reasons=("certainty_inflation",)), 2),
    AssertionClass.TEMPORAL_MISMATCH: lambda: (
        _tap("CONSTRAINED", coverage=0.5, supported=("period_claim",),
             omitted=("reporting_period",),
             constraints=(("temporal_limitation", "cited_period"),),
             reasons=("temporal_mismatch",)), 2),
    AssertionClass.POPULATION_OR_SEGMENT_MISMATCH: lambda: (
        _tap("CONSTRAINED", coverage=0.5, supported=("cohort_claim",),
             omitted=("study_population",),
             constraints=(("population_limitation", "cited_cohort"),),
             reasons=("population_mismatch",)), 2),
    AssertionClass.METRIC_MISMATCH: lambda: (
        _tap("CONSTRAINED", coverage=0.5, supported=("metric_claim",),
             unsupported=("reported_metric",),
             constraints=(("metric_limitation", "defined_metric"),),
             reasons=("metric_mismatch",)), 2),
    AssertionClass.SOURCE_AUTHORITY_MISMATCH: lambda: (
        _tap("CONSTRAINED", coverage=0.5, supported=("attributed_claim",),
             constraints=(("required_attribution", "authoritative_source"),),
             reasons=("source_authority_mismatch",)), 2),
}


# --- action policy factories (action classes) -------------------------------

def _action_policy(domain_vocab, action_class: ActionClass) -> tuple[ActionPolicy, dict]:
    """Return (ActionPolicy, proposed_parameter_overrides) for the action class."""
    limit = domain_vocab["limit"]
    amount_param = domain_vocab["amount_param"]
    base = {amount_param: str(int(limit) // 2)}          # inside envelope by default
    ac = action_class
    if ac is ActionClass.AUTHORIZED:
        return ActionPolicy(mode="allow",
                            obligations=(("logging", "audit"),)), base
    if ac is ActionClass.AUTHORIZED_WITH_LIMIT:
        return ActionPolicy(mode="constrained",
                            constraints=(("maximum_amount", limit),),
                            obligations=(("logging", "audit"),)), base
    if ac is ActionClass.AUTHORIZED_WITH_APPROVAL:
        return ActionPolicy(mode="constrained",
                            constraints=(("required_approval", "senior"),),
                            obligations=(("human_review", ""),)), base
    if ac is ActionClass.AUTHORIZED_WITH_NOTIFICATION:
        return ActionPolicy(mode="constrained",
                            constraints=(("allowed_region", "domestic"),),
                            obligations=(("notification", "compliance"),)), {**base, "region": "domestic"}
    if ac is ActionClass.AUTHORIZED_WITH_EXPIRY:
        return ActionPolicy(mode="constrained", expiry_seconds=3600,
                            constraints=(("single_use", "true"),),
                            obligations=(("logging", "audit"),)), base
    if ac is ActionClass.DENIED_BY_POLICY:
        return ActionPolicy(mode="deny"), base
    if ac is ActionClass.DENIED_BY_AUTHORITY:
        return ActionPolicy(mode="deny"), base
    if ac is ActionClass.DENIED_BY_RESOURCE_SCOPE:
        return ActionPolicy(mode="deny"), base
    if ac is ActionClass.INDETERMINATE_POLICY:
        return ActionPolicy(mode="unknown"), base
    if ac is ActionClass.PROVIDER_TIMEOUT:
        return ActionPolicy(mode="allow", fail="timeout"), base
    if ac is ActionClass.PROVIDER_UNAVAILABLE:
        return ActionPolicy(mode="allow", fail="unavailable"), base
    if ac is ActionClass.MALFORMED_PROVIDER_RESULT:
        return ActionPolicy(mode="allow", fail="malformed"), base
    if ac is ActionClass.OBLIGATION_NOT_SATISFIED:
        # a non-blocking constraint keeps the authorization valid while a
        # human-review *obligation* (distinct from a blocking required_approval
        # constraint) governs compliance — execution proceeds, compliance may not
        return ActionPolicy(mode="constrained",
                            constraints=(("execution_deadline", "3600"),),
                            obligations=(("human_review", ""),)), base
    # execution/reconciliation classes authorize normally
    return ActionPolicy(mode="allow", obligations=(("logging", "audit"),)), base


def _expected_action(domain_vocab, action_class, policy, params):
    """Author the expected downstream behavior for the action side."""
    ag_outcome = _ag_outcome_for(policy)
    constraints = _encode(policy.constraints, _AG_KNOWN_CONSTRAINTS)
    obligations = _encode(policy.obligations, _AG_KNOWN_OBLIGATIONS)
    authorized = ag_outcome in ("AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS")
    dispatched = authorized
    behavior = ExecutionBehavior.DISPATCHED_SUCCESS.value
    reconciliation = ReconciliationExpectation.RECONCILED.value
    compliance = ComplianceVerdict.COMPLIANT.value
    if not authorized:
        dispatched = False
        behavior = ExecutionBehavior.NOT_DISPATCHED.value
        reconciliation = ReconciliationExpectation.NONE.value
        compliance = ComplianceVerdict.NOT_APPLICABLE.value
    return ag_outcome, constraints, obligations, dispatched, behavior, reconciliation, compliance


# --- scenario assembly ------------------------------------------------------

def _scenario(domain, idx, assertion_class, action_class, cross_class, *,
              tap_override=None, exec_spec=None, human_review=None,
              params_override=None, exec_behavior=None, reconciliation=None,
              compliance=None, tap_outcome_expected=None, expected_tap=None,
              notes="") -> Scenario:
    vocab = _DOMAINS[domain]
    tap_policy, n_ev = (tap_override if tap_override else _ASSERTION_RECIPES[assertion_class]())
    if isinstance(tap_policy, tuple):  # from recipe
        tap_policy, n_ev = tap_policy
    # expected assertion fields come from the *final* TAP policy (post human review)
    etap = expected_tap or tap_policy
    evidence = _evidence(domain, n_ev)
    policy, params = _action_policy(vocab, action_class)
    if params_override:
        params = {**params, **params_override}
    proposed = ProposedActionSpec(
        action_type=vocab["action_type"], parameters=params, authority="gov",
        resource=f"{vocab['domain_id']}:resource", target_system=vocab["target"],
        domain_id=vocab["domain_id"], required_fields=vocab["required"])
    ex = exec_spec or ExecutionSpec()

    t_out = tap_outcome_expected or etap.outcome
    ag_outcome, con, obl, dispatched, behavior, recon, comp = _expected_action(
        vocab, action_class, policy, params)
    # overrides for execution/reconciliation-class scenarios
    if exec_behavior is not None:
        behavior = exec_behavior
    if reconciliation is not None:
        recon = reconciliation
    if compliance is not None:
        comp = compliance
    # assertion halt gate: a non-supportable assertion never reaches the action
    # layer — no authorization, no dispatch (invariants I1/I2 designed in).
    if t_out not in ("SUPPORTED", "CONSTRAINED"):
        ag_outcome, con, obl = "NONE", (), ()
        dispatched, behavior = False, ExecutionBehavior.NOT_DISPATCHED.value
        recon, comp = (ReconciliationExpectation.NONE.value,
                       ComplianceVerdict.NOT_APPLICABLE.value)
    elif behavior in (ExecutionBehavior.NOT_DISPATCHED.value,
                      ExecutionBehavior.DISPATCH_BLOCKED_BY_CONSTRAINT.value):
        dispatched = False
    expected = ExpectedOutcome(
        tap_outcome=t_out,
        supported_components=etap.supported_components,
        unsupported_components=etap.unsupported_components,
        omitted_qualifiers=etap.omitted_qualifiers,
        evidence_coverage=etap.evidence_coverage,
        recommendation_posture=_posture_for(t_out),
        actiongate_outcome=ag_outcome, constraints=con, obligations=obl,
        dispatched=dispatched, execution_behavior=behavior, reconciliation=recon,
        compliance_verdict=comp,
        audit_milestones=("DECISION_CASE_CREATED", "DECISION_CASE_ASSESSMENT_LINKED",
                          "DECISION_CASE_RECOMMENDATION_ADDED"))
    return Scenario(
        scenario_id=f"{domain}-{idx:03d}", domain=domain,
        assertion_class=assertion_class.value, action_class=action_class.value,
        cross_class=cross_class.value, assertion=f"{vocab['subject']} #{idx}",
        assertion_type="claim", evidence=evidence, tap_policy=tap_policy,
        action_policy=policy, proposed_action=proposed, execution=ex,
        expected=expected, human_review=human_review, notes=notes)


def build_domain(domain: str) -> list[Scenario]:
    vocab = _DOMAINS[domain]
    S = []
    i = 0

    def add(ac_assert, ac_action, cross, **kw):
        nonlocal i
        i += 1
        S.append(_scenario(domain, i, ac_assert, ac_action, cross, **kw))

    # 1-12: every assertion class, authorized/constrained action as appropriate
    add(AssertionClass.FULLY_SUPPORTED, ActionClass.AUTHORIZED,
        CrossProviderClass.SUPPORTED_ASSERTION_AUTHORIZED_ACTION)
    add(AssertionClass.PARTIALLY_SUPPORTED, ActionClass.AUTHORIZED_WITH_LIMIT,
        CrossProviderClass.CONSTRAINED_ASSERTION_CONSTRAINED_ACTION)
    add(AssertionClass.UNSUPPORTED_COMPONENT, ActionClass.AUTHORIZED,
        CrossProviderClass.UNSUPPORTED_ASSERTION_NO_ACTION,
        exec_behavior=ExecutionBehavior.NOT_DISPATCHED.value,
        reconciliation=ReconciliationExpectation.NONE.value,
        compliance=ComplianceVerdict.NOT_APPLICABLE.value,
        notes="unsupported assertion halts before action")
    add(AssertionClass.CONTRADICTORY_EVIDENCE, ActionClass.AUTHORIZED,
        CrossProviderClass.UNSUPPORTED_ASSERTION_NO_ACTION,
        exec_behavior=ExecutionBehavior.NOT_DISPATCHED.value,
        reconciliation=ReconciliationExpectation.NONE.value,
        compliance=ComplianceVerdict.NOT_APPLICABLE.value,
        notes="contradicted assertion halts before action")
    add(AssertionClass.MISSING_EVIDENCE, ActionClass.AUTHORIZED,
        CrossProviderClass.INDETERMINATE_ASSERTION_HUMAN_REVIEW,
        expected_tap=_tap("SUPPORTED", coverage=1.0, supported=("primary_claim",),
                          reasons=("evidence_supports",)),
        human_review=HumanReviewSpec(
            action="supply_evidence", approver="reviewer",
            added_evidence=_evidence(domain, 2, provenance="human_provided",
                                     cls="human_provided", authority="reviewer"),
            reevaluate_tap=_tap("SUPPORTED", coverage=1.0, supported=("primary_claim",),
                                reasons=("evidence_supports",)),
            note="human supplies missing evidence; TAP re-evaluates to SUPPORTED → action proceeds"),
        notes="INDETERMINATE → human evidence → re-evaluate to SUPPORTED → authorized action")
    add(AssertionClass.OMITTED_QUALIFIER, ActionClass.AUTHORIZED_WITH_APPROVAL,
        CrossProviderClass.CONSTRAINED_ASSERTION_CONSTRAINED_ACTION,
        human_review=HumanReviewSpec(action="approve_action", approver="senior",
                                     note="human approval obligation satisfied"))
    add(AssertionClass.SCOPE_EXPANSION, ActionClass.AUTHORIZED_WITH_NOTIFICATION,
        CrossProviderClass.CONSTRAINED_ASSERTION_CONSTRAINED_ACTION)
    add(AssertionClass.CERTAINTY_INFLATION, ActionClass.AUTHORIZED_WITH_EXPIRY,
        CrossProviderClass.CONSTRAINED_ASSERTION_CONSTRAINED_ACTION)
    add(AssertionClass.TEMPORAL_MISMATCH, ActionClass.AUTHORIZED_WITH_LIMIT,
        CrossProviderClass.CONSTRAINED_ASSERTION_CONSTRAINED_ACTION)
    add(AssertionClass.POPULATION_OR_SEGMENT_MISMATCH, ActionClass.AUTHORIZED_WITH_APPROVAL,
        CrossProviderClass.CONSTRAINED_ASSERTION_CONSTRAINED_ACTION,
        human_review=HumanReviewSpec(action="approve_action", approver="senior"))
    add(AssertionClass.METRIC_MISMATCH, ActionClass.AUTHORIZED_WITH_LIMIT,
        CrossProviderClass.CONSTRAINED_ASSERTION_CONSTRAINED_ACTION)
    add(AssertionClass.SOURCE_AUTHORITY_MISMATCH, ActionClass.AUTHORIZED,
        CrossProviderClass.CONSTRAINED_ASSERTION_CONSTRAINED_ACTION)

    # 13-17: denial / indeterminate action paths (supported assertion, action gated)
    add(AssertionClass.FULLY_SUPPORTED, ActionClass.DENIED_BY_POLICY,
        CrossProviderClass.SUPPORTED_ASSERTION_ACTION_DENIED)
    add(AssertionClass.FULLY_SUPPORTED, ActionClass.DENIED_BY_AUTHORITY,
        CrossProviderClass.SUPPORTED_ASSERTION_ACTION_DENIED)
    add(AssertionClass.FULLY_SUPPORTED, ActionClass.DENIED_BY_RESOURCE_SCOPE,
        CrossProviderClass.SUPPORTED_ASSERTION_ACTION_DENIED)
    add(AssertionClass.FULLY_SUPPORTED, ActionClass.INDETERMINATE_POLICY,
        CrossProviderClass.INDETERMINATE_ASSERTION_HUMAN_REVIEW)
    add(AssertionClass.FULLY_SUPPORTED, ActionClass.AUTHORIZED_WITH_LIMIT,
        CrossProviderClass.SUPPORTED_ASSERTION_AUTHORIZED_ACTION,
        params_override={vocab["amount_param"]: str(int(vocab["limit"]) * 2)},
        exec_behavior=ExecutionBehavior.DISPATCH_BLOCKED_BY_CONSTRAINT.value,
        reconciliation=ReconciliationExpectation.NONE.value,
        compliance=ComplianceVerdict.NOT_APPLICABLE.value,
        notes="action amount exceeds maximum_amount → dispatch blocked before execution")

    # 18-21: provider failure (assertion + action) — fail-safe
    add(AssertionClass.FULLY_SUPPORTED, ActionClass.PROVIDER_TIMEOUT,
        CrossProviderClass.ACTION_PROVIDER_FAILURE,
        exec_behavior=ExecutionBehavior.NOT_DISPATCHED.value,
        reconciliation=ReconciliationExpectation.NONE.value,
        compliance=ComplianceVerdict.NOT_APPLICABLE.value)
    add(AssertionClass.FULLY_SUPPORTED, ActionClass.PROVIDER_UNAVAILABLE,
        CrossProviderClass.ACTION_PROVIDER_FAILURE,
        exec_behavior=ExecutionBehavior.NOT_DISPATCHED.value,
        reconciliation=ReconciliationExpectation.NONE.value,
        compliance=ComplianceVerdict.NOT_APPLICABLE.value)
    add(AssertionClass.FULLY_SUPPORTED, ActionClass.MALFORMED_PROVIDER_RESULT,
        CrossProviderClass.ACTION_PROVIDER_FAILURE,
        exec_behavior=ExecutionBehavior.NOT_DISPATCHED.value,
        reconciliation=ReconciliationExpectation.NONE.value,
        compliance=ComplianceVerdict.NOT_APPLICABLE.value)
    add(AssertionClass.FULLY_SUPPORTED, ActionClass.AUTHORIZED,
        CrossProviderClass.ASSERTION_PROVIDER_FAILURE,
        tap_override=(_tap("INDETERMINATE", fail="timeout"), 2),
        expected_tap=_tap("INDETERMINATE", coverage=0.0),  # fail-safe result carries 0.0
        tap_outcome_expected="INDETERMINATE",
        notes="TAP infrastructure failure is fail-safe INDETERMINATE (halts before action)")

    # 22-25: execution / reconciliation outcomes (authorized, then execution varies)
    add(AssertionClass.FULLY_SUPPORTED, ActionClass.EXECUTION_BUSINESS_FAILURE,
        CrossProviderClass.SUPPORTED_ASSERTION_AUTHORIZED_ACTION,
        exec_spec=ExecutionSpec(business_outcome="FAILED"),
        exec_behavior=ExecutionBehavior.EXECUTION_FAILED.value,
        reconciliation=ReconciliationExpectation.FAILED.value,
        compliance=ComplianceVerdict.NONCOMPLIANT.value,
        notes="executed but business-failed; reconciliation records failure")
    add(AssertionClass.FULLY_SUPPORTED, ActionClass.EXECUTION_TRANSPORT_FAILURE,
        CrossProviderClass.SUPPORTED_ASSERTION_AUTHORIZED_ACTION,
        exec_spec=ExecutionSpec(transport_fail=True),
        exec_behavior=ExecutionBehavior.TRANSPORT_FAILED.value,
        reconciliation=ReconciliationExpectation.FAILED.value,
        compliance=ComplianceVerdict.NONCOMPLIANT.value)
    add(AssertionClass.FULLY_SUPPORTED, ActionClass.RECONCILIATION_MISMATCH,
        CrossProviderClass.SUPPORTED_ASSERTION_AUTHORIZED_ACTION,
        exec_spec=ExecutionSpec(observed_overrides={vocab["amount_param"]: "1"}),
        exec_behavior=ExecutionBehavior.DISPATCHED_SUCCESS.value,
        reconciliation=ReconciliationExpectation.MISMATCHED.value,
        compliance=ComplianceVerdict.NONCOMPLIANT.value,
        notes="observed parameters differ from authorized → reconciliation mismatch")
    add(AssertionClass.OMITTED_QUALIFIER, ActionClass.OBLIGATION_NOT_SATISFIED,
        CrossProviderClass.CONSTRAINED_ASSERTION_CONSTRAINED_ACTION,
        human_review=HumanReviewSpec(action="decline_action", approver="senior",
                                     note="required human approval NOT granted"),
        compliance=ComplianceVerdict.NONCOMPLIANT.value,
        notes="action executes but human-approval obligation unmet → noncompliant")

    # 26-30: peer-availability / degraded / both-available cross classes
    add(AssertionClass.FULLY_SUPPORTED, ActionClass.AUTHORIZED,
        CrossProviderClass.BOTH_PROVIDERS_AVAILABLE)
    add(AssertionClass.PARTIALLY_SUPPORTED, ActionClass.AUTHORIZED_WITH_LIMIT,
        CrossProviderClass.CONSTRAINED_ASSERTION_CONSTRAINED_ACTION)
    add(AssertionClass.FULLY_SUPPORTED, ActionClass.AUTHORIZED,
        CrossProviderClass.ONE_PROVIDER_DEGRADED, notes="ActionGate degraded but authorizes")
    add(AssertionClass.UNSUPPORTED_COMPONENT, ActionClass.DENIED_BY_POLICY,
        CrossProviderClass.UNSUPPORTED_ASSERTION_NO_ACTION,
        exec_behavior=ExecutionBehavior.NOT_DISPATCHED.value,
        reconciliation=ReconciliationExpectation.NONE.value,
        compliance=ComplianceVerdict.NOT_APPLICABLE.value)
    add(AssertionClass.MISSING_EVIDENCE, ActionClass.INDETERMINATE_POLICY,
        CrossProviderClass.INDETERMINATE_ASSERTION_HUMAN_REVIEW,
        exec_behavior=ExecutionBehavior.NOT_DISPATCHED.value,
        reconciliation=ReconciliationExpectation.NONE.value,
        compliance=ComplianceVerdict.NOT_APPLICABLE.value)
    return S


def build_dataset_scenarios() -> list[Scenario]:
    out: list[Scenario] = []
    for domain in _DOMAINS:
        out.extend(build_domain(domain))
    return out
