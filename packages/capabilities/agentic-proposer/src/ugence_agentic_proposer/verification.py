"""Part H — verifiers, and the three exceptions this package defines (H2, OD-6(ii),
OD-7).

Independent replay: each verifier recomputes from stored content, consults no cache
and no side table, and returns ``False`` rather than raising, "on the same terms" as
one another (H1). The **builder** raises; the **verifier** reports, so a read-only
auditor can inspect stored content without exception handling. OD-7's two new replay
functions keep that discipline exactly: a provider exception raised inside
``verify_domain_evaluation``'s own call is caught and reported as ``False``, so a
read-only auditor calling a verifier still never needs exception handling.
"""
from __future__ import annotations

import typing
import warnings

from .equations import evaluate_eligibility

if typing.TYPE_CHECKING:
    from .contracts import (
        AdvisoryCandidateSet,
        AgentIdentityRef,
        BoundedContextEnvelope,
        CognitiveRoleContract,
        DomainEvaluationProvider,
        ProposerAdvisory,
        ProposerProcessRecord,
        StrategyPolicyResponse,
        ToolObservation,
        WorkMandate,
    )

#: OD-7 part 5's two R-1b correspondence clauses, and the mirrored fields they govern.
#: Scoped to ``ProposerAdvisory`` and ``AdvisoryCandidateSet`` together, never to a
#: field name alone (OD-3's lesson).
MIRRORED_EVALUATION_FIELDS = (
    "domain_evaluation_profile_id",
    "domain_evaluation_profile_version",
    "selection_policy_id",
    "selection_policy_version",
)

__all__ = [
    "EligibilityMismatchError",
    "CrossContractViolationError",
    "DomainEvaluationProviderError",
    "verify_candidate_eligibility",
    "verify_advisory_selection",
    "verify_observation_resolution",
    "verify_domain_evaluation",
    "verify_deterministic_selection",
    "verify_strategy_permission",
]


class EligibilityMismatchError(ValueError):
    """H2. A stored ``is_eligible`` that does not match the recomputation.

    Not a field-validation failure: the value is well-formed and the object is
    well-typed. What failed is provenance (G4)."""


class CrossContractViolationError(ValueError):
    """H2, OD-6(ii). A Part E rule that compares fields across two or more
    independently constructed contract instances — R-5, R-6, R-7, R-9 and R-10 as
    implemented by ``identity.py``'s builders — and so cannot be decided, and cannot
    raise ``pydantic.ValidationError``, from any single model's own validator.

    Not a field-validation failure any more than ``EligibilityMismatchError`` is:
    each of the objects involved is, on its own, well-formed and well-typed. What
    failed is a relationship the builder is required to check between two or more of
    them. R-1b's own cross-contract clauses ((i)-(iv), (viii), (ix)) fall under this
    same exception conceptually, but the builder never has occasion to raise it for
    them: the advisory's nested ``candidates`` and its four selection-dependent
    fields are *derived* from the referenced ``AdvisoryCandidateSet`` rather than
    separately supplied and checked, so those clauses hold by construction on every
    path this package's builders support. ``verify_advisory_selection`` remains the
    independent replay that reports a violation of them — including one produced by
    a hand-constructed or tampered object outside the builder's own path — by
    returning ``False``, on the same terms H1 states for every verifier.
    """


class DomainEvaluationProviderError(ValueError):
    """H2's fifth class (OD-7). Raised when a provider's echoed profile identity, its
    echoed ``candidate_id``, its returned outcome, or the recorded selector-policy
    identity cannot be verified against what the request or the ratified policy
    actually specifies — or when ``provider`` itself raises during the original build.

    Not a field-validation failure, on the same grounds ``EligibilityMismatchError`` and
    ``CrossContractViolationError`` are not: every object involved is well-formed and
    well-typed on its own terms. What failed is that the provider's answer does not
    correspond to the question, or that a stored selection names a policy this package
    did not ratify.

    It exists so that a caller catches **one** named exception family for every OD-7
    construction-time failure rather than an arbitrary third-party type. Builders raise;
    verifiers report — H1's own distinction, applied here: a provider exception raised
    inside a *verifier's* replay call is caught and reported as ``False``, never
    re-raised as this class.
    """


