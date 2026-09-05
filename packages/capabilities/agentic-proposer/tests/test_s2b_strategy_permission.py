"""S2-B — Reasoning Strategy Permission, behaviourally.

Discharges the coverage the S2-B change set owes, over the **production** surface:

* the vocabulary pinned by equality — three members, no more, no default, no escape;
* each of ``verify_strategy_permission``'s **six** checks failing **independently**,
  so no check is carried by another;
* a **forged** process record rejected by replay;
* `S2B-S1-Q12=A`'s **construction order**, proven by two stubs sharing an order log:
  an unpermitted run never reaches the injected domain evaluator;
* the three new advisory fields **inside** ``P_unsigned``, each mutation changing the
  advisory identity, which is `S2B-D6=B1`'s proposal-bound guarantee;

Test **names** here deliberately avoid ``SUSPECT_DEF_SUBSTRINGS``. D2's text scan
(``tests/test_no_local_canonicalization.py``) hunts those substrings in definition names
everywhere outside the one module I1 exempts, and it is right to: this module computes
no identity and defines no such function, so the names read the way they do rather than
the guard being narrowed to accommodate them.
* `S2B-D5=A`'s **structural** failure semantics: no artifact, ``False`` at replay, and
  **no disposition and no reserved authority term** anywhere near either.

`[R]` **What none of this establishes.** Nothing here proves a model's private
reasoning became deterministic, that the producer internally followed the token it
declared, or that the declared procedure was *executed*. The S2-B ADR's §6 is the
standard and this module does not widen it. Every resolver here is a **stub**, on the
``DomainEvaluationProvider`` precedent, because this package owns the protocol and
implements no resolver — not because none exists. A concrete resolver and a policy
family now live in separate integration distributions outside this package, and the
end-to-end proof belongs to them; nothing here depends on either, and these guards run
with no policy authority present anywhere.
"""
from __future__ import annotations

from datetime import timedelta

import pydantic
import pytest

import ugence_agentic_proposer as ap
import s1_specification_mirror as spec

FIXED_INSTANT = spec.FIXED_INSTANT
LATER = FIXED_INSTANT + timedelta(days=365)


# --------------------------------------------------------------------------- #
# A complete lawful world, built through the ratified builders only
# --------------------------------------------------------------------------- #

def _world(*, provider=None, resolver=None, declared=None, parent=None):
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
        normalized_fields={"vendor.name": "Acme Corp"})
    provider = provider or spec.StubDomainEvaluationProvider()
    resolver = resolver or spec.StubStrategyPolicyResolver()
    candidate = ap.build_candidate_advisory(
        candidate_id="cand-1", identity=identity, role=role, mandate=mandate,
        context=context, observations=[observation],
        disposition=ap.CandidateDisposition.RECOMMEND_WITHHOLD,
        requested_review_action=ap.ReviewAction.ROUTE_APPROVAL_BUNDLE,
        observation_refs=["obs-1"], claim_refs=[], assumptions=[], uncertainties=[],
        evaluated_at=FIXED_INSTANT, provider=provider,
        profile_id=spec.PROFILE_ID, profile_version=spec.PROFILE_VERSION)
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
        parent_advisory_digest=parent, claim_summaries=[], observation_refs=[],
        uncertainties=[], expires_at=LATER, provider=provider,
        expected_profile_id=spec.PROFILE_ID,
        expected_profile_version=spec.PROFILE_VERSION,
        requested_review_destination_role_ref="role-approver",
        strategy_policy_resolver=resolver,
        constitution_resolution=spec.StubConstitutionResolution(),
        declared_strategy=(declared
                           or ap.ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED))
    record = ap.build_proposer_process_record(
        process_record_id="rec-1", tenant_id="tenant-1", case_ref="case-1",
        created_at=FIXED_INSTANT, advisory=advisory, state_transitions=[],
        tool_invocations=[], candidate_ids=["cand-1"],
        selected_candidate_id="cand-1",
        terminal_outcome=ap.TerminalOutcome.PROPOSAL,
        started_at=FIXED_INSTANT, completed_at=FIXED_INSTANT)
    return dict(identity=identity, role=role, mandate=mandate, context=context,
                observation=observation, candidate=candidate, provider=provider,
                resolver=resolver, candidate_set=candidate_set, advisory=advisory,
                record=record, policy=spec.strategy_policy_response())


@pytest.fixture(scope="module")
def world():
    return _world()


def _builder_kwargs(world, **overrides):
    """``build_proposer_advisory``'s full keyword set, so each probe varies exactly
    the one thing it names."""
    kwargs = dict(
        tenant_id="tenant-1", case_ref="case-1", created_at=FIXED_INSTANT,
        identity=world["identity"], role=world["role"], mandate=world["mandate"],
        context=world["context"], observations=[world["observation"]],
        candidate_set=world["candidate_set"], parent_advisory_digest=None,
        claim_summaries=[], observation_refs=[], uncertainties=[], expires_at=LATER,
        provider=world["provider"], expected_profile_id=spec.PROFILE_ID,
        expected_profile_version=spec.PROFILE_VERSION,
        requested_review_destination_role_ref="role-approver",
        strategy_policy_resolver=world["resolver"],
        constitution_resolution=spec.StubConstitutionResolution(),
        declared_strategy=ap.ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED)
    kwargs.update(overrides)
    return kwargs


# --------------------------------------------------------------------------- #
# `S2B-R2-Q1=A` — the vocabulary, pinned by equality
# --------------------------------------------------------------------------- #

