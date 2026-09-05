"""I8.1 – I8.15 — the OD-7 / OD-8 / OD-9 / OD-10 enforcement and mutation obligations.

Each obligation below is numbered as I8 states it in
``docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md``. Until this module existed every one
of them was prospective: the amendment was ratified and unimplemented, and the only
guards touching it were the documentation-consistency checks in
``test_documentation_consistency.py``, which read what the documents say and prove
nothing about what any selector does. These are the behavioural guards.

**What this module deliberately does not contain: a domain evaluator.** OD-7 part 2
ratifies an injected protocol and nothing more, so every provider here is
``s1_specification_mirror.StubDomainEvaluationProvider`` — a test double that returns
whatever a test asked for. No business-domain logic exists anywhere in this package,
and a guard that had to supply some would be evidence the boundary was drawn wrong.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
from datetime import timedelta

import pydantic
import pytest

import s1_specification_mirror as spec
import ugence_agentic_proposer as ap
from ugence_agentic_proposer import contracts as c
from ugence_agentic_proposer import verification as v

SRC = pathlib.Path(ap.__file__).resolve().parent
FIXED_INSTANT = spec.FIXED_INSTANT
LATER = FIXED_INSTANT + timedelta(days=365)

SATISFIED = ap.DomainEvaluationOutcome.SATISFIED
NOT_SATISFIED = ap.DomainEvaluationOutcome.NOT_SATISFIED
INCONCLUSIVE = ap.DomainEvaluationOutcome.INCONCLUSIVE
COMPLETE = ap.DomainCheckCompletion.COMPLETE
NOT_EVALUATED = ap.DomainCheckCompletion.NOT_EVALUATED


# --------------------------------------------------------------------------- #
# Fixtures — one lawful world, and candidates varied inside it
# --------------------------------------------------------------------------- #


def _world():
    identity = ap.AgentIdentityRef(
        schema_version="1.0", tenant_id="tenant-1", created_at=FIXED_INSTANT,
        agent_id="agent-1", agent_version="1.0.0",
        lifecycle_state=ap.AgentLifecycleState.ACTIVE,
        bound_role_contract_id="role-1", owner_role_ref="role-owner")
    role = ap.CognitiveRoleContract(
        schema_version="1.0", tenant_id="tenant-1", created_at=FIXED_INSTANT,
        role_contract_id="role-1", primary_function="reconcile invoices",
        permitted_tool_scopes=["invoice.read"],
        permitted_candidate_dispositions=[ap.CandidateDisposition.RECOMMEND_WITHHOLD],
        permitted_review_actions=[ap.ReviewAction.ROUTE_APPROVAL_BUNDLE],
        escalation_role_ref="role-2", activation_status=ap.RoleActivationStatus.ACTIVE,
        strategy_policy_ref=spec.STRATEGY_POLICY_REF,
        constitution_ref=spec.CONSTITUTION_REF)
    mandate = ap.WorkMandate(
        schema_version="1.0", tenant_id="tenant-1", created_at=FIXED_INSTANT,
        mandate_id="mandate-1", case_ref="case-1", assigned_role_contract_id="role-1",
        purpose="reconcile invoices for Q1", allowed_source_scopes=["ledger.read"],
        expires_at=LATER)
    context = ap.BoundedContextEnvelope(
        schema_version="1.0", tenant_id="tenant-1", created_at=FIXED_INSTANT,
        context_id="context-1", mandate_id="mandate-1",
        allowed_record_refs=["record-1"], excluded_data_classes=[],
        context_hash=spec.PLACEHOLDER_DIGEST, expires_at=LATER)
    observation = ap.ToolObservation(
        schema_version="1.0", tenant_id="tenant-1", created_at=FIXED_INSTANT,
        observation_id="obs-1", case_ref="case-1", tool_name="invoice.read",
        operation_class=ap.ToolOperationClass.READ_ONLY, source_ref="record-1",
        observed_at=FIXED_INSTANT, content_hash=spec.PLACEHOLDER_DIGEST,
        normalized_fields={})
    return dict(identity=identity, role=role, mandate=mandate, context=context,
                observation=observation)


@pytest.fixture(scope="module")
def world():
    return _world()


def _candidate(candidate_id, *, eligible=True, outcome=SATISFIED, refs=("obs-1",)):
    """One ``CandidateAdvisory``, varied only in the two fields the selector reads."""
    fields = {
        **spec.complete_candidate(candidate_id),
        "is_eligible": eligible,
        "observation_refs": list(refs),
        "domain_check_completion": COMPLETE if outcome is not None else NOT_EVALUATED,
        "domain_evaluation_outcome": outcome,
    }
    return ap.CandidateAdvisory(**fields)


def _set(candidates, *, selected=None, profile=True):
    """An ``AdvisoryCandidateSet`` built through the ratified builder, so the policy
    identity is stamped by the package rather than supplied by this test."""
    any_complete = any(x.domain_check_completion is COMPLETE for x in candidates)
    return ap.build_advisory_candidate_set(
        candidate_set_id="set-1", tenant_id="tenant-1", case_ref="case-1",
        created_at=FIXED_INSTANT, candidates=tuple(candidates),
        selected_candidate_id=selected,
        domain_evaluation_profile_id=spec.PROFILE_ID if (any_complete and profile) else None,
        domain_evaluation_profile_version=(
            spec.PROFILE_VERSION if (any_complete and profile) else None))


def _advisory(world, candidate_set, *, provider=None, destination="role-approver",
              strategy_policy_resolver=None, declared_strategy=None):
    """``declared_strategy`` defaults to the member this advisory's own shape yields —
    no parent here, so it turns on the candidate count (`S2B-R2-Q1=A`). A test that
    wants a mismatch passes one explicitly."""
    if declared_strategy is None:
        declared_strategy = (
            ap.ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED
            if len(candidate_set.candidates) == 1
            else ap.ReasoningStrategy.MULTI_CANDIDATE_UNREVISED)
    return ap.build_proposer_advisory(
        tenant_id="tenant-1", case_ref="case-1", created_at=FIXED_INSTANT,
        identity=world["identity"], role=world["role"], mandate=world["mandate"],
        context=world["context"], observations=[world["observation"]],
        candidate_set=candidate_set, parent_advisory_digest=None,
        claim_summaries=[], observation_refs=[], uncertainties=[], expires_at=LATER,
        provider=provider or spec.StubDomainEvaluationProvider(),
        expected_profile_id=spec.PROFILE_ID,
        expected_profile_version=spec.PROFILE_VERSION,
        requested_review_destination_role_ref=(
            destination if candidate_set.selected_candidate_id is not None else None),
        strategy_policy_resolver=(
            strategy_policy_resolver or spec.StubStrategyPolicyResolver()),
        constitution_resolution=spec.StubConstitutionResolution(),
        declared_strategy=declared_strategy)


# --------------------------------------------------------------------------- #
# I8.1 — the completion/outcome coupling, both directions, mutation-tested
# --------------------------------------------------------------------------- #


def test_i8_1_complete_requires_an_outcome():
    with pytest.raises(pydantic.ValidationError):
        ap.CandidateAdvisory(**{**spec.complete_candidate(),
                                "domain_check_completion": COMPLETE,
                                "domain_evaluation_outcome": None})


def test_i8_1_an_outcome_requires_complete():
    with pytest.raises(pydantic.ValidationError):
        ap.CandidateAdvisory(**{**spec.complete_candidate(),
                                "domain_check_completion": NOT_EVALUATED,
                                "domain_evaluation_outcome": SATISFIED})


@pytest.mark.parametrize("outcome", [SATISFIED, NOT_SATISFIED, INCONCLUSIVE])
def test_i8_1_every_outcome_is_lawful_alongside_complete(outcome):
    """``INCONCLUSIVE`` in particular: the coupling must not exclude it. ``COMPLETE``
    is a claim about process — every check ran to a recorded conclusion — not a claim
    that those conclusions converge. A coupling that refused ``INCONCLUSIVE`` would
    reintroduce the ``DomainCheckCompletion`` overload OD-7's rejected-alternatives
    list forbids, through the coupling rule rather than the field's own type."""
    candidate = ap.CandidateAdvisory(**{**spec.complete_candidate(),
                                        "domain_check_completion": COMPLETE,
                                        "domain_evaluation_outcome": outcome})
    assert candidate.domain_evaluation_outcome is outcome