def verify_candidate_eligibility(
    *,
    candidate_set: AdvisoryCandidateSet,
    identity: AgentIdentityRef,
    role: CognitiveRoleContract,
    mandate: WorkMandate,
    context: BoundedContextEnvelope,
    observations: list[ToolObservation],
) -> bool:
    """G4. Recomputes Equation 1 for every candidate in ``candidate_set`` and returns
    ``False`` if any stored ``is_eligible`` differs from the recomputation. Returns
    ``False`` rather than raising, so a read-only auditor can inspect a stored set
    without exception handling."""
    for candidate in candidate_set.candidates:
        recomputed = evaluate_eligibility(
            identity=identity,
            role=role,
            mandate=mandate,
            context=context,
            observations=observations,
            disposition=candidate.disposition,
            requested_review_action=candidate.requested_review_action,
            referenced_observation_ids=list(candidate.observation_refs),
            evaluated_at=candidate.evaluated_at,
        )
        if candidate.is_eligible is not recomputed:
            return False
    return True


def _resolve_references(
    *,
    required: list[str],
    tenant_id: str,
    case_ref: str,
    context: BoundedContextEnvelope,
    observations: list[ToolObservation],
) -> bool:
    """E2's replay algorithm, over an already-derived ``required`` list of
    ``observation_refs`` entries (the advisory's own, concatenated with every nested
    candidate's, in order, duplicates included). Shared by the builder (construction)
    and by ``verify_observation_resolution`` (replay), so the two cannot drift apart.
    """
    index: dict[str, list[ToolObservation]] = {}
    for observation in observations:
        index.setdefault(observation.observation_id, []).append(observation)

    for observation_id, group in index.items():
        if len(group) > 1:
            warnings.warn(
                f"observation_id {observation_id!r} is ambiguous: "
                f"{len(group)} observations share it", stacklevel=2)
            return False

    referenced_ids = set()
    for observation_id in required:
        matches = index.get(observation_id, [])
        if len(matches) == 0:
            warnings.warn(f"dangling observation reference: {observation_id!r}",
                          stacklevel=2)
            return False
        if len(matches) > 1:
            warnings.warn(f"ambiguous observation reference: {observation_id!r}",
                          stacklevel=2)
            return False
        observation = matches[0]
        referenced_ids.add(observation_id)
        if observation.tenant_id != tenant_id:
            warnings.warn(
                f"observation {observation_id!r} is outside the advisory's tenant "
                "(R-5)", stacklevel=2)
            return False
        if observation.case_ref != case_ref:
            warnings.warn(
                f"observation {observation_id!r} is outside the advisory's case "
                "(R-6)", stacklevel=2)
            return False
        if observation.source_ref not in context.allowed_record_refs:
            warnings.warn(
                f"observation {observation_id!r} has a source_ref outside "
                "BoundedContextEnvelope.allowed_record_refs", stacklevel=2)
            return False

    for observation_id in index:
        if observation_id not in referenced_ids:
            warnings.warn(
                f"observation {observation_id!r} is supplied but unreferenced; it "
                "is not advisory evidence", stacklevel=2)

    return True


def verify_observation_resolution(
    *,
    advisory: ProposerAdvisory,
    context: BoundedContextEnvelope,
    observations: list[ToolObservation],
) -> bool:
    """E2. Replays R-7 against the **complete** observation collection the caller
    holds, not a pre-filtered subset. Returns ``False`` and reports (via a warning
    naming the failing reference) on a dangling, ambiguous, duplicated or
    continuity-broken reference; an unreferenced extra observation is reported but is
    not itself a failure."""
    required = list(advisory.observation_refs)
    for candidate in advisory.candidates:
        required.extend(candidate.observation_refs)
    return _resolve_references(
        required=required, tenant_id=advisory.tenant_id, case_ref=advisory.case_ref,
        context=context, observations=observations)


