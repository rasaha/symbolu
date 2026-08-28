"""I7's twelve test obligations, discharged against the declared S1 contracts.

Each obligation below is numbered as I7 states it in
``docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md``. None of these duplicate the
per-field classification checks in ``test_identifier_normalization.py`` or the
per-rule constructions in ``test_unenforced_local_rules.py``; they discharge the
obligations Part I lists as still outstanding once the first contract module lands.
"""
from __future__ import annotations

import ast
import pathlib
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import pydantic
import pytest

import ugence_agentic_proposer as ap
import s1_specification_mirror as spec
from ugence_agentic_proposer import identity as identity_module

SRC = pathlib.Path(ap.__file__).resolve().parent


def _sources():
    return sorted(SRC.rglob("*.py"))


FIXED_INSTANT = spec.FIXED_INSTANT


def _full_advisory_scenario():
    """A complete, lawful scenario: identity, role, mandate, context, one read-only
    observation, one eligible candidate, a candidate set and a built advisory."""
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
        escalation_role_ref="role-2", activation_status=ap.RoleActivationStatus.ACTIVE)
    later = FIXED_INSTANT + timedelta(days=365)
    mandate = ap.WorkMandate(
        schema_version="1.0", tenant_id="tenant-1", created_at=FIXED_INSTANT,
        mandate_id="mandate-1", case_ref="case-1", assigned_role_contract_id="role-1",
        purpose="reconcile invoices for Q1", allowed_source_scopes=["ledger.read"],
        expires_at=later)
    context = ap.BoundedContextEnvelope(
        schema_version="1.0", tenant_id="tenant-1", created_at=FIXED_INSTANT,
        context_id="context-1", mandate_id="mandate-1",
        allowed_record_refs=["record-1"], excluded_data_classes=[],
        context_hash=spec.PLACEHOLDER_DIGEST, expires_at=later)
    observation = ap.ToolObservation(
        schema_version="1.0", tenant_id="tenant-1", created_at=FIXED_INSTANT,
        observation_id="obs-1", case_ref="case-1", tool_name="invoice.read",
        operation_class=ap.ToolOperationClass.READ_ONLY, source_ref="record-1",
        observed_at=FIXED_INSTANT, content_hash=spec.PLACEHOLDER_DIGEST,
        normalized_fields={"vendor.name": "Acme Corp"})
    provider = spec.StubDomainEvaluationProvider()
    candidate = ap.build_candidate_advisory(
        candidate_id="cand-1", identity=identity, role=role, mandate=mandate,
        context=context, observations=[observation],
        disposition=ap.CandidateDisposition.RECOMMEND_WITHHOLD,
        requested_review_action=ap.ReviewAction.ROUTE_APPROVAL_BUNDLE,
        observation_refs=["obs-1"], claim_refs=[], assumptions=[], uncertainties=[],
        evaluated_at=FIXED_INSTANT, provider=provider,
        profile_id=spec.PROFILE_ID, profile_version=spec.PROFILE_VERSION)
    # Under selection-policy v1 a set holding exactly one eligible, SATISFIED
    # candidate MUST select it (OD-7 part 7, row 3). The always-null shape C9 forced
    # in S1 is no longer the lawful one for a set like this.
    candidate_set = ap.build_advisory_candidate_set(
        candidate_set_id="set-1", tenant_id="tenant-1", case_ref="case-1",
        created_at=FIXED_INSTANT, candidates=(candidate,),
        selected_candidate_id="cand-1",
        domain_evaluation_profile_id=spec.PROFILE_ID,
        domain_evaluation_profile_version=spec.PROFILE_VERSION)
    advisory = ap.build_proposer_advisory(
        tenant_id="tenant-1", case_ref="case-1", created_at=FIXED_INSTANT,
        identity=identity, role=role, mandate=mandate, context=context,
        observations=[observation], candidate_set=candidate_set,
        parent_advisory_digest=None, claim_summaries=["reconciled against ledger"],
        observation_refs=[], uncertainties=[], expires_at=later,
        provider=provider, expected_profile_id=spec.PROFILE_ID,
        expected_profile_version=spec.PROFILE_VERSION,
        requested_review_destination_role_ref="role-approver")
    return dict(identity=identity, role=role, mandate=mandate, context=context,
               observation=observation, candidate=candidate, provider=provider,
               candidate_set=candidate_set, advisory=advisory)


@pytest.fixture(scope="module")
def scenario():
    return _full_advisory_scenario()


# --------------------------------------------------------------------------- #
# I7.1 — the frozen-profile suite
# --------------------------------------------------------------------------- #

def test_i7_1_frozen_profile_pins_exact_bytes_and_identity(scenario):
    """The C6 profile, the C4 `Z` serialisation at microsecond precision, the
    `exclude_none=False` retention of `parent_advisory_digest: null`, and the G1/G2
    payload-projection equivalence — over a fixed, pinned corpus.

    Never spells the digest prefix or recomputes the hash inline: doing so in this
    (non-authorised) module would collide with the D2 scan exactly as A7 records, so
    the comparison goes through ``identity.compute_advisory_identity`` and
    ``verify_advisory_identity``, both already correct and pinned by their own tests.
    """
    advisory = scenario["advisory"]

    p_unsigned = advisory.model_dump(
        mode="json", exclude={"advisory_digest"}, exclude_none=False)

    # exclude_none=False retains parent_advisory_digest: null (A9, C6).
    assert "parent_advisory_digest" in p_unsigned
    assert p_unsigned["parent_advisory_digest"] is None

    # C4: full microsecond precision with a trailing Z.
    assert p_unsigned["created_at"] == "2026-01-01T12:00:00Z"
    assert p_unsigned["expires_at"].endswith("Z")

    # The identity value is pinned: recomputing it twice agrees, byte for byte.
    import ugence_jcs
    canonical = ugence_jcs.canonical_bytes(p_unsigned, set_paths=frozenset(),
                                          nfc_paths=frozenset())
    assert ugence_jcs.canonical_bytes(p_unsigned, set_paths=frozenset(),
                                      nfc_paths=frozenset()) == canonical
    assert ap.verify_advisory_identity(advisory=advisory) is True

    # G2's equivalence obligation: the payload's own projection equals G1's.
    assert (identity_module.compute_advisory_identity(advisory=advisory)
            == advisory.advisory_digest)


def test_i7_1_the_identity_value_is_a_bare_64_character_lowercase_hex_body(scenario):
    body = scenario["advisory"].advisory_digest.split(":", 1)[1]
    assert len(body) == 64
    assert body == body.lower()
    int(body, 16)  # raises ValueError if not valid hex


# --------------------------------------------------------------------------- #
# I7.2 — list-order significance
# --------------------------------------------------------------------------- #

def test_i7_2_reordering_an_identity_participating_list_changes_the_identity_value(scenario):
    advisory = scenario["advisory"]
    reordered = advisory.model_copy(update={
        "claim_summaries": ["a", "b"], "uncertainties": [],
    })
    original = advisory.model_copy(update={"claim_summaries": ["a", "b"]})
    swapped = advisory.model_copy(update={"claim_summaries": ["b", "a"]})
    assert (identity_module.compute_advisory_identity(advisory=original)
            != identity_module.compute_advisory_identity(advisory=swapped))


def test_i7_2_reordering_a_nested_candidates_list_changes_the_identity_value(scenario):
    candidate_a = scenario["candidate"]
    candidate_b = candidate_a.model_copy(update={"candidate_id": "cand-2"})
    advisory = scenario["advisory"]
    forward = advisory.model_copy(update={"candidates": (candidate_a, candidate_b)})
    # Ascending order is enforced at construction, so a "reversed" comparison is made
    # directly against P_unsigned rather than by constructing an out-of-order model.
    forward_identity = identity_module.compute_advisory_identity(advisory=forward)
    p_unsigned = forward.model_dump(mode="json", exclude={"advisory_digest"},
                                    exclude_none=False)
    reversed_projection = dict(p_unsigned)
    reversed_projection["candidates"] = list(reversed(p_unsigned["candidates"]))
    import ugence_jcs
    reversed_identity = ugence_jcs.canonical_sha256_hex(
        reversed_projection, set_paths=frozenset(), nfc_paths=frozenset())
    assert forward_identity.split(":", 1)[1] != reversed_identity