def test_the_vocabulary_has_exactly_three_members_pinned_by_equality():
    """Pinned by **equality**, not by containment: a fourth member fails here.

    `[R]` The three tile every lawful advisory, so `S2B-R2-Q4`'s disclosed forward cost
    is that no fourth can simply be added — it would overlap one of the three, contradict
    the disjoint-and-exhaustive property `S2B-R2-Q1=A` ratifies, and leave the
    shape-derived comparison with no unique answer. The owner acknowledged that cost in
    ratifying `S2B-R2-Q8=A`, and this equality is where a later addition surfaces it.
    """
    assert {m.name for m in ap.ReasoningStrategy} == {
        "SINGLE_CANDIDATE_UNREVISED", "MULTI_CANDIDATE_UNREVISED", "REVISED_ADVISORY"}
    assert len(ap.ReasoningStrategy) == 3


def test_every_member_value_equals_its_name_and_the_enum_is_a_str_enum():
    for member in ap.ReasoningStrategy:
        assert member.value == member.name
    assert issubclass(ap.ReasoningStrategy, str)


@pytest.mark.parametrize("barred", ["OTHER", "UNSPECIFIED", "NONE", "DEFAULT"])
def test_there_is_no_default_and_no_escape_member(barred):
    """`S2B-S1-Q1=A`: no default member and no escape member. A producer that cannot
    name one of the three has not produced a lawful advisory."""
    assert barred not in {m.name for m in ap.ReasoningStrategy}


@pytest.mark.parametrize("rejected", [
    "STAGED_DECOMPOSITION", "SELF_CRITIQUE", "REFLECTION", "TOOL_AUGMENTED",
    "EXTENDED_REASONING"])
def test_the_four_recorded_rejections_are_inadmissible(rejected):
    """`S2B-R2-Q2=A`. Each is rejected for a stated reason: no observable stages exist;
    private model behaviour; evidence collection, an OD-5 exclusion by name; and a model
    capability tier barred by `S2B-D2=A` that is also a compute claim."""
    assert rejected not in {m.name for m in ap.ReasoningStrategy}


def test_no_member_is_a_reserved_authority_term():
    """D4's standing bar. The vocabulary names artifact shapes; it claims no authority."""
    for member in ap.ReasoningStrategy:
        assert member.value not in ap.RESERVED_AUTHORITY_VOCABULARY


def test_no_member_carries_a_condition_on_the_selector():
    """`S2B-R2-Q1=A`, behaviourally. Under OD-8 more than one qualifying candidate
    produces **no** selection, so a lawful multi-candidate advisory may carry a null
    selector; a selector condition would leave it matching no member.

    Asserted against the derivation itself: two advisories that differ only in their
    selector yield the same token.
    """
    from ugence_agentic_proposer import contracts as c

    world = _world()
    selecting = world["advisory"]
    unselected = selecting.model_construct(**{
        **{n: getattr(selecting, n) for n in ap.ProposerAdvisory.model_fields},
        "selected_candidate_id": None})
    assert c.shape_derived_strategy(selecting) is c.shape_derived_strategy(unselected)


# --------------------------------------------------------------------------- #
# `S2B-D6=B1` — the three fields are inside ``P_unsigned``
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("field,value", [
    ("strategy_policy_id", "some.other.policy"),
    ("strategy_policy_version", "v2"),
    ("declared_strategy", ap.ReasoningStrategy.MULTI_CANDIDATE_UNREVISED),
])
def test_mutating_any_of_the_three_new_fields_changes_the_advisory_identity(world, field, value):
    """`S2B-D6=B1`'s **proposal-bound guarantee**, executed rather than asserted.

    Each of the three is inside ``P_unsigned``, so altering it produces a different
    identity — which is precisely what the ruling chose over the weak linked-record
    guarantee, under which the proposal digest would not bind the declaration and a
    proposal would remain digest-valid with its declaration absent, replaced or never
    produced.

    `[R]` This proves **integrity after construction, never provenance**. That the
    declaration is bound establishes it was not altered afterwards; it does not
    establish that the proper authority issued it, which is why `S2B-D7=A` requires
    package-stamping from an independently resolved policy.
    """
    advisory = world["advisory"]
    assert ap.verify_advisory_identity(advisory=advisory) is True
    assert getattr(advisory, field) != value, "the mutation must actually differ"

    mutated = advisory.model_construct(**{
        **{n: getattr(advisory, n) for n in ap.ProposerAdvisory.model_fields},
        field: value})
    assert (ap.compute_advisory_identity(advisory=mutated)
            != advisory.advisory_digest), (
        f"mutating {field!r} left the digest unchanged; it is not inside P_unsigned")
    assert ap.verify_advisory_identity(advisory=mutated) is False


def test_the_private_payload_mirrors_the_three_fields(world):
    """G2's equivalence obligation. If ``_UnsignedAdvisoryPayload`` omitted any of the
    three, they would sit inside the advisory and **outside** ``P_unsigned`` — exactly
    the shape `S2B-D6=B1` rejected — and the two models would drift apart at the point
    identity is computed."""
    from ugence_agentic_proposer import identity as identity_module

    payload_fields = set(
        identity_module._unsigned_advisory_payload_model().model_fields)
    assert payload_fields == set(ap.ProposerAdvisory.model_fields) - {"advisory_digest"}
    for field in ("strategy_policy_id", "strategy_policy_version", "declared_strategy"):
        assert field in payload_fields


# --------------------------------------------------------------------------- #
# `S2B-D7=A` — package-stamped, never caller-supplied
# --------------------------------------------------------------------------- #