def verify_advisory_selection(
    *,
    advisory: ProposerAdvisory,
    candidate_set: AdvisoryCandidateSet,
    role: CognitiveRoleContract,
    context: BoundedContextEnvelope,
    observations: list[ToolObservation],
) -> bool:
    """The independent replay of R-1b **and** R-7. A separate function from
    ``verify_advisory_identity``: identity asks whether the stored bytes are the ones
    that were signed; this asks whether what was signed agrees with the artifacts it
    references."""
    # R-1b(ix): tenant, case and candidate-set references are continuous.
    if advisory.tenant_id != candidate_set.tenant_id:
        return False
    if advisory.case_ref != candidate_set.case_ref:
        return False
    if advisory.candidate_set_id != candidate_set.candidate_set_id:
        return False

    # R-1b(i)-(iii): membership, order and content. Lengths are compared first, so a
    # shorter or longer sequence is a membership failure rather than a truncated
    # positional walk. Both sequences are `tuple[CandidateAdvisory, ...]`, so no
    # container-type mismatch can mask the comparison.
    advisory_ids = {c.candidate_id for c in advisory.candidates}
    set_ids = {c.candidate_id for c in candidate_set.candidates}
    if advisory_ids != set_ids:
        return False
    if len(advisory.candidates) != len(candidate_set.candidates):
        return False
    for left, right in zip(advisory.candidates, candidate_set.candidates):
        if left != right:
            return False

    # R-1b(iv): the two selectors agree.
    if advisory.selected_candidate_id != candidate_set.selected_candidate_id:
        return False

    # R-1b's two new correspondence clauses (OD-7 part 5): each mirrored field on the
    # advisory equals the separately transported set's. The advisory's copy is inside
    # ``P_unsigned``; the set's is not, so a divergence here is exactly the case the
    # mirroring exists to make detectable.
    for name in MIRRORED_EVALUATION_FIELDS:
        if getattr(advisory, name) != getattr(candidate_set, name):
            return False

    # OD-7 part 5: what this function's structural correspondence check does NOT do on
    # its own. Above, the two selectors are checked to agree WITH EACH OTHER; neither
    # of those checks establishes that either selector is the ratified selector's own
    # lawful output. ``verify_deterministic_selection`` is what establishes that, so it
    # is called here rather than replacing this function.
    if not verify_deterministic_selection(candidate_set=candidate_set):
        return False

    if advisory.selected_candidate_id is not None:
        # R-1b(v): the selector resolves to exactly one element of each sequence, and
        # the two are the same candidate.
        advisory_matches = [c for c in advisory.candidates
                            if c.candidate_id == advisory.selected_candidate_id]
        set_matches = [c for c in candidate_set.candidates
                      if c.candidate_id == candidate_set.selected_candidate_id]
        if len(advisory_matches) != 1 or len(set_matches) != 1:
            return False
        if advisory_matches[0] != set_matches[0]:
            return False
        candidate = advisory_matches[0]

        # R-1b(vi): recommended_disposition equals the selected nested candidate's.
        if advisory.recommended_disposition != candidate.disposition:
            return False
        # R-1b(vii): requested_review_action equals the selected nested candidate's
        # and is a member of the role's permitted set.
        if advisory.requested_review_action != candidate.requested_review_action:
            return False
        if advisory.requested_review_action not in role.permitted_review_actions:
            return False

    if not verify_observation_resolution(
            advisory=advisory, context=context, observations=observations):
        return False

    return True


# --------------------------------------------------------------------------- #
# OD-7 — the domain-evaluation boundary: request assembly, the provider call, and
# the two new replay functions
# --------------------------------------------------------------------------- #


def _evaluation_request(
    *,
    candidate_id: str,
    profile_id: str,
    profile_version: str,
    observation_refs,
    mandate: WorkMandate,
    context: BoundedContextEnvelope,
    observations: list[ToolObservation],
):
    """OD-7 part 2. Assemble the request from already-identity-bound public content
    only: the candidate under evaluation, its referenced observations, the mandate and
    context in force, and the profile evaluation is requested under.

    Shared by the builder (construction) and by ``verify_domain_evaluation`` (replay),
    so the two cannot assemble different questions and compare the answers.
    """
    from . import contracts as c

    wanted = set(observation_refs)
    return c.DomainEvaluationRequest(
        candidate_id=candidate_id,
        profile_id=profile_id,
        profile_version=profile_version,
        mandate=mandate,
        context=context,
        observations=tuple(o for o in observations if o.observation_id in wanted),
    )


def _echo_is_correlated(response, request) -> bool:
    """OD-7 part 2's request/response correlation check, stated once.

    It catches a provider that mixed up concurrent or batched requests, answered under
    a stale profile, returned a cached result for a different candidate, or was wired
    up wrongly. It is **not** a defence against a dishonest provider: one that wishes to
    mislead echoes back what it was handed while evaluating something else.
    """
    return (response.candidate_id == request.candidate_id
            and response.profile_id == request.profile_id
            and response.profile_version == request.profile_version)