def test_i7_2_reordering_a_nested_candidates_observation_refs_changes_the_identity_value(scenario):
    candidate = scenario["candidate"].model_copy(
        update={"observation_refs": ["obs-1", "obs-2"]})
    other = scenario["candidate"].model_copy(
        update={"observation_refs": ["obs-2", "obs-1"]})
    advisory_a = scenario["advisory"].model_copy(update={"candidates": (candidate,)})
    advisory_b = scenario["advisory"].model_copy(update={"candidates": (other,)})
    assert (identity_module.compute_advisory_identity(advisory=advisory_a)
            != identity_module.compute_advisory_identity(advisory=advisory_b))


def test_i7_2_reordering_a_non_identity_participating_list_does_not_change_the_identity_value(
        scenario):
    """`permitted_tool_scopes` (CognitiveRoleContract) and `allowed_record_refs`
    (BoundedContextEnvelope) are not reachable from `ProposerAdvisory` (D9), so no
    order of either can appear in `P_unsigned` at all."""
    advisory = scenario["advisory"]
    reachable_keys = _projection_keys(advisory.model_dump(mode="json"))
    assert "permitted_tool_scopes" not in reachable_keys
    assert "allowed_record_refs" not in reachable_keys


def _projection_keys(payload, prefix=""):
    keys = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            keys.add(f"{prefix}{key}")
            keys |= _projection_keys(value, f"{prefix}{key}.")
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            keys |= _projection_keys(item, f"{prefix}[].")
    return keys


def test_i7_2_an_out_of_order_candidate_sequence_is_rejected_not_reordered(scenario):
    """``model_copy`` skips validation by design, so the out-of-order construction is
    tested through a validating path — ``model_validate`` over the advisory's own
    projection with a reordered ``candidates`` — and through the builder."""
    candidate_a = scenario["candidate"]
    candidate_b = candidate_a.model_copy(update={"candidate_id": "z-2"})
    fields = scenario["advisory"].model_dump(mode="python")
    fields["candidates"] = (candidate_b, candidate_a)
    with pytest.raises(pydantic.ValidationError):
        ap.ProposerAdvisory.model_validate(fields)
    with pytest.raises(pydantic.ValidationError):
        ap.build_advisory_candidate_set(
            candidate_set_id="set-2", tenant_id="tenant-1", case_ref="case-1",
            created_at=FIXED_INSTANT, candidates=(candidate_b, candidate_a),
            selected_candidate_id=None,
            domain_evaluation_profile_id=spec.PROFILE_ID,
            domain_evaluation_profile_version=spec.PROFILE_VERSION)


# --------------------------------------------------------------------------- #
# I7.3 — no bare number
# --------------------------------------------------------------------------- #

import decimal
import typing as _typing

_NUMERIC_LEAF_TYPES = (int, float, decimal.Decimal)


def _leaf_types(annotation, seen=None):
    """Every leaf type reachable from ``annotation`` through generics and unions.

    Structural, not textual: a substring scan over ``str(annotation)`` is unreliable
    (``StringConstraints`` itself contains the substring ``"int"``).
    """
    seen = set() if seen is None else seen
    if id(annotation) in seen:
        return set()
    seen.add(id(annotation))
    if annotation is _typing.Any:
        return {_typing.Any}
    args = _typing.get_args(annotation)
    if args:
        found = set()
        for arg in args:
            found |= _leaf_types(arg, seen)
        return found
    if isinstance(annotation, type):
        return {annotation}
    return set()


def test_i7_3_no_contract_field_is_numeric_or_any_typed():
    """No field of any contract or nested model is `int`, `float`, `Decimal` or
    `Any`, at any depth, including inside a container (A1, C3). `bool` is unaffected
    (A1): it is not `int` by identity, only by subclassing."""
    for name in spec.TOP_LEVEL_CONTRACTS + spec.NESTED_PUBLIC_SHAPES:
        model = getattr(ap, name)
        for field_name, field in model.model_fields.items():
            leaves = _leaf_types(field.annotation)
            numeric = leaves & set(_NUMERIC_LEAF_TYPES)
            assert not numeric, f"{name}.{field_name} is numeric-typed: {numeric}"
            assert _typing.Any not in leaves, f"{name}.{field_name} is Any-typed"


def test_i7_3_the_scenario_corpus_raises_no_bare_number_error(scenario):
    import ugence_jcs
    for name, model in (
        ("identity", scenario["identity"]), ("role", scenario["role"]),
        ("mandate", scenario["mandate"]), ("context", scenario["context"]),
        ("observation", scenario["observation"]), ("candidate", scenario["candidate"]),
        ("candidate_set", scenario["candidate_set"]), ("advisory", scenario["advisory"]),
    ):
        payload = model.model_dump(mode="json")
        try:
            ugence_jcs.canonical_bytes(payload, set_paths=frozenset(), nfc_paths=frozenset())
        except ugence_jcs.BareNumberError:
            pytest.fail(f"{name}'s projection raised BareNumberError")


# --------------------------------------------------------------------------- #
# I7.4 — no wall clock
# --------------------------------------------------------------------------- #

_WALL_CLOCK_CALLS = ("now", "utcnow", "time", "monotonic")


def test_i7_4_no_src_module_reads_a_wall_clock():
    offenders = []
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute) or node.attr not in _WALL_CLOCK_CALLS:
                continue
            owner = node.value
            owner_name = (owner.id if isinstance(owner, ast.Name)
                         else owner.attr if isinstance(owner, ast.Attribute) else "")
            if owner_name in {"datetime", "time"}:
                offenders.append((path.name, ast.unparse(node)))
    assert not offenders, f"a wall clock is referenced: {offenders}"


def test_i7_4_no_field_defaults_to_a_computed_current_time():
    for name in spec.TOP_LEVEL_CONTRACTS + spec.NESTED_PUBLIC_SHAPES:
        model = getattr(ap, name)
        for field_name, field in model.model_fields.items():
            assert field.default_factory is None, (
                f"{name}.{field_name} has a default_factory; no datetime field may "
                "default to a computed current time (C4)")


# --------------------------------------------------------------------------- #
# I7.5 — naive-datetime rejection, and non-UTC normalisation
# --------------------------------------------------------------------------- #

def _revalidated(model, **overrides):
    """``model_copy(update=...)`` skips validation; this re-validates so C4's
    normalising validator actually runs. Fields are read back by attribute rather
    than through ``model_dump``, because (G2) the explicit C4 serializer runs in
    every dump mode and a JSON-mode string is rejected by this ``strict=True``
    model exactly as G2 describes for ``ProposerAdvisory`` itself."""
    fields = {name: getattr(model, name) for name in type(model).model_fields}
    fields.update(overrides)
    return type(model).model_validate(fields)


def test_i7_5_a_non_utc_offset_is_normalised_to_utc_not_preserved(scenario):
    plus_two = FIXED_INSTANT.astimezone(timezone(timedelta(hours=2)))
    advisory = _revalidated(scenario["advisory"], created_at=plus_two)
    assert advisory.created_at == FIXED_INSTANT
    assert advisory.created_at.utcoffset() == timedelta(0)
    dumped = advisory.model_dump(mode="json")
    assert dumped["created_at"] == "2026-01-01T12:00:00Z"


def test_i7_5_two_offsets_naming_the_same_instant_produce_the_same_identity_value(scenario):
    plus_two = FIXED_INSTANT.astimezone(timezone(timedelta(hours=2)))
    a = _revalidated(scenario["advisory"], created_at=FIXED_INSTANT)
    b = _revalidated(scenario["advisory"], created_at=plus_two)
    assert (identity_module.compute_advisory_identity(advisory=a)
            == identity_module.compute_advisory_identity(advisory=b))


# --------------------------------------------------------------------------- #
# I7.6 — eligibility forgery
# --------------------------------------------------------------------------- #