def test_neither_advisory_builder_accepts_a_policy_identity_or_version_parameter():
    """`S2B-D7=A` with `S2B-S1-Q5=A`: each builder gained **exactly two** keyword-only
    parameters at `0.3.0`, and neither is a policy identity or version. Read off the
    signatures, because a caller-supplied value is not authoritative merely because it
    is structured or digest-bound — the whole point of OD-7 part 5's selector-policy
    precedent. The `OD-C1=B` amendment (`ACC-AM-2`, `0.4.0`) added **exactly one**
    more on the same discipline — ``constitution_resolution``, the injected resolved
    constitution the identity pair is stamped from — and, like the strategy pair, the
    constitution identity pair itself is barred from the signatures."""
    import inspect

    for builder, before in ((ap.build_proposer_advisory, 18),
                            (ap.build_advisory_revision, 16)):
        params = inspect.signature(builder).parameters
        assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params.values())
        assert len(params) == before + 2 + 1, (
            f"{builder.__name__} must carry S2B-S1-Q5=A's two additions plus "
            "ACC-AM-2's one, and nothing further")
        assert "strategy_policy_resolver" in params
        assert "declared_strategy" in params
        assert "constitution_resolution" in params
        for barred in ("strategy_policy_id", "strategy_policy_version",
                       "permitted_strategies", "policy",
                       "constitution_policy_id", "constitution_policy_version"):
            assert barred not in params, (
                f"{builder.__name__} accepts {barred!r}; S2B-D7=A and ACC-AM-2 "
                "package-stamp it from an independently resolved policy instead")


def test_the_stamped_identity_comes_from_the_resolver_not_from_any_caller(world):
    """The positive half. A resolver answering under a different policy identity stamps
    **that** identity onto the advisory, because the value is read off the response."""
    resolver = spec.StubStrategyPolicyResolver(
        policy_id="ugence.strategy_permission.other", policy_version="v7")
    advisory = ap.build_proposer_advisory(
        **_builder_kwargs(world, strategy_policy_resolver=resolver))
    assert advisory.strategy_policy_id == "ugence.strategy_permission.other"
    assert advisory.strategy_policy_version == "v7"


def test_the_stamped_version_is_a_string_never_a_number(world):
    """C3 bars every numeric type in this contract family at any depth. The policy
    version is carried as a string on both the response and the advisory."""
    assert isinstance(world["policy"].strategy_policy_version, str)
    assert isinstance(world["advisory"].strategy_policy_version, str)
    with pytest.raises(pydantic.ValidationError):
        ap.StrategyPolicyResponse(
            strategy_policy_id=spec.STRATEGY_POLICY_ID,
            strategy_policy_version=1,  # noqa: the point of the probe
            permitted_strategies=(ap.ReasoningStrategy.REVISED_ADVISORY,),
            strategy_policy_ref=spec.STRATEGY_POLICY_REF,
            constitution_ref=spec.CONSTITUTION_REF)


def test_the_process_record_derives_both_values_from_the_advisory(world):
    """Rider `R1`. The record builder takes neither ``declared_strategy`` nor
    ``advisory_digest``; it takes the advisory and derives both, so a caller cannot hand
    it a declaration or a digest reference that disagrees with the advisory."""
    import inspect

    params = inspect.signature(ap.build_proposer_process_record).parameters
    assert "advisory" in params
    assert "declared_strategy" not in params
    assert "advisory_digest" not in params

    record = world["record"]
    assert record.declared_strategy is world["advisory"].declared_strategy
    assert record.advisory_digest == world["advisory"].advisory_digest


# --------------------------------------------------------------------------- #
# `S2B-S1-Q12=A` — construction order
# --------------------------------------------------------------------------- #

def test_an_unpermitted_run_never_reaches_the_injected_domain_evaluator():
    """`S2B-S1-Q12=A`, the ruling's own stated reason for existing. Resolution and the
    permission test occur **before** the OD-7 evaluation sequence, so an unpermitted run
    never reaches the injected domain evaluator. `[I]` That is externally observable,
    which is why it required an owner ruling rather than an implementer's choice.

    Two stubs share one order log, so this reads the ORDER rather than merely whether
    each boundary was reached — a guard that only counted calls would not test the rule.
    """
    order = []
    provider = spec.StubDomainEvaluationProvider(log=order)
    permitting = spec.StubStrategyPolicyResolver(log=order)
    world = _world(provider=provider, resolver=permitting)

    # The candidate builder legitimately calls the provider before any advisory is
    # built, so the log is cleared and only the advisory build is observed.
    order.clear()
    refusing = spec.StubStrategyPolicyResolver(
        permitted=(ap.ReasoningStrategy.REVISED_ADVISORY,), log=order)
    with pytest.raises(ap.CrossContractViolationError):
        ap.build_proposer_advisory(**_builder_kwargs(
            world, strategy_policy_resolver=refusing,
            declared_strategy=ap.ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED))
    assert order == ["resolver"], (
        f"the unpermitted run reached further than the resolver: {order}")
    assert "provider" not in order


def test_a_permitted_run_reaches_the_resolver_first_and_then_the_evaluator():
    """The control, without which the assertion above could pass because the provider
    is never reached on **any** path."""
    order = []
    provider = spec.StubDomainEvaluationProvider(log=order)
    resolver = spec.StubStrategyPolicyResolver(log=order)
    world = _world(provider=provider, resolver=resolver)
    order.clear()
    ap.build_proposer_advisory(**_builder_kwargs(world))
    assert order[0] == "resolver", f"the resolver must be reached first: {order}"
    assert "provider" in order, "the control must actually reach the evaluator"


def test_the_resolver_receives_the_callers_own_as_of_never_a_wall_clock(world):
    """C4 holds across the new boundary: ``as_of`` is caller-supplied. The builders pass
    the advisory's own ``created_at``, so the policy consulted is the one in force at the
    instant the advisory asserts, and no ``src`` module reads a clock to decide it."""
    resolver = spec.StubStrategyPolicyResolver()
    ap.build_proposer_advisory(
        **_builder_kwargs(world, strategy_policy_resolver=resolver))
    assert len(resolver.calls) == 1
    request = resolver.calls[0]
    assert request.as_of == FIXED_INSTANT
    assert request.strategy_policy_ref == spec.STRATEGY_POLICY_REF
    assert request.tenant_id == "tenant-1"
    assert request.case_ref == "case-1"


# --------------------------------------------------------------------------- #
# `S2B-D5=A` — construction refuses, structurally, with no new exception type
# --------------------------------------------------------------------------- #