def test_i8_1_mutation_a_validator_that_names_both_fields_and_enforces_neither():
    """The mutation I8.1 names. A twin declaring both fields, and a validator that
    reads both and returns without deciding anything, accepts exactly what
    ``CandidateAdvisory`` rejects — so the rejection is the coupling's, not the
    field types'."""
    from typing import Optional

    class _CandidateWithAnInertValidator(pydantic.BaseModel):
        model_config = c._MODEL_CONFIG
        candidate_id: c.Identifier
        domain_check_completion: ap.DomainCheckCompletion = NOT_EVALUATED
        domain_evaluation_outcome: Optional[ap.DomainEvaluationOutcome] = None

        @pydantic.model_validator(mode="after")
        def _names_both_and_enforces_neither(self):
            _ = (self.domain_check_completion, self.domain_evaluation_outcome)
            return self

    twin = _CandidateWithAnInertValidator(
        candidate_id="cand-1", domain_check_completion=COMPLETE)
    assert twin.domain_evaluation_outcome is None
    with pytest.raises(pydantic.ValidationError):
        ap.CandidateAdvisory(**{**spec.complete_candidate(),
                                "domain_check_completion": COMPLETE})


# --------------------------------------------------------------------------- #
# I8.2 — the two AdvisoryCandidateSet couplings, both directions, bearer-scoped
# --------------------------------------------------------------------------- #


def test_i8_2_a_complete_candidate_requires_the_profile_pair():
    with pytest.raises(pydantic.ValidationError):
        _set([_candidate("cand-1")], selected="cand-1", profile=False)


def test_i8_2_no_complete_candidate_forbids_the_profile_pair():
    unevaluated = _candidate("cand-1", outcome=None)
    with pytest.raises(pydantic.ValidationError):
        ap.AdvisoryCandidateSet(
            schema_version="1.0", tenant_id="tenant-1", created_at=FIXED_INSTANT,
            candidate_set_id="set-1", case_ref="case-1", candidates=(unevaluated,),
            domain_evaluation_profile_id=spec.PROFILE_ID,
            domain_evaluation_profile_version=spec.PROFILE_VERSION,
            selected_candidate_id=None, selection_reason_codes=[])


def test_i8_2_a_selection_requires_the_policy_pair():
    built = _set([_candidate("cand-1")], selected="cand-1")
    fields = {name: getattr(built, name) for name in ap.AdvisoryCandidateSet.model_fields}
    fields["selection_policy_id"] = None
    with pytest.raises(pydantic.ValidationError):
        ap.AdvisoryCandidateSet.model_validate(fields)


def test_i8_2_no_selection_forbids_the_policy_pair():
    unevaluated = _candidate("cand-1", outcome=None)
    with pytest.raises(pydantic.ValidationError):
        ap.AdvisoryCandidateSet(
            schema_version="1.0", tenant_id="tenant-1", created_at=FIXED_INSTANT,
            candidate_set_id="set-1", case_ref="case-1", candidates=(unevaluated,),
            selected_candidate_id=None,
            selection_policy_id=c.SELECTION_POLICY_ID,
            selection_policy_version=c.SELECTION_POLICY_VERSION,
            selection_reason_codes=[])


def test_i8_2_the_couplings_are_scoped_to_their_bearers_and_not_to_a_field_name():
    """OD-3's lesson, restated for four new names. ``AdvisoryCandidateSet`` and
    ``ProposerAdvisory`` bear these fields; nothing else declares them, so no coupling
    can be applied by name alone to a contract that never agreed to it."""
    bearers = {"AdvisoryCandidateSet", "ProposerAdvisory"}
    for name, model in spec.representative_shapes().items():
        declared = set(model.model_fields) & set(v.MIRRORED_EVALUATION_FIELDS)
        if name in bearers:
            assert declared == set(v.MIRRORED_EVALUATION_FIELDS), name
        else:
            assert declared == set(), f"{name} declares a mirrored field it does not bear"
    assert "domain_evaluation_outcome" in ap.CandidateAdvisory.model_fields
    assert "domain_evaluation_outcome" not in ap.AdvisoryCandidateSet.model_fields