def _ineligible_candidate_fields():
    """A candidate whose ``disposition`` is not in the scenario role's permitted set
    (``[RECOMMEND_WITHHOLD]``), so Equation 1's ``OutputPermitted`` term — and so
    ``evaluate_eligibility`` as a whole — is genuinely ``False`` for it under the
    scenario's own identity/role/mandate/context/observations."""
    return {
        **spec.complete_candidate("cand-1"),
        "disposition": ap.CandidateDisposition.RECOMMEND_MATCHED_FOR_APPROVAL,
        "is_eligible": False,
    }


def test_i7_6_a_forged_is_eligible_via_model_construct_is_rejected_on_replay(scenario):
    forged = ap.CandidateAdvisory.model_construct(
        **{**_ineligible_candidate_fields(), "is_eligible": True})
    forged_set = scenario["candidate_set"].model_copy(update={"candidates": (forged,)})
    assert ap.verify_candidate_eligibility(
        candidate_set=forged_set, identity=scenario["identity"], role=scenario["role"],
        mandate=scenario["mandate"], context=scenario["context"],
        observations=[scenario["observation"]]) is False


def test_i7_6_build_proposer_advisory_raises_eligibility_mismatch_error(scenario):
    forged = ap.CandidateAdvisory.model_construct(
        **{**_ineligible_candidate_fields(), "is_eligible": True})
    forged_set = scenario["candidate_set"].model_copy(update={"candidates": (forged,)})
    with pytest.raises(ap.EligibilityMismatchError):
        ap.build_proposer_advisory(
            tenant_id="tenant-1", case_ref="case-1", created_at=FIXED_INSTANT,
            identity=scenario["identity"], role=scenario["role"],
            mandate=scenario["mandate"], context=scenario["context"],
            observations=[scenario["observation"]], candidate_set=forged_set,
            parent_advisory_digest=None, claim_summaries=[], observation_refs=[],
            uncertainties=[], expires_at=scenario["mandate"].expires_at,
            provider=scenario["provider"], expected_profile_id=spec.PROFILE_ID,
            expected_profile_version=spec.PROFILE_VERSION,
            requested_review_destination_role_ref=None)
    assert issubclass(ap.EligibilityMismatchError, ValueError)


# --------------------------------------------------------------------------- #
# I7.7 — what replaced C7's structural ceiling (OD-7 part 3, part 6)
#
# C7 rejected ``COMPLETE`` unconditionally, which is what made every candidate this
# package could build unready. C7 is gone. What stands in its place is the
# completion/outcome coupling and Equation 2's seventh term, and I7.7 is discharged
# against those rather than against a refusal that no longer exists.
# --------------------------------------------------------------------------- #

def test_i7_7_complete_without_an_outcome_is_unconstructible():
    """The coupling's first direction. ``COMPLETE`` is now constructible — but not
    with no bound evaluation result to check it against, which is precisely the state
    OD-7 part 8 says removing C7 alone would have allowed."""
    with pytest.raises(pydantic.ValidationError):
        ap.CandidateAdvisory(**{
            **spec.complete_candidate(), "domain_check_completion":
            ap.DomainCheckCompletion.COMPLETE, "domain_evaluation_outcome": None})


def test_i7_7_an_outcome_without_complete_is_unconstructible():
    """The coupling's second direction: a result with no completed evaluation behind
    it."""
    with pytest.raises(pydantic.ValidationError):
        ap.CandidateAdvisory.model_validate({
            **spec.complete_candidate(),
            "domain_check_completion": "NOT_EVALUATED",
            "domain_evaluation_outcome": "SATISFIED"})


def test_i7_7_the_coupling_survives_model_construct_then_validate():
    """``model_construct`` bypasses every validator; a subsequent revalidation catches
    the bypassed state, because the coupling is a real validator rather than merely
    absent from ``model_construct``'s own path. The same disclosed ceiling C7 and C9
    each stated of themselves."""
    forged = ap.CandidateAdvisory.model_construct(**{
        **spec.complete_candidate(), "domain_check_completion":
        ap.DomainCheckCompletion.COMPLETE})
    with pytest.raises(pydantic.ValidationError):
        ap.CandidateAdvisory.model_validate(forged.model_dump())


def test_i7_7_a_lawfully_evaluated_candidate_is_ready(scenario):
    """The direction C7 made untestable. A candidate that is eligible, ``COMPLETE``
    and ``SATISFIED``, with matching lineage, is ready — which is R-2's condition for
    ``terminal_outcome=PROPOSAL``, reachable for the first time here."""
    assert scenario["candidate"].domain_check_completion is (
        ap.DomainCheckCompletion.COMPLETE)
    assert scenario["candidate"].domain_evaluation_outcome is (
        ap.DomainEvaluationOutcome.SATISFIED)
    assert ap.evaluate_readiness(
        candidate=scenario["candidate"], identity=scenario["identity"],
        role=scenario["role"], mandate=scenario["mandate"],
        context=scenario["context"]) is True


def test_i7_7_an_unevaluated_candidate_is_still_unready(scenario):
    """The fail-closed direction is unchanged: no evaluation, no readiness."""
    unevaluated = ap.CandidateAdvisory(**{
        **spec.complete_candidate(), "is_eligible": True})
    assert ap.evaluate_readiness(
        candidate=unevaluated, identity=scenario["identity"],
        role=scenario["role"], mandate=scenario["mandate"],
        context=scenario["context"]) is False


# --------------------------------------------------------------------------- #
# I7.8 — V13
# --------------------------------------------------------------------------- #

def test_i7_8_proposal_without_a_selection_is_refused_by_the_builder(scenario):
    """V13's surviving locally decidable half (R-2). The S1 form of this test asserted
    that ``PROPOSAL`` was unreachable at all; with C7 gone it is reachable, and what
    remains refused is a proposal that proposes nothing."""
    with pytest.raises(pydantic.ValidationError):
        ap.build_proposer_process_record(
            process_record_id="rec-1", tenant_id="tenant-1", case_ref="case-1",
            created_at=FIXED_INSTANT, declared_strategy="reconcile and propose",
            state_transitions=[], tool_invocations=[], candidate_ids=["cand-1"],
            selected_candidate_id=None, terminal_outcome=ap.TerminalOutcome.PROPOSAL,
            advisory_digest=scenario["advisory"].advisory_digest,
            started_at=FIXED_INSTANT, completed_at=FIXED_INSTANT)


def test_i7_8_a_lawful_selection_is_carried_with_all_three_dependents(scenario):
    """The S1 form of this test asserted a null selector on every builder-produced
    advisory, which was C9's ceiling rather than a property of the builder. With C9
    gone the builder carries the selection selection-policy v1 produced, and R-1a's
    joint-presence coupling holds on the non-null branch for the first time."""
    advisory = scenario["advisory"]
    assert advisory.selected_candidate_id == "cand-1"
    assert advisory.recommended_disposition is (
        ap.CandidateDisposition.RECOMMEND_WITHHOLD)
    assert advisory.requested_review_action is ap.ReviewAction.ROUTE_APPROVAL_BUNDLE
    assert advisory.requested_review_destination_role_ref == "role-approver"


def test_i7_8_the_selection_is_mirrored_into_the_advisorys_own_policy_identity(scenario):
    """OD-7 part 5: the selector-policy identity is inside ``P_unsigned`` because it is
    the advisory's own field, and it equals the set's (R-1b's new clauses)."""
    advisory, candidate_set = scenario["advisory"], scenario["candidate_set"]
    for name in ("domain_evaluation_profile_id", "domain_evaluation_profile_version",
                 "selection_policy_id", "selection_policy_version"):
        assert getattr(advisory, name) == getattr(candidate_set, name) is not None
    projection = advisory.model_dump(mode="json", exclude={"advisory_digest"})
    assert projection["selection_policy_version"] == "v1"


# --------------------------------------------------------------------------- #
# I7.9 — R-3 process ordering
# --------------------------------------------------------------------------- #

def _record_fixture(**overrides):
    fixture = dict(
        schema_version="1.0", tenant_id="tenant-1", created_at=FIXED_INSTANT,
        process_record_id="rec-1", case_ref="case-1",
        declared_strategy="reconcile and propose", state_transitions=[],
        tool_invocations=[], deterministic_checks=[], candidate_ids=[],
        selected_candidate_id=None, semantic_audit_refs=[],
        terminal_outcome=ap.TerminalOutcome.ABSTAIN, reason_codes=[],
        advisory_digest=spec.PLACEHOLDER_DIGEST, jcs_distribution_version="0.2.0",
        started_at=FIXED_INSTANT, completed_at=FIXED_INSTANT)
    fixture.update(overrides)
    return fixture