def verify_domain_evaluation(
    *,
    provider: DomainEvaluationProvider,
    candidate_set: AdvisoryCandidateSet,
    mandate: WorkMandate,
    context: BoundedContextEnvelope,
    observations: list[ToolObservation],
    expected_profile_id: str,
    expected_profile_version: str,
) -> bool:
    """OD-7 part 5. Replay of every completed domain evaluation the set records.

    **Not a self-check against the set's own recorded profile.** ``expected_profile_id``
    and ``expected_profile_version`` are supplied by the caller from a source outside
    the advisory under test — the profile currently configured or ratified for this
    case — precisely so this function cannot be satisfied merely by a provider echoing
    back whatever profile identity a tampered ``AdvisoryCandidateSet`` happens to
    record.

    For every candidate whose ``domain_check_completion is COMPLETE`` it (a) checks the
    stored profile pair equals the expected pair; (b) re-issues a request carrying the
    **expected** profile and the candidate's own ``candidate_id``; and (c) checks the
    response's echoed profile, its echoed ``candidate_id`` and its outcome equal,
    respectively, the expected profile, the candidate under test, and the stored
    ``domain_evaluation_outcome``.

    ``[G]`` **Disclosed ceiling.** This proves the recorded profile matches what was
    independently expected and that invoking ``provider`` again under that profile
    reproduces the stored outcome. It does **not** and cannot prove the *original*
    evaluation was correct if ``provider`` is non-deterministic or its behaviour has
    since changed under an unchanged version label. Four further limits, each a
    consequence of what replay operates on:

    * **Candidate suppression is invisible.** Replay iterates the candidates the set
      *contains*. A candidate never added leaves no trace in ``P_unsigned`` and no
      verifier can report its absence.
    * **A profile label is not a profile.** The pair is compared by equality. Two
      providers, or one provider before and after an unversioned change to its own
      rules, can present the same label; replay then confirms agreement between two
      things that share a name and nothing more.
    * **There is no selector-policy registry** — see ``verify_deterministic_selection``.
    * **Replay proves reproducibility, never authority.** Every check here answers
      "does re-running agree with what was stored", which is a different question from
      "was the stored answer right". The provider remains the sole authority on domain
      substance.

    Returns ``False`` and never raises, on H1's unchanged terms — including for a
    malformed set that bypassed the construction-time couplings via ``model_construct``
    or ``model_copy(update=...)``, and including a provider that raises during this
    function's own replay call.
    """
    from .contracts import DomainCheckCompletion

    for candidate in candidate_set.candidates:
        if candidate.domain_check_completion is not DomainCheckCompletion.COMPLETE:
            continue
        if (candidate_set.domain_evaluation_profile_id != expected_profile_id
                or candidate_set.domain_evaluation_profile_version
                != expected_profile_version):
            return False
        try:
            request = _evaluation_request(
                candidate_id=candidate.candidate_id,
                profile_id=expected_profile_id,
                profile_version=expected_profile_version,
                observation_refs=candidate.observation_refs,
                mandate=mandate, context=context, observations=observations)
            response = provider.evaluate(request=request)
        except Exception:  # noqa: BLE001 — a verifier reports; it does not propagate.
            return False
        if response is None or not _echo_is_correlated(response, request):
            return False
        if response.outcome is not candidate.domain_evaluation_outcome:
            return False
    return True