def test_an_empty_permitted_set_refuses_construction(world):
    """A policy permitting nothing permits this declaration too. `S2B-S1-Q8=A`: the
    refusal is ``CrossContractViolationError``, an existing H2 class."""
    resolver = spec.StubStrategyPolicyResolver(permitted=())
    with pytest.raises(ap.CrossContractViolationError):
        ap.build_proposer_advisory(
            **_builder_kwargs(world, strategy_policy_resolver=resolver))


def test_a_non_member_declaration_refuses_construction(world):
    resolver = spec.StubStrategyPolicyResolver(
        permitted=(ap.ReasoningStrategy.REVISED_ADVISORY,))
    with pytest.raises(ap.CrossContractViolationError):
        ap.build_proposer_advisory(
            **_builder_kwargs(world, strategy_policy_resolver=resolver))


def test_a_resolver_that_raises_refuses_construction(world):
    """The exception is **not** allowed to escape as an arbitrary third-party type:
    H2 stays at five classes (`S2B-S1-Q8=A`), so it is re-raised as an existing one."""
    resolver = spec.StubStrategyPolicyResolver(raises=RuntimeError("policy store down"))
    with pytest.raises(ap.CrossContractViolationError):
        ap.build_proposer_advisory(
            **_builder_kwargs(world, strategy_policy_resolver=resolver))


def test_an_uncorrelated_echo_refuses_construction(world):
    """The echo is correlation-checked **before use**. `[G]` It catches a resolver that
    mixed up concurrent requests, answered under a stale reference or was wired up
    wrongly; it is **not** a defence against a dishonest resolver, and must never be
    described as one."""
    resolver = spec.StubStrategyPolicyResolver(echo_ref="policy-authority/something-else")
    with pytest.raises(ap.CrossContractViolationError):
        ap.build_proposer_advisory(
            **_builder_kwargs(world, strategy_policy_resolver=resolver))


# --------------------------------------------------------------------------- #
# `S2B-PF-G=B` (`0.3.1`) — the widened resolver boundary
#
# A resolver that answers with a structurally alien object used to escape the H2
# surface as ``AttributeError`` from whichever field was read first. The boundary now
# covers the WHOLE ratified response shape, so the refusal is an existing H2 class
# wherever the object is deficient. `S2B-S1-Q8=A` still holds: no new exception type,
# and the public surface is unchanged at fifty-one names.
# --------------------------------------------------------------------------- #

class _AlienResponse:
    """Carries none of the ratified response fields."""


class _EchoOnlyResponse:
    """Carries the echo and nothing else.

    This is the probe that makes the boundary's WIDTH testable rather than assumed: it
    survives the echo comparison and is deficient three lines later, at
    ``permitted_strategies``. A guard closing only the echo access would pass the test
    above and still fail here.
    """

    strategy_policy_ref = spec.STRATEGY_POLICY_REF


class _DuckTypedResponse:
    """A lawful, complete response that is **not** a ``StrategyPolicyResponse``.

    The widened guard reads fields; it does not narrow the protocol to one concrete
    class. `S2B-S1-Q9=A` ratifies a Protocol, and this asserts the `0.3.1` change did
    not quietly turn it into a nominal type test.
    """

    strategy_policy_id = spec.STRATEGY_POLICY_ID
    strategy_policy_version = spec.STRATEGY_POLICY_VERSION
    permitted_strategies = tuple(ap.ReasoningStrategy)
    strategy_policy_ref = spec.STRATEGY_POLICY_REF


def test_a_structurally_alien_response_refuses_construction(world):
    """`S2B-PF-G=B`. Before `0.3.1` this raised ``AttributeError: 'Alien' object has no
    attribute 'strategy_policy_ref'`` — outside H2 entirely."""
    resolver = spec.StubStrategyPolicyResolver(returns=_AlienResponse())
    with pytest.raises(ap.CrossContractViolationError):
        ap.build_proposer_advisory(
            **_builder_kwargs(world, strategy_policy_resolver=resolver))


def test_a_response_carrying_only_the_echo_refuses_construction(world):
    """The same defect at a different line, closed by the same guard."""
    resolver = spec.StubStrategyPolicyResolver(returns=_EchoOnlyResponse())
    with pytest.raises(ap.CrossContractViolationError):
        ap.build_proposer_advisory(
            **_builder_kwargs(world, strategy_policy_resolver=resolver))


@pytest.mark.parametrize("missing", sorted(ap.StrategyPolicyResponse.model_fields))
def test_every_ratified_response_field_is_covered_by_the_boundary(world, missing):
    """Each field of the ratified shape, withheld on its own. The boundary is the whole
    response, so no single field's absence can escape H2 — and this fails if a later
    field is added to the contract but read outside the guard."""
    lawful = {"strategy_policy_id": spec.STRATEGY_POLICY_ID,
              "strategy_policy_version": spec.STRATEGY_POLICY_VERSION,
              "permitted_strategies": tuple(ap.ReasoningStrategy),
              "strategy_policy_ref": spec.STRATEGY_POLICY_REF}
    assert set(lawful) == set(ap.StrategyPolicyResponse.model_fields), (
        "the probe must cover exactly the ratified fields")
    del lawful[missing]
    deficient = type("DeficientResponse", (), dict(lawful))()
    resolver = spec.StubStrategyPolicyResolver(returns=deficient)
    with pytest.raises(ap.CrossContractViolationError):
        ap.build_proposer_advisory(
            **_builder_kwargs(world, strategy_policy_resolver=resolver))


def test_the_original_attribute_error_survives_as_the_cause(world):
    """The refusal does not swallow what went wrong. `[R]` The widened guard reports in
    an H2 class and preserves the underlying error as ``__cause__``, so an operator
    still sees which field the resolver failed to carry."""
    resolver = spec.StubStrategyPolicyResolver(returns=_AlienResponse())
    with pytest.raises(ap.CrossContractViolationError) as excinfo:
        ap.build_proposer_advisory(
            **_builder_kwargs(world, strategy_policy_resolver=resolver))
    cause = excinfo.value.__cause__
    assert isinstance(cause, AttributeError), (
        f"the original error must survive as __cause__, not be swallowed: {cause!r}")
    assert "strategy_policy_id" in str(cause)