def _t(state, at=None):
    return ap.ProposerProcessStateTransition(
        state=state, at=FIXED_INSTANT if at is None else at)


def test_i7_9_r3_rejects_a_backward_transition():
    with pytest.raises(pydantic.ValidationError):
        ap.ProposerProcessRecord(**_record_fixture(state_transitions=[
            _t(ap.ProposerProcessState.VALIDATED), _t(ap.ProposerProcessState.RECEIVED)]))


def test_i7_9_r3_rejects_a_repeated_state():
    with pytest.raises(pydantic.ValidationError):
        ap.ProposerProcessRecord(**_record_fixture(state_transitions=[
            _t(ap.ProposerProcessState.RECEIVED), _t(ap.ProposerProcessState.RECEIVED)]))


def test_i7_9_r3_rejects_two_terminal_states():
    with pytest.raises(pydantic.ValidationError):
        ap.ProposerProcessRecord(**_record_fixture(state_transitions=[
            _t(ap.ProposerProcessState.ABSTAIN), _t(ap.ProposerProcessState.ESCALATE)],
            terminal_outcome=ap.TerminalOutcome.ESCALATE))


def test_i7_9_r3_rejects_a_terminal_in_non_final_position():
    with pytest.raises(pydantic.ValidationError):
        ap.ProposerProcessRecord(**_record_fixture(state_transitions=[
            _t(ap.ProposerProcessState.ABSTAIN), _t(ap.ProposerProcessState.EVALUATING)]))


def test_i7_9_r3_accepts_a_lawful_forward_only_chain():
    record = ap.ProposerProcessRecord(**_record_fixture(state_transitions=[
        _t(ap.ProposerProcessState.RECEIVED),
        _t(ap.ProposerProcessState.VALIDATED),
        _t(ap.ProposerProcessState.OBSERVING),
        _t(ap.ProposerProcessState.RECONCILING),
        _t(ap.ProposerProcessState.EVALUATING),
        _t(ap.ProposerProcessState.ABSTAIN),
    ]))
    assert record.terminal_outcome is ap.TerminalOutcome.ABSTAIN


# --------------------------------------------------------------------------- #
# I7.10 — ugence-jcs resolves as an installed distribution
# --------------------------------------------------------------------------- #

def test_i7_10_the_substrate_resolves_as_an_installed_distribution_at_or_above_0_2_0():
    import ugence_jcs
    version = tuple(int(part) for part in ugence_jcs.__version__.split(".")[:2])
    assert version >= (0, 2), (
        f"ugence-jcs {ugence_jcs.__version__} is below the 0.2.0 floor that exposes "
        "canonical_sha256_hex")
    assert hasattr(ugence_jcs, "canonical_sha256_hex")
    assert callable(ugence_jcs.canonical_sha256_hex)


def test_i7_10_the_process_record_states_the_resolved_distribution_version(scenario):
    import ugence_jcs
    record = ap.build_proposer_process_record(
        process_record_id="rec-1", tenant_id="tenant-1", case_ref="case-1",
        created_at=FIXED_INSTANT, declared_strategy="reconcile and propose",
        state_transitions=[], tool_invocations=[], candidate_ids=["cand-1"],
        selected_candidate_id=None, terminal_outcome=ap.TerminalOutcome.ABSTAIN,
        advisory_digest=scenario["advisory"].advisory_digest,
        started_at=FIXED_INSTANT, completed_at=FIXED_INSTANT)
    assert record.jcs_distribution_version == ugence_jcs.__version__


# --------------------------------------------------------------------------- #
# I7.11 — rival-identity reachability is discharged by test_advisory_contract_
# shape.py's existing, now-armed tests over the real ``ProposerAdvisory`` and
# ``CandidateAdvisory``; this is a cross-check that they actually bind.
# --------------------------------------------------------------------------- #

def test_i7_11_the_declared_surface_guard_is_armed_not_skipped():
    import importlib
    shape = importlib.import_module("test_advisory_contract_shape")
    declared = shape._declared_advisory_classes()
    assert set(declared) == {"ProposerAdvisory", "CandidateAdvisory"}, (
        "the I7.11 declared-surface tests in test_advisory_contract_shape.py are "
        "dormant: no advisory type was found in src/")


# --------------------------------------------------------------------------- #
# I7.12 — the C8 declaration-form mutation test
# --------------------------------------------------------------------------- #

def test_i7_12_no_src_model_declares_a_string_constraint_through_field():
    """A scan asserting no `src` model declares a string constraint through
    `Field(...)` on any field (C8)."""
    offenders = []
    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = (node.func.id if isinstance(node.func, ast.Name)
                     else node.func.attr if isinstance(node.func, ast.Attribute) else "")
            if called != "Field":
                continue
            for keyword in node.keywords:
                if keyword.arg in ("pattern", "regex", "max_length", "min_length",
                                   "strip_whitespace"):
                    offenders.append((path.name, ast.unparse(node)))
    assert not offenders, f"a string constraint reached through Field(...): {offenders}"


#: Built at runtime, never spelled contiguously in this module's own source: this
#: file is not the authorised identity module, and the C6 grammar's hash-algorithm
#: name is exactly the substring the D2 scan hunts (A7, I1).
_DIGEST_LIKE_PATTERN = "^sha" "256:[0-9a-f]{64}$"


def test_i7_12_field_pattern_is_reported_as_an_unpermitted_identity_source():
    """The mutation half: `advisory_digest: str = Field(pattern=...)` must be reported
    by the identity-source guard, and the ratified `Annotated[...]` spelling must not."""
    import importlib
    shape = importlib.import_module("test_advisory_contract_shape")
    field_form = (
        "class M:\n"
        "    advisory_digest: str = Field(pattern=" + repr(_DIGEST_LIKE_PATTERN) + ")\n"
    )
    annotated_form = (
        "class M:\n"
        "    advisory_digest: Annotated[str, StringConstraints(pattern="
        + repr(_DIGEST_LIKE_PATTERN) + ")]\n"
    )
    assert shape._unpermitted_identity_sources(field_form)
    assert not shape._unpermitted_identity_sources(annotated_form)


def test_i7_12_the_real_hash_shaped_fields_use_the_annotated_spelling():
    tree = ast.parse((SRC / "contracts.py").read_text(encoding="utf-8"),
                     filename="contracts.py")
    digest_fields = {"advisory_digest", "parent_advisory_digest", "context_hash",
                     "content_hash"}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)):
            continue
        if node.target.id not in digest_fields:
            continue
        text = ast.unparse(node.annotation)
        assert "Field(" not in text, f"{node.target.id}: {text}"


# --------------------------------------------------------------------------- #
# I7.13 — construction shape under strict=True (G2)
# --------------------------------------------------------------------------- #

def _unsigned_payload_for(advisory):
    """The private payload model, populated from an already-built advisory's own
    fields — the same fields ``build_proposer_advisory`` itself passes through
    before computing the identity value."""
    PayloadModel = identity_module._unsigned_advisory_payload_model()
    return PayloadModel(**{name: getattr(advisory, name)
                           for name in PayloadModel.model_fields})


def test_i7_13_the_explicit_pass_through_constructs_the_right_leaf_types(scenario):
    payload = _unsigned_payload_for(scenario["advisory"])
    assert isinstance(payload.created_at, datetime)
    assert isinstance(payload.candidates, tuple)
    assert all(isinstance(c, ap.CandidateAdvisory) for c in payload.candidates)