# --------------------------------------------------------------------------- #
# I8.3 — R-1b's two new correspondence clauses, replayed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("field", v.MIRRORED_EVALUATION_FIELDS)
def test_i8_3_a_mirrored_field_that_diverges_from_the_set_fails_replay(world, field):
    candidate_set = _set([_candidate("cand-1")], selected="cand-1")
    advisory = _advisory(world, candidate_set)
    assert ap.verify_advisory_selection(
        advisory=advisory, candidate_set=candidate_set, role=world["role"],
        context=world["context"], observations=[world["observation"]]) is True

    # ``model_copy(update=...)`` never re-validates, which is the only way to produce a
    # divergence: construction couples the two.
    tampered = advisory.model_copy(update={field: "tampered.value"})
    assert ap.verify_advisory_selection(
        advisory=tampered, candidate_set=candidate_set, role=world["role"],
        context=world["context"], observations=[world["observation"]]) is False


def test_i8_3_the_mirrored_values_are_inside_p_unsigned(world):
    """The reason the fields are mirrored at all (OD-7 part 5): recording them only on
    ``ProposerProcessRecord`` was rejected because that record sits outside
    ``P_unsigned`` and can change without changing advisory identity."""
    candidate_set = _set([_candidate("cand-1")], selected="cand-1")
    advisory = _advisory(world, candidate_set)
    projection = advisory.model_dump(mode="json", exclude={"advisory_digest"})
    for field in v.MIRRORED_EVALUATION_FIELDS:
        assert projection[field] is not None
    assert ap.verify_advisory_identity(advisory=advisory) is True
    assert "domain_evaluation_outcome" in projection["candidates"][0]


# --------------------------------------------------------------------------- #
# I8.4 — verify_domain_evaluation
# --------------------------------------------------------------------------- #


def _replay(world, candidate_set, provider, **overrides):
    kwargs = dict(
        provider=provider, candidate_set=candidate_set, mandate=world["mandate"],
        context=world["context"], observations=[world["observation"]],
        expected_profile_id=spec.PROFILE_ID,
        expected_profile_version=spec.PROFILE_VERSION)
    kwargs.update(overrides)
    return ap.verify_domain_evaluation(**kwargs)


def test_i8_4_replay_passes_on_the_lawful_case(world):
    candidate_set = _set([_candidate("cand-1")], selected="cand-1")
    assert _replay(world, candidate_set,
                   spec.StubDomainEvaluationProvider()) is True


@pytest.mark.parametrize("override", [
    {"expected_profile_id": "some.other.profile"},
    {"expected_profile_version": "2027.9"},
])
def test_i8_4_a_stored_profile_that_diverges_from_the_expected_one_fails(world, override):
    """The expected profile is supplied from **outside** the advisory under test, so a
    provider echoing back whatever a tampered set records cannot satisfy this."""
    candidate_set = _set([_candidate("cand-1")], selected="cand-1")
    assert _replay(world, candidate_set, spec.StubDomainEvaluationProvider(),
                   **override) is False


def test_i8_4_a_provider_that_does_not_reproduce_the_stored_outcome_fails(world):
    candidate_set = _set([_candidate("cand-1")], selected="cand-1")
    drifted = spec.StubDomainEvaluationProvider(default=NOT_SATISFIED)
    assert _replay(world, candidate_set, drifted) is False


def test_i8_4_a_provider_that_echoes_the_wrong_candidate_id_fails(world):
    candidate_set = _set([_candidate("cand-1")], selected="cand-1")
    confused = spec.StubDomainEvaluationProvider(echo_candidate_id="cand-other")
    assert _replay(world, candidate_set, confused) is False


def test_i8_4_a_provider_that_echoes_a_stale_profile_fails(world):
    candidate_set = _set([_candidate("cand-1")], selected="cand-1")
    stale = spec.StubDomainEvaluationProvider(echo_profile_version="2025.1")
    assert _replay(world, candidate_set, stale) is False


def test_i8_4_replay_does_not_establish_the_original_evaluations_correctness(world):
    """`[G]` The disclosed ceiling, stated explicitly rather than left to a docstring.

    A provider whose behaviour changed under an unchanged version label reproduces
    whatever it now believes. Replay agrees with it, and that agreement is **not**
    evidence the original evaluation was correct — it is evidence that re-running
    under the same label produces the same answer. A non-deterministic provider is the
    same case. The provider remains the sole authority on domain substance, and no
    check in this package can or does contradict it.
    """
    revised = spec.StubDomainEvaluationProvider(default=NOT_SATISFIED)
    # A set whose stored outcome is whatever the provider said at the time.
    stored_under_the_revised_rules = _set(
        [_candidate("cand-1", outcome=NOT_SATISFIED)], selected=None)
    assert _replay(world, stored_under_the_revised_rules, revised) is True
    # The same label, an unchanged version, and a different answer than the original
    # run would have given. Replay cannot see that, and does not claim to.
    assert stored_under_the_revised_rules.domain_evaluation_profile_version == (
        spec.PROFILE_VERSION)


# --------------------------------------------------------------------------- #
# I8.5 — verify_deterministic_selection
# --------------------------------------------------------------------------- #


def test_i8_5_a_selector_the_policy_did_not_produce_fails_replay(world):
    """Including one that satisfies R-1b's structural correspondence: the advisory and
    the set agree with **each other**, and neither is the ratified selector's output."""
    two = (_candidate("cand-1"), _candidate("cand-2"))
    lawful = _set(two, selected=None)
    forged = lawful.model_copy(update={
        "selected_candidate_id": "cand-1",
        "selection_policy_id": c.SELECTION_POLICY_ID,
        "selection_policy_version": c.SELECTION_POLICY_VERSION})
    assert ap.verify_deterministic_selection(candidate_set=forged) is False


def test_i8_5_a_foreign_policy_label_fails_even_when_the_recomputation_matches():
    built = _set([_candidate("cand-1")], selected="cand-1")
    mislabelled = built.model_copy(update={"selection_policy_id": "someone.elses"})
    assert mislabelled.selected_candidate_id == "cand-1"
    assert ap.verify_deterministic_selection(candidate_set=mislabelled) is False


def test_i8_5_replay_passes_on_the_ratified_selection():
    assert ap.verify_deterministic_selection(
        candidate_set=_set([_candidate("cand-1")], selected="cand-1")) is True


def test_i8_5_replay_passes_on_a_lawful_no_selection():
    two = (_candidate("cand-1"), _candidate("cand-2"))
    assert ap.verify_deterministic_selection(
        candidate_set=_set(two, selected=None)) is True