def test_the_widened_boundary_does_not_narrow_the_protocol_to_one_class(world):
    """A complete duck-typed response still constructs. `0.3.1` routes a **deficient**
    response into H2; it does not make ``StrategyPolicyResponse`` a nominal
    requirement, which would be a second, unruled behaviour change."""
    resolver = spec.StubStrategyPolicyResolver(returns=_DuckTypedResponse())
    advisory = ap.build_proposer_advisory(
        **_builder_kwargs(world, strategy_policy_resolver=resolver))
    assert advisory.strategy_policy_id == spec.STRATEGY_POLICY_ID
    assert advisory.strategy_policy_version == spec.STRATEGY_POLICY_VERSION


def test_a_bare_string_declaration_is_a_plain_validation_error(world):
    """`S2B-S1-Q8=A`'s other half: a value failing its own field constraint is
    ``pydantic.ValidationError``. `S2B-R2-Q5=A` makes both ``declared_strategy`` fields
    **fail-closed at construction** by typing them as the enum.

    `[V]` The probe uses the **string spelling of a real member**, which is precisely
    the case the ruling weighed: it passes a membership test — ``ReasoningStrategy`` is
    a ``str`` enum, so the string compares equal to the member — and still fails the
    enum-typed field under ``strict=True``. That is the strictly larger invalidation
    `S2B-R2-Q5=A` accepted in exchange for catching a non-member at construction rather
    than at replay.
    """
    spelling = ap.ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED.value
    resolver = spec.StubStrategyPolicyResolver()
    assert spelling in resolver.permitted, (
        "the probe must clear the membership test, so only the typing can be what fails")
    with pytest.raises(pydantic.ValidationError):
        ap.build_proposer_advisory(
            **_builder_kwargs(world, strategy_policy_resolver=resolver,
                              declared_strategy=spelling))


def test_the_record_also_refuses_a_bare_string_declaration(world):
    """Rider `R1`'s other side, fail-closed on the same terms. The record derives its
    declaration from the advisory, so the only route to a bare string is a direct
    construction — and the retyped field refuses it there."""
    fields = {n: getattr(world["record"], n)
              for n in ap.ProposerProcessRecord.model_fields}
    fields["declared_strategy"] = ap.ReasoningStrategy.REVISED_ADVISORY.value
    with pytest.raises(pydantic.ValidationError):
        ap.ProposerProcessRecord.model_validate(fields)
    # And the S1 free-text value the field used to admit is no longer lawful at all.
    fields["declared_strategy"] = "reconcile and propose"
    with pytest.raises(pydantic.ValidationError):
        ap.ProposerProcessRecord.model_validate(fields)


def test_no_new_exception_type_was_added(world):
    """H2 stays at **five classes** (`S2B-S1-Q8=A`). This package still defines exactly
    three exceptions, and no S2-B-specific one joined them."""
    exceptions = {name for name in ap.__all__
                  if isinstance(getattr(ap, name), type)
                  and issubclass(getattr(ap, name), Exception)}
    assert exceptions == {"EligibilityMismatchError", "CrossContractViolationError",
                          "DomainEvaluationProviderError"}


@pytest.mark.parametrize("resolver_kwargs", [
    {"permitted": ()},
    {"permitted": (ap.ReasoningStrategy.REVISED_ADVISORY,)},
    {"raises": RuntimeError("policy store down")},
    {"echo_ref": "policy-authority/something-else"},
    # `S2B-PF-G=B` (`0.3.1`): the widened boundary's refusals are held to the same
    # uppercased-substring rule as every other refusal on this path.
    {"returns": _AlienResponse()},
    {"returns": _EchoOnlyResponse()},
])
def test_a_refused_construction_emits_no_disposition_and_no_authority_term(
        world, resolver_kwargs):
    """`S2B-D5=A`, asserted rather than assumed. The result is **structural**:
    construction produces no identity-bearing artifact and **no authority disposition is
    emitted**. This capability emits no denial, and ``ABSTAIN`` is never a denial.

    `[R]` Which component maps a structural permission failure to an operational outcome
    — abstention, hold, escalation or referral — is deliberately outside this scope and
    is **not ruled**, so nothing here may name one.
    """
    resolver = spec.StubStrategyPolicyResolver(**resolver_kwargs)
    with pytest.raises(ValueError) as excinfo:
        ap.build_proposer_advisory(
            **_builder_kwargs(world, strategy_policy_resolver=resolver))
    message = str(excinfo.value).upper()
    for reserved in ap.RESERVED_AUTHORITY_VOCABULARY:
        assert reserved not in message, (
            f"the refusal names the reserved authority term {reserved!r}")
    for outcome in ap.TerminalOutcome:
        assert outcome.value not in message, (
            f"the refusal names the terminal outcome {outcome.value!r}; S2B-D5=A "
            "leaves the operational mapping unruled")
    for disposition in ap.CandidateDisposition:
        assert disposition.value not in message


# --------------------------------------------------------------------------- #
# `S2B-S1-Q11=A` as amended by `S2B-R2-Q8=A` — the six replay checks
#
# Each below fails the run **independently**: the positive control passes, one check's
# input is broken, and replay returns ``False``. Without the independence, a suite could
# pass with a check silently carried by another.
# --------------------------------------------------------------------------- #

def _replay(world, **overrides):
    kwargs = dict(advisory=world["advisory"], policy=world["policy"],
                  role=world["role"], process_record=world["record"])
    kwargs.update(overrides)
    return ap.verify_strategy_permission(**kwargs)