def test_i7_13_the_json_mode_dump_idiom_raises_datetime_type_and_tuple_type(scenario):
    """The exact regression I7.13 exists to block: feeding the payload's own
    ``model_dump(mode="json", exclude_none=False)`` back into the constructor is
    not a no-op under ``strict=True``. It fails on two independent grounds at
    once — every datetime became a string, and the tuple became a JSON array —
    and both must be asserted, not just that construction fails somehow."""
    payload = _unsigned_payload_for(scenario["advisory"])
    dumped = payload.model_dump(mode="json", exclude_none=False)
    dumped["advisory_digest"] = spec.PLACEHOLDER_DIGEST
    with pytest.raises(pydantic.ValidationError) as excinfo:
        ap.ProposerAdvisory(**dumped)
    types = {error["type"] for error in excinfo.value.errors()}
    assert {"datetime_type", "tuple_type"} <= types


def test_i7_13_the_default_mode_dump_idiom_raises_datetime_type_but_not_tuple_type(
        scenario):
    """The narrower failure under the *other* dump mode, asserted separately so
    the two modes' distinct failure surfaces cannot collapse into one vague
    "model_dump raises" claim. The explicit C4 field_serializer carries no
    ``when_used="json"``, so it runs under ``model_dump()`` too and
    ``created_at`` comes back a string either way; the tuple container itself
    survives mode="python" untouched, so this mode fails on strictly fewer
    grounds than the JSON-mode idiom above."""
    payload = _unsigned_payload_for(scenario["advisory"])
    dumped = payload.model_dump()
    dumped["advisory_digest"] = spec.PLACEHOLDER_DIGEST
    with pytest.raises(pydantic.ValidationError) as excinfo:
        ap.ProposerAdvisory(**dumped)
    types = {error["type"] for error in excinfo.value.errors()}
    assert "datetime_type" in types
    assert "tuple_type" not in types


def test_i7_13_a_list_passed_to_either_candidates_field_is_rejected_with_tuple_type(
        scenario):
    with pytest.raises(pydantic.ValidationError) as excinfo:
        ap.AdvisoryCandidateSet(
            schema_version="1.0", tenant_id="tenant-1", created_at=FIXED_INSTANT,
            candidate_set_id="set-1", case_ref="case-1",
            candidates=[scenario["candidate"]], selected_candidate_id=None,
            selection_reason_codes=[])
    assert "tuple_type" in {e["type"] for e in excinfo.value.errors()}

    with pytest.raises(pydantic.ValidationError) as excinfo:
        _revalidated(scenario["advisory"], candidates=[scenario["candidate"]])
    assert "tuple_type" in {e["type"] for e in excinfo.value.errors()}


# --------------------------------------------------------------------------- #
# I7.14 — R-7 replay (E2)
# --------------------------------------------------------------------------- #

def test_i7_14_a_dangling_reference_is_rejected_and_reported(scenario):
    with pytest.warns(UserWarning, match="dangling"):
        result = ap.verify_observation_resolution(
            advisory=scenario["advisory"], context=scenario["context"],
            observations=[])
    assert result is False


def test_i7_14_two_observations_sharing_an_id_are_rejected_as_ambiguous(scenario):
    duplicate = scenario["observation"].model_copy(update={"tool_name": "other.read"})
    with pytest.warns(UserWarning, match="ambiguous"):
        result = ap.verify_observation_resolution(
            advisory=scenario["advisory"], context=scenario["context"],
            observations=[scenario["observation"], duplicate])
    assert result is False


def test_i7_14_an_observation_substituted_to_another_tenant_is_rejected(scenario):
    substituted = scenario["observation"].model_copy(update={"tenant_id": "tenant-2"})
    with pytest.warns(UserWarning, match="tenant"):
        result = ap.verify_observation_resolution(
            advisory=scenario["advisory"], context=scenario["context"],
            observations=[substituted])
    assert result is False


def test_i7_14_an_observation_substituted_to_another_case_is_rejected(scenario):
    substituted = scenario["observation"].model_copy(update={"case_ref": "case-2"})
    with pytest.warns(UserWarning, match="case"):
        result = ap.verify_observation_resolution(
            advisory=scenario["advisory"], context=scenario["context"],
            observations=[substituted])
    assert result is False


def test_i7_14_an_observation_with_a_source_ref_outside_allowed_record_refs_is_rejected(
        scenario):
    substituted = scenario["observation"].model_copy(update={"source_ref": "record-2"})
    with pytest.warns(UserWarning, match="source_ref"):
        result = ap.verify_observation_resolution(
            advisory=scenario["advisory"], context=scenario["context"],
            observations=[substituted])
    assert result is False


def test_i7_14_an_unreferenced_extra_observation_is_reported_but_not_a_failure(
        scenario):
    extra = scenario["observation"].model_copy(update={"observation_id": "obs-extra"})
    with pytest.warns(UserWarning, match="unreferenced"):
        result = ap.verify_observation_resolution(
            advisory=scenario["advisory"], context=scenario["context"],
            observations=[scenario["observation"], extra])
    assert result is True


def test_i7_14_an_empty_refs_candidate_cannot_vacuously_pass_a_dangling_reference_elsewhere(
        scenario):
    """The candidate-content half of I7.14. Two nested candidates: one with an
    empty ``observation_refs`` — which alone would make the required list empty
    and the check vacuously true — and one with a genuinely dangling reference.
    The dangling reference must still be caught; the empty-refs candidate must
    not be usable to short-circuit the check for the other one."""
    empty_refs_candidate = ap.CandidateAdvisory(
        candidate_id="cand-a", disposition=ap.CandidateDisposition.RECOMMEND_WITHHOLD,
        requested_review_action=ap.ReviewAction.ROUTE_APPROVAL_BUNDLE, is_eligible=True,
        evaluated_at=FIXED_INSTANT, observation_refs=[])
    dangling_candidate = ap.CandidateAdvisory(
        candidate_id="cand-b", disposition=ap.CandidateDisposition.RECOMMEND_WITHHOLD,
        requested_review_action=ap.ReviewAction.ROUTE_APPROVAL_BUNDLE, is_eligible=True,
        evaluated_at=FIXED_INSTANT, observation_refs=["obs-missing"])
    # Neither replacement candidate is evaluated, so the qualifying pool is empty and
    # selection-policy v1 selects nothing; the selection fields go with it.
    advisory = _revalidated(
        scenario["advisory"], candidates=(empty_refs_candidate, dangling_candidate),
        domain_evaluation_profile_id=None, domain_evaluation_profile_version=None,
        selected_candidate_id=None, selection_policy_id=None,
        selection_policy_version=None, recommended_disposition=None,
        requested_review_action=None, requested_review_destination_role_ref=None)
    with pytest.warns(UserWarning, match="dangling"):
        result = ap.verify_observation_resolution(
            advisory=advisory, context=scenario["context"], observations=[])
    assert result is False


def test_i7_14_verify_advisory_selection_returns_false_whenever_observation_resolution_does(
        scenario):
    with pytest.warns(UserWarning):
        result = ap.verify_advisory_selection(
            advisory=scenario["advisory"], candidate_set=scenario["candidate_set"],
            role=scenario["role"], context=scenario["context"], observations=[])
    assert result is False


# --------------------------------------------------------------------------- #
# I7.15 — revision inputs (G3)
# --------------------------------------------------------------------------- #

def _revision_kwargs(scenario, **overrides):
    kwargs = dict(
        parent=scenario["advisory"], candidate_set=scenario["candidate_set"],
        identity=scenario["identity"], role=scenario["role"],
        mandate=scenario["mandate"], context=scenario["context"],
        observations=[scenario["observation"]], claim_summaries=["revised claim"],
        observation_refs=["obs-1"], uncertainties=["revised uncertainty"],
        created_at=FIXED_INSTANT, expires_at=scenario["mandate"].expires_at,
        provider=scenario["provider"], expected_profile_id=spec.PROFILE_ID,
        expected_profile_version=spec.PROFILE_VERSION,
        requested_review_destination_role_ref="role-approver")
    kwargs.update(overrides)
    return kwargs


def test_i7_15_omitting_claim_summaries_is_refused_not_inherited(scenario):
    kwargs = _revision_kwargs(scenario)
    del kwargs["claim_summaries"]
    with pytest.raises(TypeError):
        ap.build_advisory_revision(**kwargs)


def test_i7_15_omitting_observation_refs_is_refused_not_inherited(scenario):
    kwargs = _revision_kwargs(scenario)
    del kwargs["observation_refs"]
    with pytest.raises(TypeError):
        ap.build_advisory_revision(**kwargs)


