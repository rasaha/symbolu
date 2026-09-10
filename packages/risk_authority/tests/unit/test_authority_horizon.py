"""Delegated authority bounds what it delegates — in time, not only in scope.

Two defects, found by auditing the temporal-boundary family and fixed together because
neither is closed by the other.

**The operator.** ``AuthorityGrant.is_active`` was inclusive, so a grant expiring at
exactly ``now`` was still "active" and ``authority_violations`` returned no reasons. That
is an authorization gate, not a freshness report: it decides who may mint a
``RiskDecision`` at all.

**The reach.** ``RiskDecision.expires_at`` was ``now + DEFAULT_DECISION_TTL``,
uncapped. So the boundary instant did not cost a microsecond — a grant expiring at ``now``
minted a decision valid a full hour, and an envelope minted from that decision as late as
the decision allowed carried a further envelope TTL on top. Measured before the fix,
machine authority reached ``1:29:59.999999`` past a delegation that had already expired
when it was exercised.

Fixing only the operator would have moved that ninety-minute reach one microsecond
earlier. Fixing only the cap would have left the boundary instant able to start the chain.
The tests below pin both, and the reach test is the one that would have caught the real
exposure.

A third gap surfaced while proving it: ``EnvelopeIssuer.issue`` did not cap the envelope by
the decision's expiry — only the issuance seam did — so a direct caller with a generous
``ttl`` produced an envelope outliving its decision by hours. The reach assertion cannot
hold without closing that, so it is closed at the service.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from risk_authority.domain import freshness_horizon
from risk_authority.domain.authority import AuthorityGrant, authority_violations
from risk_authority.domain.controls import ControlResult
from risk_authority.domain.enums import ControlStatus, RiskCaseState, RiskClass
from risk_authority.domain.errors import AuthorityDeniedError, RiskAuthorityError

from ..scenario import (
    ACTOR,
    FINANCE_SCOPE,
    FIXED_NOW,
    MODEL,
    PRINCIPAL,
    TENANT,
    approved_envelope,
    build_application,
    build_grant,
)

#: The smallest instant a ``datetime`` can represent.
EPS = timedelta(microseconds=1)


def _grant_expiring_at(when) -> AuthorityGrant:
    return replace(build_grant(), expires_at=when)


def _violations_at(grant, now) -> list[str]:
    return authority_violations(
        grant,
        tenant_id=TENANT,
        domain="FINANCE",
        risk_class=RiskClass.MEDIUM,
        autonomy_level=2,
        requested_scope=FINANCE_SCOPE,
        now=now,
    )


def _app_with(grant):
    app = build_application()
    app.authority._grants.clear()
    app.authority.add_grant(grant)
    return app


# ------------------------------------------------------- the operator: is_active
@pytest.mark.parametrize(
    "offset,active,label",
    [
        (-EPS, True, "one instant before expiry"),
        (timedelta(0), False, "at exactly expires_at"),
        (EPS, False, "one instant after expiry"),
    ],
)
def test_grant_activity_is_half_open(offset, active, label):
    """``[.., expires_at)`` at all three instants that can distinguish the rules."""

    grant = _grant_expiring_at(FIXED_NOW)

    assert grant.is_active(FIXED_NOW + offset) is active, label


def test_authority_is_denied_at_exactly_the_grant_expiry():
    """The gate that matters: violations, not just the predicate."""

    grant = _grant_expiring_at(FIXED_NOW)

    assert _violations_at(grant, FIXED_NOW - EPS) == []
    assert "grant expired" in _violations_at(grant, FIXED_NOW)


def test_an_unbounded_grant_is_unaffected():
    """``expires_at is None`` means no upper bound, not a zero one."""

    grant = _grant_expiring_at(None)

    assert grant.is_active(FIXED_NOW) and grant.is_active(FIXED_NOW + timedelta(days=3650))
    assert _violations_at(grant, FIXED_NOW) == []


# ------------------------------------------------------------- the reach: the cap
def test_a_decision_never_outlives_the_grant_that_authorized_it():
    """The cap, at the seam that mints decisions.

    The grant expires well inside ``DEFAULT_DECISION_TTL``, so the cap — not the TTL — is
    what decides, and a regression that dropped the cap would show as a full-hour expiry.
    """

    horizon = FIXED_NOW + timedelta(minutes=10)
    app = _app_with(_grant_expiring_at(horizon))

    _evaluation, decision, _envelope = approved_envelope(app)

    assert decision.expires_at == horizon, (
        f"decision expires at {decision.expires_at.isoformat()}, past the grant horizon "
        f"{horizon.isoformat()}; DEFAULT_DECISION_TTL would give "
        f"{(FIXED_NOW + timedelta(hours=1)).isoformat()}")


def test_the_total_reach_past_an_expired_grant_is_zero():
    """The regression test for the ninety minutes. This is the one that mattered.

    Mints through the real path with a short-lived grant, then issues an envelope as late
    as the decision still permits and with a TTL far longer than the grant's remaining
    life — the exact shape that previously produced 1:29:59.999999 of authority past an
    expired delegation.
    """

    horizon = FIXED_NOW + timedelta(minutes=10)
    app = _app_with(_grant_expiring_at(horizon))
    _evaluation, decision, _envelope = approved_envelope(app)

    latest_issuance = decision.expires_at - EPS
    envelope = app._issuer_service.issue(
        envelope_id="env_reach",
        decision=decision,
        audience="finance-agent-runtime",
        subject=ACTOR,
        model_id=MODEL,
        session_id="sess_reach",
        nonce="nonce_reach",
        key_record=app._key_record,
        revocation_state=app.revocation,
        now=latest_issuance,
        ttl=timedelta(hours=6),
    )

    reach = envelope.expires_at - horizon
    assert reach <= timedelta(0), (
        f"machine authority reaches {reach} past a grant that expired at "
        f"{horizon.isoformat()}; envelope expires {envelope.expires_at.isoformat()}")


def test_an_envelope_never_outlives_its_decision_even_from_the_service():
    """The third gap: the service capped nothing, only the seam did.

    A six-hour TTL against a one-hour decision previously gave five hours of envelope
    authority no decision covered.
    """

    app = build_application()
    _evaluation, decision, _envelope = approved_envelope(app)

    envelope = app._issuer_service.issue(
        envelope_id="env_cap",
        decision=decision,
        audience="finance-agent-runtime",
        subject=ACTOR,
        model_id=MODEL,
        session_id="sess_cap",
        nonce="nonce_cap",
        key_record=app._key_record,
        revocation_state=app.revocation,
        now=FIXED_NOW,
        ttl=timedelta(hours=6),
    )

    assert envelope.expires_at <= decision.expires_at, (
        f"envelope outlives its decision by "
        f"{envelope.expires_at - decision.expires_at}")


def test_a_grant_expiring_at_the_issuance_instant_cannot_mint_at_all():
    """The operator catches this one before any cap is computed."""

    app = _app_with(_grant_expiring_at(FIXED_NOW))

    with pytest.raises((AuthorityDeniedError, RiskAuthorityError), match="expired|validity"):
        approved_envelope(app)


def test_a_zero_width_horizon_is_refused_rather_than_minted_already_expired():
    """The freshness bounds are still inclusive, and that makes this reachable.

    A control PASS is ``is_current`` at exactly its ``valid_until`` — the ``valid_until``
    family was deliberately left inclusive by the ruling — so it satisfies the required
    set and the evaluation allows. Its freshness horizon is then exactly ``now``, capping
    the decision to a window of zero width. Under the half-open rule such a decision
    authorizes nothing at any instant, so it must be refused rather than returned already
    expired, which would push the failure to a later and less obvious refusal.

    This is the interaction between the two boundary conventions the ruling deliberately
    left different. It is not hypothetical, and without this test the refusal branch is
    dead code that a mutation survives.
    """

    from risk_authority.services.decision_authority import ReferenceDecisionAuthority

    app = build_application()
    evaluation, _decision, _envelope = approved_envelope(app)

    with pytest.raises(AuthorityDeniedError, match="no validity remains"):
        ReferenceDecisionAuthority().issue_decision(
            decision_id="risk_dec_zero",
            case=app.cases.get(TENANT, "rdc_1"),
            evaluation=evaluation,
            grant=build_grant(),
            requested_scope=FINANCE_SCOPE,
            evidence_snapshot_digest="",
            model_digest="",
            now=FIXED_NOW,
            prerequisite_horizons={"control_freshness": FIXED_NOW},
        )


# --------------------------------------------------------- the freshness horizon
def _pass(control_id, valid_until):
    return ControlResult(
        control_id=control_id,
        status=ControlStatus.PASS,
        evaluated_at=FIXED_NOW - timedelta(hours=1),
        valid_until=valid_until,
    )


def test_evidence_bounds_cap_transitively_through_the_control_horizon():
    """Evidence is covered by construction, not by omission.

    ``binding._freshness_is_monotonic`` refuses any trusted control result whose
    ``valid_until`` outlives the earliest ``valid_until`` of its admitted backing
    evidence. So a control horizon is already no later than the evidence floor beneath it,
    and capping the decision by the control horizon caps it by the evidence too. Asserting
    the invariant here rather than assuming it, because the whole evidence bullet of the
    ruling rests on it.
    """

    from risk_authority.domain.binding import AdmittedContext, _freshness_is_monotonic

    evidence_floor = FIXED_NOW + timedelta(minutes=5)
    admitted = AdmittedContext(valid_until_by_id={"ev1": evidence_floor})

    within = replace(_pass("A", evidence_floor), evidence_ids=("ev1",))
    outliving = replace(
        _pass("A", evidence_floor + EPS), evidence_ids=("ev1",))
    non_expiring = replace(_pass("A", None), evidence_ids=("ev1",))

    assert _freshness_is_monotonic(within, admitted)
    assert not _freshness_is_monotonic(outliving, admitted)
    assert not _freshness_is_monotonic(non_expiring, admitted)


def test_downstream_execution_authority_inherits_the_cap():
    """Reach past the earliest authorizing bound is zero for the *action* too.

    ``ActionAuthorization.expires_at`` is copied from the envelope at admission, so the
    chain grant -> decision -> envelope -> authorization must not widen at any hop.
    """

    from risk_authority.api import ActionAdmissionRequest, ActionAdmissionSeam
    from risk_authority.domain.actions import CanonicalAction

    horizon = FIXED_NOW + timedelta(minutes=10)
    app = _app_with(_grant_expiring_at(horizon))
    _evaluation, decision, envelope = approved_envelope(app)

    action = CanonicalAction(
        tenant_id=TENANT, actor_id=ACTOR, model_id=MODEL, action_type="crm.read",
        target_id="txn", purpose="CUSTOMER_REFUND_REVIEW",
        destination="internal://finance")
    admitted = ActionAdmissionSeam.reference(
        app=app, clock=lambda: FIXED_NOW).issue(
        ActionAdmissionRequest(tenant_id=TENANT, envelope_id=envelope.envelope_id,
                               action=action, session_id=envelope.session_id))

    assert admitted.admitted, (admitted.refusal, admitted.detail)
    for name, bound in (
        ("decision", decision.expires_at),
        ("envelope", envelope.expires_at),
        ("authorization", admitted.authorization.expires_at),
    ):
        assert bound <= horizon, (
            f"{name} reaches {bound - horizon} past the grant horizon "
            f"{horizon.isoformat()}")


# ------------------------------------------------- the subject assertion as a bound
def _seam_at(now):
    from ..adversarial.test_phase4b_admission_adversarial import (
        CallLog, SpyClock, production_seam, v2_request)

    log = CallLog()
    seam, _ = production_seam(log=log, clock=SpyClock(log, now))
    return seam.evaluate(v2_request())


def _subject_bound():
    from ..adversarial.test_phase4b_admission_adversarial import adr_context

    return adr_context().subject_valid_until


def test_a_decision_never_outlives_the_subject_assertion_that_authorized_it():
    """Mid-window the subject bound, not the decision TTL, is what decides.

    The default TTL would put this decision an hour past the subject's own upper bound.
    """

    bound = _subject_bound()
    result = _seam_at(bound - timedelta(minutes=5))

    assert result.non_decision_reason is None, result.non_decision_reason
    assert result.decision_snapshot["expires_at"].startswith(
        bound.isoformat().replace("+00:00", "")), (
        f"decision expires {result.decision_snapshot['expires_at']}, not capped at the "
        f"subject bound {bound.isoformat()}")


def test_the_subject_window_itself_is_still_inclusive_at_its_terminal_instant():
    """T-3: the point-in-time contract is preserved, not quietly narrowed.

    At exactly ``subject_valid_until`` the subject is *not* reported expired. That is the
    ratified inclusive endpoint, and it must survive the capping work.
    """

    from risk_authority.integrations.evaluation_contracts import (
        SubjectRiskNonDecisionReason)

    result = _seam_at(_subject_bound())

    assert result.non_decision_reason is not SubjectRiskNonDecisionReason.EXPIRED_SUBJECT


def test_a_terminal_instant_subject_mints_no_executable_decision_and_names_why():
    """T-3's consequence, with a reason that attributes the cause correctly.

    The subject holds at exactly its upper bound, so the cap lands on ``now`` and no
    positive validity window remains. The authority refuses rather than minting a decision
    that is already expired.

    The reason must be neither ``EXPIRED_SUBJECT`` — the subject is *not* expired here,
    which is the whole point of T-3 — nor ``AUTHORITY_UNAVAILABLE``, which blames the
    evaluator principal for a subject-window cause. Both were the status quo at some point
    in this work and both misattributed it in the audit record.
    """

    from risk_authority.integrations.evaluation_contracts import (
        SubjectRiskNonDecisionReason)

    result = _seam_at(_subject_bound())

    assert result.decision_snapshot is None, "no decision may be minted at this instant"
    assert result.non_decision_reason is (
        SubjectRiskNonDecisionReason.NO_REMAINING_SUBJECT_VALIDITY), result.non_decision_reason
    assert "subject_validity:no_remaining_window" in result.reason_codes


def test_the_typed_error_names_which_prerequisite_bound():
    """The seam maps by type and field, never by parsing a reason string."""

    from risk_authority.domain.errors import (
        AuthorityDeniedError, NoRemainingValidityError)

    err = NoRemainingValidityError(["bound"], prerequisite="subject_assertion")

    assert err.prerequisite == "subject_assertion"
    assert isinstance(err, AuthorityDeniedError), (
        "must stay catchable by every existing AuthorityDeniedError handler")


def test_the_freshness_horizon_is_the_earliest_backing_bound():
    early = FIXED_NOW + timedelta(minutes=5)
    late = FIXED_NOW + timedelta(hours=2)

    horizon = freshness_horizon(
        ("A", "B"), (_pass("A", late), _pass("B", early)))

    assert horizon == early


def test_an_unbounded_control_imposes_no_horizon():
    """``None`` means no cap, never a cap of zero."""

    assert freshness_horizon(("A",), (_pass("A", None),)) is None


def test_controls_outside_the_required_set_do_not_bound_the_decision():
    """A control the decision did not rest on cannot shorten it."""

    unrelated_early = _pass("UNREQUIRED", FIXED_NOW + timedelta(minutes=1))
    required_late = _pass("A", FIXED_NOW + timedelta(hours=2))

    horizon = freshness_horizon(("A",), (required_late, unrelated_early))

    assert horizon == FIXED_NOW + timedelta(hours=2)


def test_a_decision_never_outlives_the_freshness_that_justified_it():
    """The freshness cap at the ruler that applies it.

    Driven at ``ReferenceDecisionAuthority`` rather than through ``approved_envelope``,
    because ``ControlResultInput`` carries no ``valid_until``: control results created
    through the evaluation seam are unbounded, so the reference flow supplies no freshness
    horizon and this cap is invisible from there. Asserting it end to end would have meant
    changing a public request schema to manufacture a test condition. Stating the limit is
    better than hiding it — see the companion test that pins the unbounded case.
    """

    from risk_authority.services.decision_authority import ReferenceDecisionAuthority

    app = build_application()
    evaluation, decision, _envelope = approved_envelope(app)
    stale_soon = FIXED_NOW + timedelta(minutes=3)

    capped = ReferenceDecisionAuthority().issue_decision(
        decision_id="risk_dec_fresh",
        case=app.cases.get(TENANT, "rdc_1"),
        evaluation=evaluation,
        grant=build_grant(),
        requested_scope=FINANCE_SCOPE,
        evidence_snapshot_digest="",
        model_digest="",
        now=FIXED_NOW,
        prerequisite_horizons={"control_freshness": stale_soon},
    )

    assert capped.expires_at == stale_soon, (
        f"decision expires {capped.expires_at.isoformat()}, past the freshness horizon "
        f"{stale_soon.isoformat()}")


def test_the_application_wires_the_control_horizon_into_the_decision():
    """The wiring, not just the cap logic — and it needs the repository to reach.

    ``ControlResultInput`` carries no ``valid_until``, so no public request can create a
    bounded control result and the wiring in ``issue_decision`` is unreachable from the
    normal flow. Seeding the persisted control state directly is what makes it testable:
    that state is exactly what the application re-derives its authoritative evaluation
    from, so this exercises the real path rather than a stub.

    Without this, dropping the control bound from the application is a mutation the suite
    survives — which is how it was found.
    """

    from risk_authority.api import (
        ControlResultInput,
        CreateCaseRequest,
        DecisionRequest,
        EvaluateRequest,
    )

    horizon = FIXED_NOW + timedelta(minutes=7)
    app = build_application()
    case_id = "rdc_wired"

    # Drive the real state machine only as far as AUTHORITY_REVIEW, which is the one state
    # ``issue_decision`` may be reached from.
    app.create_case(CreateCaseRequest(
        tenant_id=TENANT, case_id=case_id, subject_id=ACTOR, model_id=MODEL,
        purpose="CUSTOMER_REFUND_REVIEW", domain="FINANCE", jurisdictions=("US",),
        tools=("crm.read", "refund.prepare"), autonomy_level=2,
        data_classes=("CUSTOMER_PII", "TRANSACTION_DATA"),
        workflow_ir_id="finance-ai-risk", inherent_risk=RiskClass.HIGH,
        residual_risk=RiskClass.MEDIUM))
    evaluation = app.evaluate(TENANT, case_id, EvaluateRequest(control_results=(
        ControlResultInput("MODEL_PROVENANCE_VALID", "PASS"),
        ControlResultInput("HUMAN_OVERSIGHT_VALID", "PASS"),
        ControlResultInput("BIAS_EVALUATION_CURRENT", "PASS"))))

    bounded = tuple(
        replace(r, valid_until=horizon) for r in app.controls.get(TENANT, case_id))
    assert bounded, "fixture assumption: evaluation persisted control results"
    app.controls.put(TENANT, case_id, bounded)

    decision = app.issue_decision(
        TENANT, case_id, evaluation,
        DecisionRequest(principal_id=PRINCIPAL, requested_scope=FINANCE_SCOPE))

    assert decision.expires_at == horizon, (
        f"decision expires {decision.expires_at.isoformat()}; the control horizon "
        f"{horizon.isoformat()} did not reach the authority")


def test_the_reference_flow_is_unaffected_because_its_controls_are_unbounded():
    """Why no existing decision moved: seam-created control results carry no bound.

    This is the control that makes the previous test's limitation explicit rather than
    leaving a reader to assume the cap fires everywhere.
    """

    app = build_application()
    _evaluation, decision, _envelope = approved_envelope(app)

    stored = app.controls.get(TENANT, "rdc_1")
    assert stored, "fixture assumption: the case has persisted control results"
    assert all(r.valid_until is None for r in stored)
    assert freshness_horizon((r.control_id for r in stored), stored) is None
    assert decision.expires_at == FIXED_NOW + timedelta(hours=1)
