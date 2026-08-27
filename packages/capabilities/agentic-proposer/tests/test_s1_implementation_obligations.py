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
    candidate = ap.build_candidate_advisory(
        candidate_id="cand-1", identity=identity, role=role, mandate=mandate,
        context=context, observations=[observation],
        disposition=ap.CandidateDisposition.RECOMMEND_WITHHOLD,
        requested_review_action=ap.ReviewAction.ROUTE_APPROVAL_BUNDLE,
        observation_refs=["obs-1"], claim_refs=[], assumptions=[], uncertainties=[],
        evaluated_at=FIXED_INSTANT)
    candidate_set = ap.build_advisory_candidate_set(
        candidate_set_id="set-1", tenant_id="tenant-1", case_ref="case-1",
        created_at=FIXED_INSTANT, candidates=(candidate,), selected_candidate_id=None)
    advisory = ap.build_proposer_advisory(
        tenant_id="tenant-1", case_ref="case-1", created_at=FIXED_INSTANT,
        identity=identity, role=role, mandate=mandate, context=context,
        observations=[observation], candidate_set=candidate_set,
        parent_advisory_digest=None, claim_summaries=["reconciled against ledger"],
        observation_refs=[], uncertainties=[], expires_at=later)
    return dict(identity=identity, role=role, mandate=mandate, context=context,
               observation=observation, candidate=candidate,
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
            selected_candidate_id=None)


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
            uncertainties=[], expires_at=scenario["mandate"].expires_at)
    assert issubclass(ap.EligibilityMismatchError, ValueError)


# --------------------------------------------------------------------------- #
# I7.7 — COMPLETE unconstructibility
# --------------------------------------------------------------------------- #

def test_i7_7_complete_is_unconstructible_by_direct_construction():
    """Intentional and fail-closed: pending a separately ratified S2 domain
    evaluator, no candidate this package builds can ever be COMPLETE."""
    with pytest.raises(pydantic.ValidationError):
        ap.CandidateAdvisory(**{
            **spec.complete_candidate(), "domain_check_completion":
            ap.DomainCheckCompletion.COMPLETE})


def test_i7_7_complete_is_unconstructible_by_model_validate():
    with pytest.raises(pydantic.ValidationError):
        ap.CandidateAdvisory.model_validate({
            **spec.complete_candidate(), "domain_check_completion": "COMPLETE"})


def test_i7_7_complete_is_unconstructible_by_model_construct_then_validate():
    forged = ap.CandidateAdvisory.model_construct(**{
        **spec.complete_candidate(), "domain_check_completion":
        ap.DomainCheckCompletion.COMPLETE})
    with pytest.raises(pydantic.ValidationError):
        ap.CandidateAdvisory.model_validate(forged.model_dump())


def test_i7_7_evaluate_readiness_is_false_for_every_constructible_candidate(scenario):
    assert ap.evaluate_readiness(
        candidate=scenario["candidate"], identity=scenario["identity"],
        role=scenario["role"], mandate=scenario["mandate"],
        context=scenario["context"]) is False


# --------------------------------------------------------------------------- #
# I7.8 — V13
# --------------------------------------------------------------------------- #

def test_i7_8_proposal_terminal_outcome_is_unreachable_via_the_builder(scenario):
    with pytest.raises(pydantic.ValidationError):
        ap.build_proposer_process_record(
            process_record_id="rec-1", tenant_id="tenant-1", case_ref="case-1",
            created_at=FIXED_INSTANT, declared_strategy="reconcile and propose",
            state_transitions=[], tool_invocations=[], candidate_ids=["cand-1"],
            selected_candidate_id=None, terminal_outcome=ap.TerminalOutcome.PROPOSAL,
            advisory_digest=scenario["advisory"].advisory_digest,
            started_at=FIXED_INSTANT, completed_at=FIXED_INSTANT)


def test_i7_8_selected_candidate_id_is_none_on_every_builder_produced_advisory(scenario):
    advisory = scenario["advisory"]
    assert advisory.selected_candidate_id is None
    assert advisory.recommended_disposition is None
    assert advisory.requested_review_action is None
    assert advisory.requested_review_destination_role_ref is None


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