def test_i7_15_omitting_uncertainties_is_refused_not_inherited(scenario):
    kwargs = _revision_kwargs(scenario)
    del kwargs["uncertainties"]
    with pytest.raises(TypeError):
        ap.build_advisory_revision(**kwargs)


def test_i7_15_the_three_supplied_values_appear_not_the_parents(scenario):
    revision = ap.build_advisory_revision(**_revision_kwargs(
        scenario, claim_summaries=["a new claim, not the parent's"],
        uncertainties=["a new uncertainty, not the parent's"]))
    assert revision.claim_summaries == ["a new claim, not the parent's"]
    assert revision.uncertainties == ["a new uncertainty, not the parent's"]
    assert revision.claim_summaries != scenario["advisory"].claim_summaries
    payload = _unsigned_payload_for(revision)
    assert payload.claim_summaries == ["a new claim, not the parent's"]
    assert payload.uncertainties == ["a new uncertainty, not the parent's"]


def test_i7_15_continuity_fields_are_inherited_unchanged(scenario):
    revision = ap.build_advisory_revision(**_revision_kwargs(scenario))
    parent = scenario["advisory"]
    assert revision.tenant_id == parent.tenant_id
    assert revision.case_ref == parent.case_ref
    assert revision.agent_id == parent.agent_id
    assert revision.role_contract_id == parent.role_contract_id
    assert revision.mandate_id == parent.mandate_id
    assert revision.context_id == parent.context_id


def test_i7_15_advisory_version_increments_and_parent_reference_binds(scenario):
    parent = scenario["advisory"]
    revision = ap.build_advisory_revision(**_revision_kwargs(scenario))
    assert parent.advisory_version == "1"
    assert revision.advisory_version == "2"
    assert revision.parent_advisory_digest == parent.advisory_digest
    assert ap.verify_advisory_identity(advisory=revision) is True


# --------------------------------------------------------------------------- #
# I7.16 — construction-call completeness (G2)
# --------------------------------------------------------------------------- #

def test_i7_16_the_construction_calls_keyword_set_equals_the_full_field_set():
    """AST over ``identity.py``'s own source: the keyword set of the
    ``ProposerAdvisory(...)`` construction call must equal
    ``set(ProposerAdvisory.model_fields)`` exactly — no field missing, no
    keyword that is not a field. Reads the call itself, not the builder's
    result, because omitting a defaulted field constructs successfully and
    silently carries the default — the failure mode this obligation exists to
    catch."""
    tree = ast.parse((SRC / "identity.py").read_text(encoding="utf-8"),
                     filename="identity.py")
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "ProposerAdvisory"
    ]
    assert len(calls) == 1, (
        f"expected exactly one ProposerAdvisory(...) construction call in "
        f"identity.py, found {len(calls)}")
    call = calls[0]
    assert not call.args, "the construction call must be keyword-only"
    assert not any(kw.arg is None for kw in call.keywords), (
        "the construction call must not use **-unpacking, which this AST check "
        "cannot verify field-by-field")
    keywords = {kw.arg for kw in call.keywords}
    assert keywords == set(ap.ProposerAdvisory.model_fields)


# --------------------------------------------------------------------------- #
# OD-6(i)/OD-7 part 8 — what replaced C9
#
# C9 made every non-null ``selected_candidate_id`` unconstructible. It is gone, and
# what stands in its place is narrower and stronger: a selection is constructible
# exactly when selection-policy v1 produces it, carries this package's own ratified
# policy identity, and resolves to an eligible member (S-1, S-2). These tests
# discharge that handover — the reason OD-7 part 8 requires the removal and the
# replacement to land in one change set.
# --------------------------------------------------------------------------- #

def test_c9s_replacement_refuses_a_selection_the_ratified_policy_did_not_produce(
        scenario):
    """The case C9 refused outright. A caller hand-supplying a selector the policy did
    not produce is still refused — now because the recomputation disagrees, not
    because every selector is barred."""
    unevaluated = ap.CandidateAdvisory(**{
        **spec.complete_candidate(candidate_id="cand-9"), "is_eligible": True})
    with pytest.raises(pydantic.ValidationError):
        ap.AdvisoryCandidateSet(
            schema_version="1.0", tenant_id="tenant-1", created_at=FIXED_INSTANT,
            candidate_set_id="set-1", case_ref="case-1",
            candidates=(unevaluated,), selected_candidate_id="cand-9",
            selection_policy_id="agentic_proposer.deterministic_selection",
            selection_policy_version="v1", selection_reason_codes=[])


def test_c9s_replacement_accepts_the_selection_the_ratified_policy_does_produce(
        scenario):
    """The direction C9 made untestable: the lawful non-null shape is constructible."""
    built = scenario["candidate_set"]
    assert built.selected_candidate_id == "cand-1"
    assert built.selection_policy_id == "agentic_proposer.deterministic_selection"
    assert built.selection_policy_version == "v1"


def test_c9s_replacement_still_accepts_the_always_null_case(scenario):
    """Negative control. A set whose qualifying pool is empty selects nothing, and
    carries neither policy field."""
    unevaluated = ap.CandidateAdvisory(**{
        **spec.complete_candidate(candidate_id="cand-9"), "is_eligible": True})
    built = ap.AdvisoryCandidateSet(
        schema_version="1.0", tenant_id="tenant-1", created_at=FIXED_INSTANT,
        candidate_set_id="set-1", case_ref="case-1", candidates=(unevaluated,),
        selected_candidate_id=None, selection_reason_codes=[])
    assert built.selected_candidate_id is None
    assert built.selection_policy_id is None
    assert built.selection_policy_version is None


def test_c9s_replacement_refuses_a_foreign_policy_label_on_a_correct_selection(
        scenario):
    """I8.5's second half at construction: the recomputed selection matches, and the
    label names a policy this package did not ratify. Refused."""
    fields = {name: getattr(scenario["candidate_set"], name)
              for name in ap.AdvisoryCandidateSet.model_fields}
    fields["selection_policy_id"] = "someone.elses.policy"
    with pytest.raises(pydantic.ValidationError):
        ap.AdvisoryCandidateSet.model_validate(fields)


def test_c9s_replacement_refuses_a_selection_with_no_policy_identity(scenario):
    """The coupling's other direction: a selection with no policy identity at all."""
    fields = {name: getattr(scenario["candidate_set"], name)
              for name in ap.AdvisoryCandidateSet.model_fields}
    fields["selection_policy_id"] = None
    fields["selection_policy_version"] = None
    with pytest.raises(pydantic.ValidationError):
        ap.AdvisoryCandidateSet.model_validate(fields)


def test_model_construct_bypasses_the_replacement_but_a_later_validate_catches_it(
        scenario):
    """The disclosed ceiling, unchanged from what C7 and C9 each stated of themselves:
    ``model_construct`` alone bypasses every validator, and this package neither
    claims nor attempts to close that pydantic primitive. A subsequent revalidation
    does catch it."""
    unevaluated = ap.CandidateAdvisory(**{
        **spec.complete_candidate(candidate_id="cand-9"), "is_eligible": True})
    forged = ap.AdvisoryCandidateSet.model_construct(
        schema_version="1.0", tenant_id="tenant-1", created_at=FIXED_INSTANT,
        candidate_set_id="set-1", case_ref="case-1", candidates=(unevaluated,),
        selected_candidate_id="cand-9", selection_reason_codes=[])
    assert forged.selected_candidate_id == "cand-9"
    with pytest.raises(pydantic.ValidationError):
        ap.AdvisoryCandidateSet.model_validate(dict(forged))


def test_model_copy_update_also_bypasses_the_replacement_a_second_ceiling(scenario):
    """``model_copy(update=...)`` never re-runs validation either, on a frozen model or
    otherwise. Pydantic's own documented behaviour, disclosed rather than papered over
    with an unsupported interception this package adds nowhere else."""
    copied = scenario["candidate_set"].model_copy(
        update={"selected_candidate_id": "cand-not-real"})
    assert copied.selected_candidate_id == "cand-not-real"
    assert ap.verify_deterministic_selection(candidate_set=copied) is False