def verify_deterministic_selection(*, candidate_set: AdvisoryCandidateSet) -> bool:
    """OD-8. Replay of selection-policy v1 over the candidate set's own members.

    Recomputes the **qualifying pool** — members that are ``is_eligible is True``
    **and** carry ``domain_evaluation_outcome is SATISFIED`` — and checks the stored
    selector against selection-policy v1: exactly one qualifying candidate requires
    ``selected_candidate_id`` to equal that candidate's identifier; zero or more than
    one requires it to be ``None``. **Selection-policy v1 does not apply the
    ``candidate_id`` tie-break**, so this function neither computes nor consults it.

    It **also** checks the stored ``selection_policy_id``/``selection_policy_version``
    equal this package's own ratified selector identity, so a ``selected_candidate_id``
    that happens to match the recomputation but is *labelled* as coming from a
    different, unratified policy still fails replay.

    ``[G]`` **Disclosed ceiling: there is no selector-policy registry.** Comparing the
    stored label against this package's own constants detects a foreign or stale label;
    it does not and cannot establish that the named policy *is* the logic that produced
    the stored selection on some other installation, because no registry maps a policy
    identity to its ratified definition. Within one installation at one version this is
    sound; across versions it degrades to a label comparison.

    Returns ``False`` and never raises, including for a set that bypassed the
    construction-time validators.
    """
    from . import contracts as c

    try:
        expected = c.selection_policy_v1(candidate_set.candidates)
        stored = candidate_set.selected_candidate_id
        if stored != expected:
            return False
        if stored is None:
            return all(getattr(candidate_set, name) is None
                       for name in c.SELECTION_POLICY_FIELDS)
        return (candidate_set.selection_policy_id == c.SELECTION_POLICY_ID
                and candidate_set.selection_policy_version
                == c.SELECTION_POLICY_VERSION)
    except Exception:  # noqa: BLE001 — a verifier reports; it does not propagate.
        return False


# --------------------------------------------------------------------------- #
# OD-7 part 7 — the fail-closed table, as one ordered, non-overlapping function
# --------------------------------------------------------------------------- #

#: The ratified outcome of each row, keyed by row number. Row 2 refuses construction
#: outright and so carries no terminal outcome; every other row names one.
FAIL_CLOSED_ROWS = {
    1: "NEED_EVIDENCE",
    2: None,
    3: "PROPOSAL",
    4: "ABSTAIN",
    5: "ABSTAIN",
    6: "ABSTAIN",
}


def classify_fail_closed_row(
    *,
    evidence_resolved: bool,
    evaluator_available: bool,
    verification_passed: bool,
    candidates,
):
    """OD-7 part 7, evaluated in the ratified order. Returns ``(row, selected_id)``.

    Every condition below is stated on the **qualifying pool** (OD-7 part 4) — never on
    the presence of an individual non-qualifying candidate. The first matching row
    governs, the rows do not overlap, and exactly one row matches any completed run, so
    no completed run falls through without a ratified outcome (OD-10, I8.15).

    ``[R]`` **OD-9's per-candidate scope is load-bearing here.** A set holding one
    eligible, ``SATISFIED`` candidate alongside any number of ``INCONCLUSIVE`` or
    ``NOT_SATISFIED`` ones matches row 3 and **selects the qualifying one**. There is no
    run-wide reading of ``INCONCLUSIVE`` in this function or anywhere else in this
    package: rows 5 and 6 are reached only when the qualifying pool is *empty*.

    Row 2 returns no terminal outcome: it refuses construction. That is a builder
    obligation (``DomainEvaluationProviderError``), not a value to record.
    """
    from . import contracts as c
    from .vocabulary import DomainEvaluationOutcome

    if not evidence_resolved or not evaluator_available:
        return 1, None
    if not verification_passed:
        return 2, None
    pool = c.qualifying_pool(candidates)
    if len(pool) == 1:
        return 3, pool[0].candidate_id
    if len(pool) > 1:
        return 4, None
    if any(candidate.domain_evaluation_outcome is DomainEvaluationOutcome.INCONCLUSIVE
           for candidate in candidates):
        return 5, None
    return 6, None


# --------------------------------------------------------------------------- #
# S2-B — proposal-bound strategy-permission replay (`S2B-D8=B`, `S2B-S1-Q11=A` as
# amended by `S2B-R2-Q8=A`)
# --------------------------------------------------------------------------- #