def test_i8_5_there_is_no_selector_policy_registry():
    """`[G]` The third disclosed ceiling, asserted rather than described. The check is
    a comparison against this package's own constants; nothing maps a policy identity
    to its ratified definition, so across installations or versions this degrades to a
    label comparison and is sound only within one installation at one version."""
    source = inspect.getsource(ap.verify_deterministic_selection)
    assert "SELECTION_POLICY_ID" in source
    assert c.SELECTION_POLICY_ID == "agentic_proposer.deterministic_selection"
    assert c.SELECTION_POLICY_VERSION == "v1"


# --------------------------------------------------------------------------- #
# I8.6 — one test per row of the fail-closed table (OD-7 part 7)
# --------------------------------------------------------------------------- #


def _row(*, evidence=True, evaluator=True, verified=True, candidates=()):
    return v.classify_fail_closed_row(
        evidence_resolved=evidence, evaluator_available=evaluator,
        verification_passed=verified, candidates=candidates)


def test_i8_6_row_1_missing_evidence_or_an_unavailable_evaluator_needs_evidence():
    assert _row(evidence=False, candidates=(_candidate("cand-1"),)) == (1, None)
    assert _row(evaluator=False, candidates=(_candidate("cand-1"),)) == (1, None)
    assert v.FAIL_CLOSED_ROWS[1] == "NEED_EVIDENCE"


def test_i8_6_row_2_a_verification_failure_refuses_construction(world):
    assert _row(verified=False, candidates=(_candidate("cand-1"),)) == (2, None)
    assert v.FAIL_CLOSED_ROWS[2] is None, (
        "row 2 refuses construction; it records no terminal outcome")
    candidate_set = _set([_candidate("cand-1")], selected="cand-1")
    with pytest.raises(ap.DomainEvaluationProviderError):
        _advisory(world, candidate_set,
                  provider=spec.StubDomainEvaluationProvider(default=NOT_SATISFIED))


def test_i8_6_row_3_exactly_one_qualifying_candidate_is_selected():
    assert _row(candidates=(_candidate("cand-1"),)) == (3, "cand-1")
    assert v.FAIL_CLOSED_ROWS[3] == "PROPOSAL"


def test_i8_6_row_4_more_than_one_qualifying_candidate_abstains():
    two = (_candidate("cand-1"), _candidate("cand-2"))
    assert _row(candidates=two) == (4, None)
    assert v.FAIL_CLOSED_ROWS[4] == "ABSTAIN"


def test_i8_6_row_5_an_empty_pool_with_an_inconclusive_candidate_abstains():
    candidates = (_candidate("cand-1", outcome=INCONCLUSIVE),)
    assert _row(candidates=candidates) == (5, None)
    assert v.FAIL_CLOSED_ROWS[5] == "ABSTAIN"


def test_i8_6_row_6_an_empty_pool_with_no_inconclusive_candidate_abstains():
    candidates = (_candidate("cand-1", outcome=NOT_SATISFIED),
                  _candidate("cand-2", eligible=False))
    assert _row(candidates=candidates) == (6, None)
    assert v.FAIL_CLOSED_ROWS[6] == "ABSTAIN"


# --------------------------------------------------------------------------- #
# I8.7 — the same-change-set discipline
# --------------------------------------------------------------------------- #


def test_i8_7_c7_and_c9_are_removed_only_alongside_their_complete_replacement():
    """I8.7 states in terms that this is a **review-time obligation** and that no
    single runtime test can enforce it alone: a test cannot see a commit boundary.
    What it can see is the pair — that neither ceiling's refusal remains, and that
    every replacement the amendment names is present at the same moment. A change
    removing one ceiling without the replacement surface fails here; a change
    splitting the work across two commits does not, and that is what the review
    obligation is for.
    """
    source = (SRC / "contracts.py").read_text(encoding="utf-8")
    assert "DomainCheckCompletion.COMPLETE is unconstructible in S1" not in source, (
        "C7's refusal is still present")
    assert "must be None in S1 (C9" not in source, "C9's refusal is still present"

    for field, model in (
            ("domain_evaluation_outcome", ap.CandidateAdvisory),
            ("domain_evaluation_profile_id", ap.AdvisoryCandidateSet),
            ("domain_evaluation_profile_version", ap.AdvisoryCandidateSet),
            ("selection_policy_id", ap.AdvisoryCandidateSet),
            ("selection_policy_version", ap.AdvisoryCandidateSet),
            ("domain_evaluation_profile_id", ap.ProposerAdvisory),
            ("selection_policy_version", ap.ProposerAdvisory)):
        assert field in model.model_fields, (field, model.__name__)

    assert {m.value for m in ap.DomainEvaluationOutcome} == {
        "SATISFIED", "NOT_SATISFIED", "INCONCLUSIVE"}
    assert hasattr(ap.DomainEvaluationProvider, "evaluate")
    assert issubclass(ap.DomainEvaluationProviderError, ValueError)
    assert callable(ap.verify_domain_evaluation)
    assert callable(ap.verify_deterministic_selection)
    assert "domain_evaluation_satisfied" in inspect.getsource(ap.evaluate_readiness)


def test_i8_7_the_private_payload_mirror_carries_the_four_fields():
    """G2's equivalence obligation, which part 8's handover depends on: a mirrored
    field missing from ``identity.py``'s private ``_UnsignedAdvisoryPayload`` would sit
    on the advisory and outside ``P_unsigned``, and the two models would drift apart at
    exactly the point identity is computed."""
    from ugence_agentic_proposer import identity as identity_module

    payload = identity_module._unsigned_advisory_payload_model()
    assert set(payload.model_fields) == (
        set(ap.ProposerAdvisory.model_fields) - {"advisory_digest"})
    for field in v.MIRRORED_EVALUATION_FIELDS:
        assert field in payload.model_fields


# --------------------------------------------------------------------------- #
# I8.8 — DomainEvaluationOutcome collides with no reserved spelling
# --------------------------------------------------------------------------- #


def test_i8_8_no_outcome_member_is_a_reserved_authority_term():
    values = {m.value for m in ap.DomainEvaluationOutcome}
    assert values & ap.RESERVED_AUTHORITY_VOCABULARY == set()