def test_replay_passes_on_the_lawful_world(world):
    """The positive control. Every negative below is meaningful only against it."""
    assert _replay(world) is True


def test_check_1_a_policy_identity_that_does_not_match_fails(world):
    assert _replay(world, policy=spec.strategy_policy_response(
        strategy_policy_id="ugence.strategy_permission.other")) is False


def test_check_1_a_policy_version_that_does_not_match_fails(world):
    """The version is compared **as a string** (C3), and a different version is a
    different policy: a permitted set is only ever a permitted set *at a version*."""
    assert _replay(world, policy=spec.strategy_policy_response(
        strategy_policy_version="v2")) is False


def test_check_2_a_role_whose_reference_resolves_elsewhere_fails(world):
    """The role's reference must resolve to the **same** policy. The response's echo of
    the reference it was resolved under is what makes this decidable from `S2B-D8=B`'s
    four inputs without a second resolver call."""
    other_role = world["role"].model_copy(
        update={"strategy_policy_ref": "policy-authority/some-other-policy"})
    assert _replay(world, role=other_role) is False


def test_check_3_an_empty_permitted_set_fails(world):
    """A policy permitting nothing permits this declaration too. This is why
    ``StrategyPolicyResponse`` admits an empty set rather than refusing one at
    construction: a non-empty validator would move this check out of reach of the replay
    it was ratified as."""
    assert _replay(world, policy=spec.strategy_policy_response(
        permitted_strategies=())) is False


def test_check_3_is_pinned_structurally_because_its_outcome_is_subsumed(world):
    """**Disclosed: check three cannot be isolated behaviourally, and that is a property
    of the ratified check list rather than of this implementation.**

    An empty permitted set fails check four as well — nothing is a member of an empty
    set — so no input makes check three the *sole* cause of a ``False``. Deleting it
    would therefore leave every outcome-based probe in this module green. `S2B-S1-Q11=A`
    nonetheless ratifies it as a distinct check **in order**, so it is pinned here by
    reading the function's own source: the emptiness test must be present and must
    appear **before** the membership test.

    Stated rather than quietly skipped, because a suite that only appeared to cover six
    checks would be claiming more than it establishes.
    """
    import ast
    import inspect
    import textwrap

    from ugence_agentic_proposer import verification

    source = textwrap.dedent(
        inspect.getsource(verification.verify_strategy_permission))
    emptiness = source.index("if not policy.permitted_strategies")
    membership = source.index("advisory.declared_strategy not in policy.permitted_")
    assert emptiness < membership, (
        "the emptiness check must precede the membership check (S2B-S1-Q11=A's "
        "ratified order)")

    # It must be a real branch whose body returns False, not a bare expression a
    # source-order check alone would accept.
    tree = ast.parse(source)
    branches = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.UnaryOp)
        and isinstance(node.test.op, ast.Not)
        and "permitted_strategies" in ast.dump(node.test)]
    assert len(branches) == 1, "exactly one emptiness branch is expected"
    assert any(isinstance(stmt, ast.Return)
               and isinstance(stmt.value, ast.Constant)
               and stmt.value.value is False
               for stmt in branches[0].body), (
        "the emptiness check must return False, which is S2B-D5=A's structural result")


def test_check_4_a_declaration_outside_the_permitted_set_fails(world):
    """Membership is **exact codepoint equality** (`S2B-S1-Q4=A`), carried by enum
    identity. No normalizer, no casefolding, no trimming, no splitting."""
    assert world["advisory"].declared_strategy is (
        ap.ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED)
    assert _replay(world, policy=spec.strategy_policy_response(
        permitted_strategies=(ap.ReasoningStrategy.REVISED_ADVISORY,
                              ap.ReasoningStrategy.MULTI_CANDIDATE_UNREVISED))) is False


def test_check_5_a_record_whose_declaration_diverges_fails(world):
    """Rider `R1`'s equality, at replay, across two independently transported artifacts.

    `[R]` It proves correspondence between **two observable fields** — that the record
    and the advisory name the same declared strategy. It never proves conformance with
    private reasoning, and never proves the declared procedure was executed.
    """
    forged = world["record"].model_construct(**{
        **{n: getattr(world["record"], n) for n in ap.ProposerProcessRecord.model_fields},
        "declared_strategy": ap.ReasoningStrategy.REVISED_ADVISORY})
    assert forged.declared_strategy is ap.ReasoningStrategy.REVISED_ADVISORY, (
        "the forgery must actually diverge")
    assert _replay(world, process_record=forged) is False


def test_check_5_a_record_bound_to_a_different_advisory_fails(world):
    """The digest half of rider `R1`, which is what stops the declaration half being
    satisfied by a record that corresponds to some **other** advisory."""
    other = world["record"].model_construct(**{
        **{n: getattr(world["record"], n) for n in ap.ProposerProcessRecord.model_fields},
        "advisory_digest": spec.PLACEHOLDER_DIGEST})
    assert _replay(world, process_record=other) is False


def test_check_6_a_declaration_that_contradicts_the_advisorys_own_shape_fails(world):
    """`S2B-R2-Q8=A`'s amendment. This advisory has one candidate and binds no parent,
    so its shape yields ``SINGLE_CANDIDATE_UNREVISED``; a record and a policy that agree
    on ``REVISED_ADVISORY`` still fail, because the shape does not.

    Every other check is satisfied here on purpose — the policy permits the token, the
    record agrees, the identity and version match — so only the sixth can be what fails.
    """
    forged_advisory = world["advisory"].model_construct(**{
        **{n: getattr(world["advisory"], n) for n in ap.ProposerAdvisory.model_fields},
        "declared_strategy": ap.ReasoningStrategy.REVISED_ADVISORY})
    forged_record = world["record"].model_construct(**{
        **{n: getattr(world["record"], n) for n in ap.ProposerProcessRecord.model_fields},
        "declared_strategy": ap.ReasoningStrategy.REVISED_ADVISORY})
    assert _replay(world, advisory=forged_advisory,
                   process_record=forged_record) is False