def test_removing_the_recomputation_would_let_the_forbidden_selection_through(
        scenario):
    """Mutation control, on the same shape the C9 version used. A twin model declaring
    the identical fields but omitting the recomputation accepts exactly what
    ``AdvisoryCandidateSet`` rejects — proving the validator, and not the field's
    ``str | None`` type, is what blocks an unproduced selector."""
    from typing import Optional

    from ugence_agentic_proposer import contracts as c

    class _AdvisoryCandidateSetWithoutTheRecomputation(pydantic.BaseModel):
        model_config = c._MODEL_CONFIG
        schema_version: str = "1.0"
        tenant_id: c.Identifier
        created_at: object
        candidate_set_id: c.Identifier
        case_ref: c.Identifier
        candidates: tuple
        domain_evaluation_profile_id: Optional[c.Token] = None
        domain_evaluation_profile_version: Optional[c.Token] = None
        selected_candidate_id: Optional[c.Identifier] = None
        selection_policy_id: Optional[c.Token] = None
        selection_policy_version: Optional[c.Token] = None
        selection_reason_codes: c.Reserved = []

    unevaluated = ap.CandidateAdvisory(**{
        **spec.complete_candidate(candidate_id="cand-9"), "is_eligible": True})
    with pytest.raises(pydantic.ValidationError):
        ap.AdvisoryCandidateSet(
            schema_version="1.0", tenant_id="tenant-1", created_at=FIXED_INSTANT,
            candidate_set_id="set-1", case_ref="case-1", candidates=(unevaluated,),
            selected_candidate_id="cand-9",
            selection_policy_id=c.SELECTION_POLICY_ID,
            selection_policy_version=c.SELECTION_POLICY_VERSION,
            selection_reason_codes=[])

    twin = _AdvisoryCandidateSetWithoutTheRecomputation(
        tenant_id="tenant-1", created_at=FIXED_INSTANT, candidate_set_id="set-1",
        case_ref="case-1", candidates=(unevaluated,),
        selected_candidate_id="cand-9")
    assert twin.selected_candidate_id == "cand-9"


def test_build_proposer_advisory_refuses_a_forged_set_rather_than_leaking_it(scenario):
    """The only route that can still reach the builder with an unlawful selection is a
    ``model_construct``-forged set. Under C9 the builder derived ``None`` regardless;
    now that it derives faithfully, it must refuse rather than carry the forged value
    into ``P_unsigned``. ``verify_deterministic_selection`` is what catches it."""
    forged_set = scenario["candidate_set"].model_copy(
        update={"selected_candidate_id": "cand-not-real"})
    with pytest.raises(ap.DomainEvaluationProviderError):
        ap.build_proposer_advisory(
            tenant_id="tenant-1", case_ref="case-1", created_at=FIXED_INSTANT,
            identity=scenario["identity"], role=scenario["role"],
            mandate=scenario["mandate"], context=scenario["context"],
            observations=[scenario["observation"]], candidate_set=forged_set,
            parent_advisory_digest=None, claim_summaries=[], observation_refs=[],
            uncertainties=[], expires_at=scenario["mandate"].expires_at,
            provider=scenario["provider"], expected_profile_id=spec.PROFILE_ID,
            expected_profile_version=spec.PROFILE_VERSION,
            requested_review_destination_role_ref="role-approver")


def test_no_separate_refusal_remains_in_construct_advisory_source():
    """Static confirmation that C9's pre-OD-6(i) builder-side refusal text never came
    back: a reviewer reading ``identity.py`` should not find a second, now-dead copy
    of a selection ceiling sitting beside the real machinery."""
    source = (SRC / "identity.py").read_text(encoding="utf-8")
    assert "cannot derive an advisory from a" not in source, (
        "the pre-OD-6(i) builder-side refusal text is present in identity.py")


def test_c7_and_c9_are_gone_from_source_together(scenario):
    """I8.7's same-change-set discipline, as far as one runtime test can reach it.

    I8.7 is explicitly a review-time obligation that no single runtime test can
    enforce alone. What *is* mechanically checkable is the pair: neither ceiling's
    refusal remains in ``contracts.py``, and every replacement the amendment names is
    present. A commit removing one ceiling without the replacement surface fails here.
    """
    source = (SRC / "contracts.py").read_text(encoding="utf-8")
    assert "DomainCheckCompletion.COMPLETE is unconstructible in S1" not in source
    assert "must be None in S1 (C9" not in source
    for replacement in (
            "domain_evaluation_outcome", "domain_evaluation_profile_id",
            "selection_policy_id", "check_deterministic_selection",
            "selection_policy_v1", "qualifying_pool", "DomainEvaluationProvider",
            "DomainEvaluationRequest", "DomainEvaluationResponse"):
        assert replacement in source, replacement
    assert ap.DomainEvaluationOutcome is not None
    assert ap.verify_domain_evaluation is not None
    assert ap.verify_deterministic_selection is not None


# --------------------------------------------------------------------------- #
# OD-6(ii) — CrossContractViolationError: the ratified cross-contract residue
# --------------------------------------------------------------------------- #

def _od6_ii_call(**overrides):
    """``build_proposer_advisory``'s full keyword set, built from ``scenario`` with
    zero or more contracts swapped out, so each cross-contract test mutates exactly
    the one relationship it names."""
    def call(scenario):
        kwargs = dict(
            tenant_id="tenant-1", case_ref="case-1", created_at=FIXED_INSTANT,
            identity=scenario["identity"], role=scenario["role"],
            mandate=scenario["mandate"], context=scenario["context"],
            observations=[scenario["observation"]],
            candidate_set=scenario["candidate_set"], parent_advisory_digest=None,
            claim_summaries=[], observation_refs=[], uncertainties=[],
            expires_at=scenario["mandate"].expires_at,
            provider=scenario["provider"], expected_profile_id=spec.PROFILE_ID,
            expected_profile_version=spec.PROFILE_VERSION,
            requested_review_destination_role_ref="role-approver")
        kwargs.update(overrides)
        return ap.build_proposer_advisory(**kwargs)
    return call


def test_od6_ii_r5_tenant_mismatch_on_role_raises_cross_contract_violation_error(
        scenario):
    bad_role = scenario["role"].model_copy(update={"tenant_id": "tenant-2"})
    with pytest.raises(ap.CrossContractViolationError):
        _od6_ii_call(role=bad_role)(scenario)


def test_od6_ii_r5_tenant_mismatch_on_an_observation_raises_cross_contract_violation_error(
        scenario):
    bad_observation = scenario["observation"].model_copy(
        update={"tenant_id": "tenant-2"})
    with pytest.raises(ap.CrossContractViolationError):
        _od6_ii_call(observations=[bad_observation])(scenario)


def test_od6_ii_r6_case_ref_mismatch_on_mandate_raises_cross_contract_violation_error(
        scenario):
    bad_mandate = scenario["mandate"].model_copy(update={"case_ref": "case-2"})
    with pytest.raises(ap.CrossContractViolationError):
        _od6_ii_call(mandate=bad_mandate)(scenario)


def test_od6_ii_r6_case_ref_mismatch_on_an_observation_raises_cross_contract_violation_error(
        scenario):
    bad_observation = scenario["observation"].model_copy(update={"case_ref": "case-2"})
    with pytest.raises(ap.CrossContractViolationError):
        _od6_ii_call(observations=[bad_observation])(scenario)


def test_od6_ii_r9_envelope_mandate_mismatch_raises_cross_contract_violation_error(
        scenario):
    bad_context = scenario["context"].model_copy(update={"mandate_id": "mandate-2"})
    with pytest.raises(ap.CrossContractViolationError):
        _od6_ii_call(context=bad_context)(scenario)


def test_od6_ii_r10_role_binding_mismatch_raises_cross_contract_violation_error(
        scenario):
    bad_role = scenario["role"].model_copy(update={"role_contract_id": "role-2"})
    with pytest.raises(ap.CrossContractViolationError):
        _od6_ii_call(role=bad_role)(scenario)