def test_i8_8_inconclusive_is_not_indeterminate():
    """D4 reserves ``INDETERMINATE`` to two authority-adjacent positions and ratifies
    it in exactly one non-authority position. A third was not ratified, so OD-7 uses a
    different spelling — and the two must never converge."""
    values = {m.value for m in ap.DomainEvaluationOutcome}
    assert "INDETERMINATE" not in values
    assert ap.SemanticAuditorFindingStatus.INDETERMINATE.value == "INDETERMINATE"
    assert values & {m.value for m in ap.SemanticAuditorFindingStatus} == set()
    assert ap.DomainEvaluationOutcome.INCONCLUSIVE.value == "INCONCLUSIVE"


# --------------------------------------------------------------------------- #
# I8.9 — the three things OD-7 refuses to let collapse
# --------------------------------------------------------------------------- #


class _Boom(RuntimeError):
    """A provider's own exception type, which no caller of this package should have to
    know about."""


def test_i8_9_a_provider_raising_during_replay_returns_false_not_an_exception(world):
    candidate_set = _set([_candidate("cand-1")], selected="cand-1")
    exploding = spec.StubDomainEvaluationProvider(raises=_Boom("evaluator down"))
    assert _replay(world, candidate_set, exploding) is False


def test_i8_9_a_provider_raising_during_a_build_surfaces_as_the_named_error(world):
    exploding = spec.StubDomainEvaluationProvider(raises=_Boom("evaluator down"))
    with pytest.raises(ap.DomainEvaluationProviderError) as excinfo:
        ap.build_candidate_advisory(
            candidate_id="cand-1", identity=world["identity"], role=world["role"],
            mandate=world["mandate"], context=world["context"],
            observations=[world["observation"]],
            disposition=ap.CandidateDisposition.RECOMMEND_WITHHOLD,
            requested_review_action=ap.ReviewAction.ROUTE_APPROVAL_BUNDLE,
            observation_refs=["obs-1"], claim_refs=[], assumptions=[],
            uncertainties=[], evaluated_at=FIXED_INSTANT, provider=exploding,
            profile_id=spec.PROFILE_ID, profile_version=spec.PROFILE_VERSION)
    assert not isinstance(excinfo.value, _Boom)
    assert isinstance(excinfo.value.__cause__, _Boom)


def test_i8_9_missing_evidence_warns_does_not_raise_and_never_calls_the_provider(world):
    """The third of the three. It is not an evaluation failure and must not be reported
    as one: ``_resolve_references`` — E2's own algorithm — warns naming the failing
    reference, the provider is not invoked at all, and the candidate is left
    unevaluated so nothing can select it. Routing the run to ``NEED_EVIDENCE`` is the
    caller's orchestration decision, not a return value."""
    provider = spec.StubDomainEvaluationProvider()
    with pytest.warns(UserWarning, match="dangling"):
        candidate = ap.build_candidate_advisory(
            candidate_id="cand-1", identity=world["identity"], role=world["role"],
            mandate=world["mandate"], context=world["context"],
            observations=[world["observation"]],
            disposition=ap.CandidateDisposition.RECOMMEND_WITHHOLD,
            requested_review_action=ap.ReviewAction.ROUTE_APPROVAL_BUNDLE,
            observation_refs=["obs-missing"], claim_refs=[], assumptions=[],
            uncertainties=[], evaluated_at=FIXED_INSTANT, provider=provider,
            profile_id=spec.PROFILE_ID, profile_version=spec.PROFILE_VERSION)
    assert provider.calls == [], "the provider was invoked despite missing evidence"
    assert candidate.domain_check_completion is NOT_EVALUATED
    assert candidate.domain_evaluation_outcome is None

    # Neither replay function reports a bare False for it, because it is neither
    # function's concern: nothing is COMPLETE, so there is nothing to replay.
    candidate_set = _set([candidate], selected=None)
    assert _replay(world, candidate_set, provider) is True
    assert ap.verify_deterministic_selection(candidate_set=candidate_set) is True
    # And the run is directed to NEED_EVIDENCE by the table, not by a return value.
    assert v.classify_fail_closed_row(
        evidence_resolved=False, evaluator_available=True, verification_passed=True,
        candidates=candidate_set.candidates) == (1, None)


# --------------------------------------------------------------------------- #
# I8.10 — Equation 2's seventh term, exercised directly
# --------------------------------------------------------------------------- #


def _readiness(world, candidate):
    return ap.evaluate_readiness(
        candidate=candidate, identity=world["identity"], role=world["role"],
        mandate=world["mandate"], context=world["context"])


@pytest.mark.parametrize("outcome", [NOT_SATISFIED, INCONCLUSIVE])
def test_i8_10_a_completed_but_unsatisfied_candidate_is_not_ready(world, outcome):
    """Exercised against ``evaluate_readiness`` as an **exported function**, not only
    through a builder: the function has no caller in ``src/``, so "invoked only after
    selection" is a convention this package cannot enforce against a consumer."""
    assert _readiness(world, _candidate("cand-1", outcome=outcome)) is False


def test_i8_10_a_satisfied_candidate_is_ready(world):
    assert _readiness(world, _candidate("cand-1", outcome=SATISFIED)) is True


def test_i8_10_mutation_a_six_term_equation_omitting_the_new_term_would_pass(world):
    """The mutation I8.10 names. A six-term equation — the pre-OD-7 form — returns
    ``True`` for a candidate whose evaluation ran and **failed**, which is R-2's
    condition for ``terminal_outcome=PROPOSAL``. That is the exposure C7 closed
    structurally and the seventh term closes now."""
    candidate = _candidate("cand-1", outcome=NOT_SATISFIED)
    six_term = all((
        candidate.is_eligible is True,
        True,
        True,
        candidate.uncertainties is not None,
        world["identity"].bound_role_contract_id == world["role"].role_contract_id
        == world["mandate"].assigned_role_contract_id
        and world["context"].mandate_id == world["mandate"].mandate_id,
        candidate.domain_check_completion is COMPLETE,
    ))
    assert six_term is True, "precondition: the six-term form accepts this candidate"
    assert _readiness(world, candidate) is False, (
        "the seventh term is what refuses it; without it the equation is one term "
        "compensating for a substantive result it does not carry")


def test_i8_10_this_is_what_replaced_c7s_structural_closure(world):
    """Stated as an assertion rather than left in prose: C7 forced Equation 2 ``False``
    for every constructible candidate. It is gone, ``COMPLETE`` is constructible, and
    what keeps an unsatisfied candidate out of ``PROPOSAL`` is the term."""
    completed_and_failed = _candidate("cand-1", outcome=NOT_SATISFIED)
    assert completed_and_failed.domain_check_completion is COMPLETE
    assert _readiness(world, completed_and_failed) is False


