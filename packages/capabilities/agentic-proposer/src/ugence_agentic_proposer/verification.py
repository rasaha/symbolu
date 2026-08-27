"""Part H — verifiers, and the two exceptions this package defines (H2, OD-6(ii)).

Independent replay: each verifier recomputes from stored content, consults no cache
and no side table, and returns ``False`` rather than raising, "on the same terms" as
one another (H1). The **builder** raises; the **verifier** reports, so a read-only
auditor can inspect stored content without exception handling.
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
        ProposerAdvisory,
        ToolObservation,
        WorkMandate,
    )

__all__ = [
    "EligibilityMismatchError",
    "CrossContractViolationError",
    "verify_candidate_eligibility",
    "verify_advisory_selection",
    "verify_observation_resolution",
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