def verify_strategy_permission(
    *,
    advisory: ProposerAdvisory,
    policy: StrategyPolicyResponse,
    role: CognitiveRoleContract,
    process_record: ProposerProcessRecord,
) -> bool:
    """`S2B-D8=B`'s **proposal-bound** replay, over exactly its four ratified inputs:
    the ``ProposerAdvisory``, the resolved and signature-verified policy version, the
    ``CognitiveRoleContract``, and the ``ProposerProcessRecord`` for rider `R1`'s
    equality check. It reads no stage record and issues no resolver call.

    **Six checks, in the ratified order.** The first five are `S2B-S1-Q11=A`; the sixth
    is `S2B-R2-Q8=A`'s amendment, which the owner expressly approved as an amendment to
    that ruling, leaving the five standing unchanged and in order:

    1. the policy identity and version match the advisory's stamped pair;
    2. the role's reference resolves to the same policy;
    3. the permitted set is non-empty;
    4. the declared strategy is a member of it;
    5. the record's declaration **and** its ``advisory_digest`` match the advisory;
    6. the declared token equals the token the advisory's **own shape** yields.

    **What the conjunction establishes, and only this.** Check 4 gives *declared token
    ∈ permitted set*; check 6 gives *declared token = shape-derived token*; jointly,
    therefore, **shape-derived token ∈ permitted set**. `[R]` What a policy governs is
    thus the **replay-verifiable shape of the advisory**, not merely what its producer
    may declare. Neither check delivers that alone. The declared token remains
    informationally redundant — a verifier could compute it — but it is a
    **digest-bound commitment**, and the conjunction is what is enforceable. `[R]` It
    is established at **replay**, never by construction.

    **The limits are not widened, and must never be described as widened.** This
    establishes **nothing** about private reasoning; it does **not** prove that a
    declared procedure was *executed*; and it establishes **no** observable-stage
    conformance beyond what the advisory's own shape shows. `[R]` For these three
    members only, it discharges early part of what `S2B-D8=B` named a later stage —
    disclosed, not glossed. Observable-procedure conformance replay in general remains
    deferred, and `[G]` is blocked regardless: no component records observable
    reasoning stages.

    **What replay can never establish**, whatever these six checks return: hidden model
    state; private chain-of-thought; undocumented provider-side routing or fallback;
    whether a model internally used a technique a provider names; external facts not
    carried across the replay boundary; or whether omitted stages, evidence or
    candidates never existed.

    `[R]` **Digest membership proves integrity after construction, never provenance.**
    Inclusion in the identity projection establishes that a value was not altered
    afterwards; it does not establish that the proper authority issued it. Verifying
    the policy's issuer and signature through Policy Authority resolution is a
    **separate call** this function's inputs do not supply and this digest cannot.

    **Structural, and silent about outcomes.** Returns ``bool`` and **never raises**,
    on H1's unchanged terms — a read-only auditor needs no exception handling, and that
    includes an artifact that bypassed its own validators via ``model_construct`` or
    ``model_copy(update=...)``. `[R]` It emits **no disposition and no reserved
    authority term**: ``False`` is not a denial, and this capability maps a permission
    failure to no operational outcome, that mapping being deliberately unruled
    (`S2B-D5=A`).
    """
    from . import contracts as c

    try:
        # 1. The policy identity and version match the pair the advisory binds. The
        #    version is compared as a string (C3 bars every numeric type here).
        if policy.strategy_policy_id != advisory.strategy_policy_id:
            return False
        if policy.strategy_policy_version != advisory.strategy_policy_version:
            return False

        # 2. The role's reference resolves to the same policy. The response's echo of
        #    the reference it was resolved under is what makes this decidable from the
        #    four ratified inputs without a second resolver call.
        if role.strategy_policy_ref != policy.strategy_policy_ref:
            return False

        # 3. The permitted set is non-empty. A policy permitting nothing permits this
        #    declaration too, and reporting that is exactly why the response shape
        #    admits an empty set rather than refusing one at construction.
        if not policy.permitted_strategies:
            return False

        # 4. The declared strategy is a member. Exact codepoint equality
        #    (`S2B-S1-Q4=A`), carried by enum identity: no normalizer, no casefolding,
        #    no trimming, no splitting.
        if advisory.declared_strategy not in policy.permitted_strategies:
            return False

        # 5. Rider `R1`: the record's declaration AND its advisory_digest match the
        #    advisory. The digest half is what stops the declaration half being
        #    satisfied by a record that corresponds to some *other* advisory.
        if process_record.declared_strategy != advisory.declared_strategy:
            return False
        if process_record.advisory_digest != advisory.advisory_digest:
            return False

        # 6. `S2B-R2-Q8=A`. The declared token equals the token the advisory's own
        #    shape yields. This is the check that turns "what the producer may declare"
        #    into "the shape a policy governs" — and it is the whole of the amendment's
        #    perimeter: `S2B-D8=B`, `S2B-S1-Q10=A` and `S2B-D5=A` are not amended.
        if advisory.declared_strategy is not c.shape_derived_strategy(advisory):
            return False

        return True
    except Exception:  # noqa: BLE001 — a verifier reports; it does not propagate.
        return False