@pytest.mark.parametrize("outcome", [NOT_SATISFIED, INCONCLUSIVE])
def test_i8_10_proposal_is_unreachable_for_an_unsatisfied_candidate(world, outcome):
    """I8.10's companion assertion, against the **reimplemented** V13.

    A test written against today's-in-S1 blanket refusal of ``PROPOSAL`` would pass for
    the wrong reason and must not be mistaken for coverage of this obligation. V13 no
    longer refuses ``PROPOSAL`` outright — ``test_i8_12_...`` builds a lawful one — so
    this asserts the path: an unsatisfied candidate is not in the qualifying pool,
    nothing selects it, and a record claiming ``PROPOSAL`` with no selection is refused.
    """
    candidate_set = _set([_candidate("cand-1", outcome=outcome)], selected=None)
    assert candidate_set.selected_candidate_id is None
    # Under rider `R1` the record derives its digest reference and its declaration
    # from a real advisory rather than taking either as a parameter, so this builds
    # the advisory the record would be about. The provider is told to reproduce the
    # candidate's own stored outcome, which is what OD-7 part 5's replay requires.
    advisory = _advisory(
        world, candidate_set,
        provider=spec.StubDomainEvaluationProvider(default=outcome))
    with pytest.raises(pydantic.ValidationError):
        ap.build_proposer_process_record(
            process_record_id="rec-1", tenant_id="tenant-1", case_ref="case-1",
            created_at=FIXED_INSTANT, advisory=advisory,
            state_transitions=[], tool_invocations=[], candidate_ids=["cand-1"],
            selected_candidate_id=candidate_set.selected_candidate_id,
            terminal_outcome=ap.TerminalOutcome.PROPOSAL,
            started_at=FIXED_INSTANT, completed_at=FIXED_INSTANT)


def test_i8_10_v13_no_longer_refuses_proposal_outright(world):
    """The other half, without which the assertion above would be vacuous: a lawful
    ``PROPOSAL`` record **is** constructible now, so the refusal above is R-2's
    condition biting rather than a blanket ban."""
    candidate_set = _set([_candidate("cand-1")], selected="cand-1")
    advisory = _advisory(world, candidate_set)
    record = ap.build_proposer_process_record(
        process_record_id="rec-1", tenant_id="tenant-1", case_ref="case-1",
        created_at=FIXED_INSTANT, advisory=advisory,
        state_transitions=[], tool_invocations=[], candidate_ids=["cand-1"],
        selected_candidate_id="cand-1",
        terminal_outcome=ap.TerminalOutcome.PROPOSAL,
        started_at=FIXED_INSTANT, completed_at=FIXED_INSTANT)
    assert record.terminal_outcome is ap.TerminalOutcome.PROPOSAL


def test_i8_10_build_proposer_advisory_recomputes_readiness_rather_than_assuming_it():
    """R-2 requires readiness **recomputed at construction**, and B3 names
    ``build_proposer_advisory`` as where V13 recomputes it.

    The case that separates recomputation from assumption: a candidate that is
    eligible, ``COMPLETE`` and ``SATISFIED`` — so selection-policy v1 selects it — and
    that Equation 2 nonetheless refuses, because a ``RECOMMEND_MATCHED_FOR_APPROVAL``
    candidate with no ``observation_refs`` fails the ``ObservationRefsPresent`` term.
    A builder that assumed readiness from selection would carry it; this one refuses.
    """
    world = _world()
    permissive_role = world["role"].model_copy(update={
        "permitted_candidate_dispositions": [
            ap.CandidateDisposition.RECOMMEND_WITHHOLD,
            ap.CandidateDisposition.RECOMMEND_MATCHED_FOR_APPROVAL]})
    world["role"] = permissive_role

    matched = ap.build_candidate_advisory(
        candidate_id="cand-1", identity=world["identity"], role=permissive_role,
        mandate=world["mandate"], context=world["context"],
        observations=[world["observation"]],
        disposition=ap.CandidateDisposition.RECOMMEND_MATCHED_FOR_APPROVAL,
        requested_review_action=ap.ReviewAction.ROUTE_APPROVAL_BUNDLE,
        observation_refs=[], claim_refs=[], assumptions=[], uncertainties=[],
        evaluated_at=FIXED_INSTANT, provider=spec.StubDomainEvaluationProvider(),
        profile_id=spec.PROFILE_ID, profile_version=spec.PROFILE_VERSION)
    assert matched.is_eligible is True
    assert matched.domain_evaluation_outcome is SATISFIED
    assert _readiness(world, matched) is False

    selecting_set = _set([matched], selected="cand-1")
    assert selecting_set.selected_candidate_id == "cand-1", (
        "precondition: selection-policy v1 selects this candidate")
    with pytest.raises(ap.CrossContractViolationError):
        _advisory(world, selecting_set)


# --------------------------------------------------------------------------- #
# I8.11 — the cardinality pins, updated in this change set
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("contract,expected", [
    ("AdvisoryCandidateSet", 12), ("CandidateAdvisory", 11), ("ProposerAdvisory", 32)])
def test_i8_11_the_moved_cardinalities_agree_with_src(contract, expected):
    """The amendment's own arithmetic — 8 -> 12, 10 -> 11, 23 -> 27 — re-verified
    against ``src/`` rather than trusted, exactly as OD-4's cardinality claims were.
    These are existing guards that failed on the field additions; updating them was
    part of the change set, not a repair after it."""
    assert spec.CONTRACT_CARDINALITY[contract] == expected
    assert len(spec.representative_shapes()[contract].model_fields) == expected
    assert len(spec.FIELD_CLASSIFICATION[contract]) == expected


# --------------------------------------------------------------------------- #
# I8.12 — OD-8 selection-policy v1
# --------------------------------------------------------------------------- #


def test_i8_12_exactly_one_qualifier_selects_it():
    assert c.selection_policy_v1((_candidate("cand-1"),)) == "cand-1"


def test_i8_12_two_qualifiers_select_nothing():
    two = (_candidate("cand-1"), _candidate("cand-2"))
    assert c.selection_policy_v1(two) is None
    assert _row(candidates=two) == (4, None)
    assert v.FAIL_CLOSED_ROWS[4] == "ABSTAIN"