def test_the_sixth_check_is_what_makes_the_conjunction_bite(world):
    """`S2B-R2-Q8=A` §2, executed. Check four gives *declared ∈ permitted*; the sixth
    gives *declared = shape-derived*; **jointly, shape-derived ∈ permitted**.

    Proven by the case only the conjunction catches: a policy that permits the declared
    token, a record that agrees with it, and an advisory whose shape yields a **different**
    token. Checks one to five all pass; replay still returns ``False``.
    """
    from ugence_agentic_proposer import contracts as c

    forged_advisory = world["advisory"].model_construct(**{
        **{n: getattr(world["advisory"], n) for n in ap.ProposerAdvisory.model_fields},
        "declared_strategy": ap.ReasoningStrategy.REVISED_ADVISORY})
    forged_record = world["record"].model_construct(**{
        **{n: getattr(world["record"], n) for n in ap.ProposerProcessRecord.model_fields},
        "declared_strategy": ap.ReasoningStrategy.REVISED_ADVISORY})
    policy = spec.strategy_policy_response(
        permitted_strategies=(ap.ReasoningStrategy.REVISED_ADVISORY,))

    # Checks 1-5 each hold on their own terms.
    assert policy.strategy_policy_id == forged_advisory.strategy_policy_id
    assert policy.strategy_policy_version == forged_advisory.strategy_policy_version
    assert world["role"].strategy_policy_ref == policy.strategy_policy_ref
    assert policy.permitted_strategies
    assert forged_advisory.declared_strategy in policy.permitted_strategies
    assert forged_record.declared_strategy is forged_advisory.declared_strategy
    assert forged_record.advisory_digest == forged_advisory.advisory_digest
    # And the shape disagrees, which is the whole of what the sixth check adds.
    assert c.shape_derived_strategy(forged_advisory) is not (
        forged_advisory.declared_strategy)
    assert _replay(world, advisory=forged_advisory, policy=policy,
                   process_record=forged_record) is False


def test_a_forged_bare_string_declaration_fails_replay_even_when_it_reads_right(world):
    """The forgery route that survives every *value* comparison, pinned deliberately.

    ``model_construct`` bypasses the enum typing, so a forged advisory can carry the
    bare **string** spelling of the correct member. Because ``ReasoningStrategy`` is a
    ``str`` enum, that string compares equal to the member — so the membership check
    (four) and the record-equality check (five) both pass. The sixth check compares by
    **enum identity**, so it does not, and replay returns ``False``.

    Fail-closed, and consistent with `S2B-R2-Q5=A`'s choice: a value that would pass a
    C5b ``Token`` and fail the enum is invalid, at construction and at replay alike.
    """
    spelling = ap.ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED.value
    forged_advisory = world["advisory"].model_construct(**{
        **{n: getattr(world["advisory"], n) for n in ap.ProposerAdvisory.model_fields},
        "declared_strategy": spelling})
    forged_record = world["record"].model_construct(**{
        **{n: getattr(world["record"], n) for n in ap.ProposerProcessRecord.model_fields},
        "declared_strategy": spelling})
    # Checks four and five are satisfied by str/enum equality — that is the point.
    assert forged_advisory.declared_strategy in world["policy"].permitted_strategies
    assert forged_record.declared_strategy == forged_advisory.declared_strategy
    assert _replay(world, advisory=forged_advisory,
                   process_record=forged_record) is False


def test_a_revision_declares_and_replays_as_revised_advisory():
    """The third member, end to end: a revision binds a parent, so its shape yields
    ``REVISED_ADVISORY`` at any candidate count, and the sixth check agrees."""
    world = _world()
    parent = world["advisory"]
    revision = ap.build_advisory_revision(
        parent=parent, candidate_set=world["candidate_set"],
        identity=world["identity"], role=world["role"], mandate=world["mandate"],
        context=world["context"], observations=[world["observation"]],
        claim_summaries=[], observation_refs=[], uncertainties=[],
        created_at=FIXED_INSTANT, expires_at=LATER, provider=world["provider"],
        expected_profile_id=spec.PROFILE_ID,
        expected_profile_version=spec.PROFILE_VERSION,
        requested_review_destination_role_ref="role-approver",
        strategy_policy_resolver=world["resolver"],
        constitution_resolution=spec.StubConstitutionResolution(),
        declared_strategy=ap.ReasoningStrategy.REVISED_ADVISORY)
    assert revision.parent_advisory_digest == parent.advisory_digest
    assert revision.declared_strategy is ap.ReasoningStrategy.REVISED_ADVISORY

    record = ap.build_proposer_process_record(
        process_record_id="rec-2", tenant_id="tenant-1", case_ref="case-1",
        created_at=FIXED_INSTANT, advisory=revision, state_transitions=[],
        tool_invocations=[], candidate_ids=["cand-1"],
        selected_candidate_id="cand-1",
        terminal_outcome=ap.TerminalOutcome.PROPOSAL,
        started_at=FIXED_INSTANT, completed_at=FIXED_INSTANT)
    assert ap.verify_strategy_permission(
        advisory=revision, policy=world["policy"], role=world["role"],
        process_record=record) is True
    # A revision that declared the unrevised token would fail the sixth check.
    assert ap.verify_strategy_permission(
        advisory=revision.model_construct(**{
            **{n: getattr(revision, n) for n in ap.ProposerAdvisory.model_fields},
            "declared_strategy": ap.ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED}),
        policy=world["policy"], role=world["role"],
        process_record=record.model_construct(**{
            **{n: getattr(record, n) for n in ap.ProposerProcessRecord.model_fields},
            "declared_strategy": ap.ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED,
        })) is False