def test_od6_ii_r7_a_dangling_observation_reference_raises_cross_contract_violation_error(
        scenario):
    with pytest.raises(ap.CrossContractViolationError):
        _od6_ii_call(observation_refs=["no-such-observation"])(scenario)


def test_od6_ii_cross_contract_violation_error_is_a_valueerror_subclass():
    assert issubclass(ap.CrossContractViolationError, ValueError)
    assert not issubclass(ap.EligibilityMismatchError, ap.CrossContractViolationError)
    assert not issubclass(ap.CrossContractViolationError, ap.EligibilityMismatchError)


def test_od6_ii_eligibility_mismatch_error_is_preserved_not_reclassified(scenario):
    """OD-6(ii) adds a fourth H2 class; it does not touch the third. A stored
    ``is_eligible`` mismatch still raises exactly ``EligibilityMismatchError``, never
    ``CrossContractViolationError``."""
    forged = ap.CandidateAdvisory.model_construct(
        **{**_ineligible_candidate_fields(), "is_eligible": True})
    forged_set = scenario["candidate_set"].model_copy(update={"candidates": (forged,)})
    with pytest.raises(ap.EligibilityMismatchError) as excinfo:
        _od6_ii_call(candidate_set=forged_set)(scenario)
    assert not isinstance(excinfo.value, ap.CrossContractViolationError)


def test_od6_ii_build_advisory_revisions_own_continuity_checks_stay_plain_valueerror(
        scenario):
    """``build_advisory_revision``'s parent-continuity checks (G3) are a different
    rule from R-5/R-6/R-7/R-9/R-10: they compare a new input against the *parent
    advisory's own stored field*, not two independently supplied contracts to the
    same call, and OD-6(ii) does not reclassify them. They must keep raising a plain
    ``ValueError`` that is not a ``CrossContractViolationError``."""
    other_identity = scenario["identity"].model_copy(update={"agent_id": "agent-2"})
    with pytest.raises(ValueError) as excinfo:
        ap.build_advisory_revision(
            parent=scenario["advisory"], candidate_set=scenario["candidate_set"],
            identity=other_identity, role=scenario["role"],
            mandate=scenario["mandate"], context=scenario["context"],
            observations=[scenario["observation"]], claim_summaries=[],
            observation_refs=[], uncertainties=[], created_at=FIXED_INSTANT,
            expires_at=scenario["mandate"].expires_at,
            provider=scenario["provider"], expected_profile_id=spec.PROFILE_ID,
            expected_profile_version=spec.PROFILE_VERSION,
            requested_review_destination_role_ref="role-approver")
    assert not isinstance(excinfo.value, ap.CrossContractViolationError)
    assert not isinstance(excinfo.value, pydantic.ValidationError)


#: The one R-1b clause that acquired a builder raise site when OD-7 made selection
#: reachable. R-1b(vii)'s **non-local half** — the selected candidate's
#: ``requested_review_action`` must be a member of ``CognitiveRoleContract.permitted_
#: review_actions`` — compares the advisory against a separately supplied role, so it
#: is not decidable from the advisory alone and H2 leaves it to
#: ``CrossContractViolationError``. Under C9 no selection existed, so the clause was
#: unreachable and the builder needed no raise site for it; it is reachable now.
_R1B_CLAUSE_WITH_A_RAISE_SITE = "R-1b(vii)"


def test_od6_ii_r1b_cross_contract_clauses_hold_by_construction_not_by_a_raise():
    """What OD-6's own ADR text says conceptually — that R-1b's cross-contract
    clauses fall under the same exception class — is not the same as a raise site
    existing for them in the builder. For R-1b(i)-(iv), (viii) and (ix) there still is
    none: the advisory's nested ``candidates`` and its selection-dependent fields are
    derived directly from ``candidate_set`` rather than separately supplied and
    compared, so those clauses hold by construction on every path
    ``build_proposer_advisory`` and ``build_advisory_revision`` support.

    Exactly one clause is exempt, and it is named rather than left implicit: see
    ``_R1B_CLAUSE_WITH_A_RAISE_SITE``. Pinning the exemption by equality is the point —
    a second clause acquiring a raise site fails here rather than being absorbed.
    """
    source = (SRC / "identity.py").read_text(encoding="utf-8")
    tree = ast.parse(source, filename="identity.py")
    named = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and node.exc is not None:
            text = ast.unparse(node.exc)
            if "CrossContractViolationError" in text and "R-1b" in text:
                named.update(re.findall(r"R-1b\(?[ivx]*\)?", text))
    assert named == {_R1B_CLAUSE_WITH_A_RAISE_SITE}, (
        f"CrossContractViolationError raise sites in identity.py name {sorted(named)}; "
        f"only {_R1B_CLAUSE_WITH_A_RAISE_SITE} is ratified to have one")


# --------------------------------------------------------------------------- #
# OD-6(iii) — ProposerProcessState membership and R-4's comparison basis
# --------------------------------------------------------------------------- #

def test_od6_iii_proposerprocessstate_has_exactly_the_nine_ratified_members():
    names = {member.name for member in ap.ProposerProcessState}
    assert names == {
        "RECEIVED", "VALIDATED", "OBSERVING", "RECONCILING", "EVALUATING",
        "PROPOSAL", "NEED_EVIDENCE", "ABSTAIN", "ESCALATE",
    }
    assert len(ap.ProposerProcessState) == 9


def test_od6_iii_the_four_terminal_members_share_terminaloutcomes_wire_values():
    for name in ("PROPOSAL", "NEED_EVIDENCE", "ABSTAIN", "ESCALATE"):
        assert ap.ProposerProcessState[name].value == ap.TerminalOutcome[name].value


def test_od6_iii_r4_compares_by_value_agreement_is_accepted_disagreement_is_rejected(
        scenario):
    agreeing = ap.ProposerProcessRecord(**_record_fixture(
        state_transitions=[_t(ap.ProposerProcessState.ABSTAIN)],
        terminal_outcome=ap.TerminalOutcome.ABSTAIN))
    assert agreeing.terminal_outcome is ap.TerminalOutcome.ABSTAIN

    with pytest.raises(pydantic.ValidationError):
        ap.ProposerProcessRecord(**_record_fixture(
            state_transitions=[_t(ap.ProposerProcessState.ABSTAIN)],
            terminal_outcome=ap.TerminalOutcome.ESCALATE))


def test_od6_iii_strict_mode_still_refuses_a_cross_enum_substitution():
    """The shared wire values settle only what R-4 compares (OD-6(iii)); they do not
    weaken either field's own type. `strict=True` still refuses a `TerminalOutcome`
    where `ProposerProcessState` is required, and the converse."""
    with pytest.raises(pydantic.ValidationError):
        ap.ProposerProcessStateTransition(state=ap.TerminalOutcome.ABSTAIN,
                                          at=FIXED_INSTANT)


def test_od6_iii_both_enums_serialise_identically_on_the_four_value_overlap():
    """All four terminal names, on the ``ProposerProcessStateTransition.state`` side
    (a standalone nested shape; V13/B3 does not reach it)."""
    for name in ("PROPOSAL", "NEED_EVIDENCE", "ABSTAIN", "ESCALATE"):
        transition = ap.ProposerProcessStateTransition(
            state=ap.ProposerProcessState[name], at=FIXED_INSTANT)
        outcome = ap.TerminalOutcome[name]
        assert transition.model_dump(mode="json")["state"] == name
        assert outcome.value == name


def test_od6_iii_the_record_side_serialises_identically_for_every_reachable_terminal(
        scenario):
    """The three terminal names V13/B3 leave reachable on ``ProposerProcessRecord``
    in S1 (``PROPOSAL`` is excluded by C7's own unreachability, not by this rule),
    each pinned as a ``(transition, record)`` pair whose serialisations agree."""
    for name in ("NEED_EVIDENCE", "ABSTAIN", "ESCALATE"):
        transition = _t(ap.ProposerProcessState[name])
        record = ap.ProposerProcessRecord(**_record_fixture(
            state_transitions=[transition], terminal_outcome=ap.TerminalOutcome[name]))
        transition_json = transition.model_dump(mode="json")["state"]
        record_json = record.model_dump(mode="json")["terminal_outcome"]
        assert transition_json == record_json == name