def test_i8_12_zero_qualifiers_select_nothing():
    assert c.selection_policy_v1((_candidate("cand-1", outcome=NOT_SATISFIED),)) is None


def test_i8_12_mutation_a_selector_falling_back_to_ascending_candidate_id_must_fail():
    """The mutation I8.12 names. A selector that resolves a two-qualifier set by
    ascending ``candidate_id`` returns ``cand-1``; the ratified one returns nothing,
    and a set recording that fallback is refused at construction."""
    two = (_candidate("cand-1"), _candidate("cand-2"))
    fallback = sorted(x.candidate_id for x in c.qualifying_pool(two))[0]
    assert fallback == "cand-1", "precondition: the tie-break would be decisive"
    assert c.selection_policy_v1(two) is None
    with pytest.raises(pydantic.ValidationError):
        _set(two, selected=fallback)


def test_i8_12_the_tie_break_is_deliberately_unexercised():
    """The companion assertion: no code path may resolve a multi-qualifier set to a
    selection. Checked structurally — the ratified selector's source performs no
    ordering of any kind — because an outcome check alone would pass against an
    implementation that sorted and then discarded the result."""
    tree = ast.parse(inspect.getsource(c.selection_policy_v1))
    called = {node.func.id for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "sorted" not in called and "min" not in called and "max" not in called, (
        "selection-policy v1 orders candidates; under OD-8's tie-break correction the "
        "candidate_id ordering may resolve a substantive preference only after one is "
        "separately ratified, and none is")
    attribute_calls = {node.func.attr for node in ast.walk(tree)
                       if isinstance(node, ast.Call)
                       and isinstance(node.func, ast.Attribute)}
    assert "sort" not in attribute_calls


# --------------------------------------------------------------------------- #
# I8.13 — OD-8 non-repurposing
# --------------------------------------------------------------------------- #

#: Every ``CandidateAdvisory`` field OD-8 bars from being read as a merit proxy. The
#: reason is provenance, not expressiveness: of these, none is package-computed and
#: replay-verified, so ranking on any of them would let the caller steer selection —
#: and ranking on fewer ``uncertainties`` would punish honest disclosure.
BARRED_AS_MERIT_PROXIES = (
    "evaluated_at", "candidate_id", "disposition", "requested_review_action",
    "claim_refs", "observation_refs", "assumptions", "uncertainties",
)

#: ``candidate_id`` is the one name that must still appear in the selector, because a
#: selector has to **name** what it selected. What OD-8 bars is reading it as a measure
#: of preference, and the two are different acts: the ratified selector reads it once,
#: after the pool is already a single candidate, purely to return that candidate's
#: identifier. The structural proof that it is not read as an ordering is
#: ``test_i8_12_the_tie_break_is_deliberately_unexercised``, which asserts the function
#: performs no ordering of any kind; this exemption is named rather than left implicit
#: so the two guards together say what a single substring scan cannot.
READ_TO_NAME_THE_SELECTION_NOT_TO_RANK = "candidate_id"


def _attributes_read_by(function):
    """Every attribute name the function's own **code** touches. Read from the AST with
    docstrings excluded: a prose mention of a barred field — this package's own
    explanation of *why* it is barred — is not a read of it, and a substring scan
    cannot tell the two apart."""
    tree = ast.parse(inspect.getsource(function))
    return {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}


def test_i8_13_the_v1_selector_reads_only_is_eligible_and_the_evaluation_outcome():
    """Enforced structurally, which is where I8.13 says to enforce it where possible."""
    read = _attributes_read_by(c.selection_policy_v1) | _attributes_read_by(
        c.qualifying_pool)
    for field in BARRED_AS_MERIT_PROXIES:
        if field == READ_TO_NAME_THE_SELECTION_NOT_TO_RANK:
            continue
        assert field not in read, (
            f"the ratified selector reads {field!r}; OD-8 bars it as a merit proxy")
    assert "is_eligible" in read and "domain_evaluation_outcome" in read
    # The pool itself — where a merit criterion would have to act — reads exactly two.
    assert _attributes_read_by(c.qualifying_pool) == {
        "is_eligible", "domain_evaluation_outcome", "SATISFIED"}


def test_i8_13_no_candidate_field_ranks_candidates_anywhere_in_src():
    """The wider structural half: no module in ``src/`` sorts candidates at all."""
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {"sorted", "min", "max"}:
                    args = ast.unparse(node)
                    assert "candidate" not in args or "ids" in args, (
                        f"{path.name} orders candidates: {args}")


def test_i8_13_the_prose_half_is_covered_by_the_documentation_guard():
    """I8.13's other half is prose, and is enforced by the documentation-consistency
    guard rather than restated here — the two must not drift into rival checks."""
    guard = pathlib.Path(__file__).with_name("test_documentation_consistency.py")
    body = guard.read_text(encoding="utf-8")
    assert "test_od8_bars_repurposing_existing_fields_as_merit_proxies" in body


# --------------------------------------------------------------------------- #
# I8.14 — OD-9 / OD-10 per-candidate scope
# --------------------------------------------------------------------------- #


def test_i8_14_one_qualifier_beside_an_inconclusive_candidate_selects_the_qualifier():
    """The case that distinguishes the ratified per-candidate reading from a run-wide
    one, and the one an implementer is most likely to get backwards.
    ``domain_evaluation_outcome`` is evaluated per candidate and does **not** poison
    the set: an ``INCONCLUSIVE`` candidate is filtered out of the qualifying pool, and
    nothing more."""
    candidates = (_candidate("cand-1", outcome=SATISFIED),
                  _candidate("cand-2", outcome=INCONCLUSIVE),
                  _candidate("cand-3", outcome=NOT_SATISFIED))
    assert c.selection_policy_v1(candidates) == "cand-1"
    assert _row(candidates=candidates) == (3, "cand-1")
    built = _set(candidates, selected="cand-1")
    assert built.selected_candidate_id == "cand-1"


def test_i8_14_a_zero_qualifier_set_with_an_inconclusive_candidate_abstains_od9():
    candidates = (_candidate("cand-1", outcome=INCONCLUSIVE),
                  _candidate("cand-2", outcome=NOT_SATISFIED))
    assert _row(candidates=candidates) == (5, None)
    assert v.FAIL_CLOSED_ROWS[5] == "ABSTAIN"


def test_i8_14_a_zero_qualifier_set_with_none_abstains_od10():
    candidates = (_candidate("cand-1", outcome=NOT_SATISFIED),
                  _candidate("cand-2", eligible=False, outcome=SATISFIED))
    assert _row(candidates=candidates) == (6, None)
    assert v.FAIL_CLOSED_ROWS[6] == "ABSTAIN"


def test_i8_14_inconclusive_never_escalates():
    """OD-9 maps ``INCONCLUSIVE`` to ``ABSTAIN`` unconditionally for the S2 MVP.
    ``ESCALATE`` is not selected: no authoritative, replayable severity condition is
    ratified, and under R-1a a no-selection run carries
    ``requested_review_destination_role_ref = None``, so a terminal ``ESCALATE`` here
    would assert a referral with no in-contract destination."""
    assert "ESCALATE" not in set(v.FAIL_CLOSED_ROWS.values())


# --------------------------------------------------------------------------- #
# I8.15 — the table's totality and disjointness, as a property
# --------------------------------------------------------------------------- #

#: Every combination of the three orchestration conditions and a representative
#: candidate population. I8.6 covers one case per row; this covers the rows together.
_POPULATIONS = {
    "empty-set": (),
    "unevaluated": (_candidate("cand-1", outcome=None),),
    "one-qualifier": (_candidate("cand-1"),),
    "two-qualifiers": (_candidate("cand-1"), _candidate("cand-2")),
    "one-qualifier-plus-inconclusive": (
        _candidate("cand-1"), _candidate("cand-2", outcome=INCONCLUSIVE)),
    "inconclusive-only": (_candidate("cand-1", outcome=INCONCLUSIVE),),
    "not-satisfied-only": (_candidate("cand-1", outcome=NOT_SATISFIED),),
    "ineligible-only": (_candidate("cand-1", eligible=False),),
}


@pytest.mark.parametrize("population", sorted(_POPULATIONS))
@pytest.mark.parametrize("evidence", [True, False])
@pytest.mark.parametrize("evaluator", [True, False])
@pytest.mark.parametrize("verified", [True, False])
def test_i8_15_exactly_one_row_matches_every_run(population, evidence, evaluator,
                                                 verified):
    """Totality: no run falls through without a ratified outcome. This is what makes
    OD-10 do its job rather than merely exist — the residual row is reached, not
    merely declared."""
    row, selected = _row(evidence=evidence, evaluator=evaluator, verified=verified,
                         candidates=_POPULATIONS[population])
    assert row in v.FAIL_CLOSED_ROWS
    assert (selected is not None) == (row == 3)


def test_i8_15_the_rows_are_mutually_exclusive_and_ordered():
    """Disjointness: each row's own condition holds for the runs it governs and for no
    others, so the ordering is a statement of precedence rather than a way to hide an
    overlap. Checked by asserting each row's defining condition on a run classified
    into it, over the whole population above.
    """
    seen = set()
    for population in _POPULATIONS.values():
        for evidence in (True, False):
            for evaluator in (True, False):
                for verified in (True, False):
                    row, _ = _row(evidence=evidence, evaluator=evaluator,
                                  verified=verified, candidates=population)
                    seen.add(row)
                    pool = c.qualifying_pool(population)
                    if row == 1:
                        assert not evidence or not evaluator
                    elif row == 2:
                        assert evidence and evaluator and not verified
                    else:
                        assert evidence and evaluator and verified
                        if row == 3:
                            assert len(pool) == 1
                        elif row == 4:
                            assert len(pool) > 1
                        elif row == 5:
                            assert not pool and any(
                                x.domain_evaluation_outcome is INCONCLUSIVE
                                for x in population)
                        else:
                            assert row == 6
                            assert not pool and not any(
                                x.domain_evaluation_outcome is INCONCLUSIVE
                                for x in population)
    assert seen == set(v.FAIL_CLOSED_ROWS), (
        f"the population above never reaches rows {sorted(set(v.FAIL_CLOSED_ROWS) - seen)}; "
        "a totality property over a population that cannot reach a row proves nothing "
        "about that row")


def test_i8_15_no_completed_run_falls_through_without_a_ratified_outcome():
    """Row 2 is the only classification that names no terminal outcome, and it is not a
    fall-through: it refuses construction outright."""
    for row, outcome in v.FAIL_CLOSED_ROWS.items():
        if row == 2:
            assert outcome is None
        else:
            assert outcome in {"NEED_EVIDENCE", "PROPOSAL", "ABSTAIN"}


# --------------------------------------------------------------------------- #
# The boundary this amendment did NOT authorize
# --------------------------------------------------------------------------- #


def test_the_provider_boundary_authorizes_no_network_storage_discovery_or_plugin_load():
    """OD-7 part 2, barred outright by the owner's ruling: the injected object is a
    plain in-process callable and nothing about its own implementation is this
    package's concern. Nothing in ``src/`` may import or name a mechanism for reaching
    one."""
    barred = {"socket", "ssl", "urllib", "http", "requests", "httpx", "importlib",
              "pkgutil", "pkg_resources", "sqlite3", "shelve", "pickle", "subprocess",
              "asyncio", "multiprocessing"}
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                roots = {(node.module or "").split(".")[0]}
            else:
                continue
            assert roots & barred == set(), (
                f"{path.name} imports {sorted(roots & barred)}; OD-7 part 2 authorizes "
                "no network, storage, service-discovery or plugin-loading mechanism")
    # And no dynamic-load spelling reaches one either.
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"__import__", "eval", "exec", "open"}, (
                    f"{path.name} calls {node.func.id}")


def test_the_provider_is_authoritative_only_for_domain_evaluation():
    """OD-8: the provider does not acquire business-preference authority through this
    or the OD-8 ruling. The selector consumes the provider's outcome and nothing else
    the provider says, and it takes no provider argument at all."""
    assert "provider" not in inspect.signature(
        ap.verify_deterministic_selection).parameters
    for function in (c.selection_policy_v1, c.qualifying_pool):
        tree = ast.parse(inspect.getsource(function))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        names |= {node.attr for node in ast.walk(tree)
                  if isinstance(node, ast.Attribute)}
        assert "provider" not in names, (
            f"{function.__name__} reaches the provider; OD-8 grants it no "
            "business-preference authority")