# --------------------------------------------------------------------------- #
# H1's verifier discipline, unchanged
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("broken", ["advisory", "policy", "role", "process_record"])
def test_replay_never_raises_even_on_a_structurally_broken_input(world, broken):
    """H1's unchanged terms: the **builder** raises, the **verifier** reports, so a
    read-only auditor can inspect stored content without exception handling. That holds
    for an artifact that bypassed its own validators, and for one that is not even the
    right type."""
    assert _replay(world, **{broken: object()}) is False
    assert _replay(world, **{broken: None}) is False


def test_replay_returns_a_real_bool_and_emits_no_authority_term(world):
    """`S2B-D5=A`: replay returns ``False`` and emits **no disposition and no reserved
    authority term**. ``False`` is not a denial, and nothing downstream may read it as
    one — this capability maps a permission failure to no operational outcome, that
    mapping being deliberately unruled."""
    assert _replay(world) is True
    assert _replay(world, policy=spec.strategy_policy_response(
        permitted_strategies=())) is False
    for result in (_replay(world),
                   _replay(world, policy=spec.strategy_policy_response(
                       permitted_strategies=()))):
        assert isinstance(result, bool)
        assert result is True or result is False


def test_replay_takes_exactly_the_four_ratified_inputs():
    """`S2B-D8=B`: the ``ProposerAdvisory``, the resolved and signature-verified policy
    version, the ``CognitiveRoleContract``, and the ``ProposerProcessRecord`` for rider
    `R1`'s equality check. A fifth input would be a scope this ruling did not grant —
    a resolver, a candidate set or a stage record above all.

    `[R]` **Observable-procedure conformance replay in general remains deferred**, and
    `[G]` is blocked regardless: no component records observable reasoning stages.
    """
    import inspect

    params = inspect.signature(ap.verify_strategy_permission).parameters
    assert set(params) == {"advisory", "policy", "role", "process_record"}
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params.values())


# --------------------------------------------------------------------------- #
# Boundary hygiene — what this package does NOT own
# --------------------------------------------------------------------------- #

#: Modules `S2B-S1-Q9=A`'s boundary must never reach for. Networking, storage, service
#: discovery and plugin loading are each named because each would turn an **injected**
#: in-process callable into a mechanism this package resolves for itself — which is what
#: `S2B-D1=A` excludes it from doing.
BARRED_IMPORTS = frozenset({
    "ugence_policy_authority", "socket", "ssl", "urllib", "urllib.request", "http",
    "http.client", "requests", "httpx", "aiohttp", "sqlite3", "pickle", "shelve",
    "pkg_resources", "importlib.metadata",
})


def test_the_resolver_boundary_imports_nothing_it_is_barred_from():
    """`S2B-S1-Q9=A`: the boundary authorizes **no** networking, storage, service
    discovery or plugin-loading mechanism of any kind. Read as real imports by ``ast``,
    not as substrings — a docstring naming a barred module is documentation, and a guard
    that could not tell the two apart would fail on this package's own prose.
    """
    import ast
    import pathlib

    src = pathlib.Path(ap.__file__).resolve().parent
    for module in sorted(src.rglob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=module.name)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        offenders = {name for name in imported
                     if name in BARRED_IMPORTS
                     or any(name.startswith(f"{b}.") for b in BARRED_IMPORTS)}
        assert not offenders, f"{module.name} imports {sorted(offenders)}"


def test_this_package_implements_no_resolver():
    """`S2B-D1=A` excludes Agentic Proposer as an issuer, and `S2B-S1-Q9=A` makes the
    resolver **injected**: this package owns the protocol and implements nothing that
    satisfies it.

    The ``Protocol`` class itself is excluded — declaring the boundary is the point —
    and it is identified by being the protocol, not by name, so a renamed or a second
    concrete implementation cannot slip past.
    """
    import ugence_agentic_proposer.contracts as contracts_module

    for name in dir(contracts_module):
        obj = getattr(contracts_module, name)
        if not isinstance(obj, type) or obj is ap.StrategyPolicyResolver:
            continue
        assert not (hasattr(obj, "resolve") and getattr(obj, "_is_protocol", False)
                    is False and callable(getattr(obj, "resolve", None))), (
            f"{name} implements resolve(); this package must implement no resolver")


def test_the_protocol_is_runtime_checkable_and_the_stub_satisfies_it():
    assert isinstance(spec.StubStrategyPolicyResolver(), ap.StrategyPolicyResolver)


def test_the_two_call_shapes_are_not_contracts():
    """Neither carries a C2 common field, and neither is reachable from ``P_unsigned``
    — exactly OD-7's terms for its own boundary shapes."""
    for shape in (ap.StrategyPolicyRequest, ap.StrategyPolicyResponse):
        for common in ("schema_version", "tenant_id", "created_at"):
            if shape is ap.StrategyPolicyRequest and common == "tenant_id":
                continue  # the request legitimately carries the tenant it asks about
            assert common not in shape.model_fields, (shape.__name__, common)
    advisory_fields = set(ap.ProposerAdvisory.model_fields)
    assert not (advisory_fields & {"permitted_strategies", "as_of"})


def test_the_c6_identity_profile_is_still_frozen():
    """C6 is untouched by S2-B: ``set_paths`` and ``nfc_paths`` remain ``frozenset()``,
    so list ordering stays identity-significant and Unicode is not normalised by the
    identity function."""
    assert ap.ADVISORY_IDENTITY_SET_PATHS == frozenset()
    assert ap.ADVISORY_IDENTITY_NFC_PATHS == frozenset()


def test_nothing_in_s2b_declares_a_numeric_field():
    """C3, across the three shapes S2-B adds and the contracts it touches."""
    for model in (ap.StrategyPolicyRequest, ap.StrategyPolicyResponse,
                  ap.ProposerAdvisory, ap.CognitiveRoleContract,
                  ap.ProposerProcessRecord):
        for name, field in model.model_fields.items():
            assert field.annotation not in (int, float, complex), (model, name)
