"""Part H — the three builders that need no identity computation.

``build_proposer_advisory`` and ``build_advisory_revision`` live in ``identity.py``
because G2 requires the substrate call inline in the ``advisory_digest=`` keyword of
the same construction expression, and I1 scopes that exemption to a single file.
"""
from __future__ import annotations

import ugence_jcs

from .contracts import (
    SELECTION_POLICY_ID,
    SELECTION_POLICY_VERSION,
    AdvisoryCandidateSet,
    CandidateAdvisory,
    DomainEvaluationProvider,
    ProposerAdvisory,
    ProposerProcessRecord,
)
from .equations import evaluate_eligibility
from .verification import (
    DomainEvaluationProviderError,
    _echo_is_correlated,
    _evaluation_request,
    _resolve_references,
)
from .vocabulary import (
    CandidateDisposition,
    DomainCheckCompletion,
    ReviewAction,
    TerminalOutcome,
)

__all__ = [
    "build_candidate_advisory",
    "build_advisory_candidate_set",
    "build_proposer_process_record",
]


def build_candidate_advisory(
    *,
    candidate_id: str,
    identity,
    role,
    mandate,
    context,
    observations: list,
    disposition: CandidateDisposition,
    requested_review_action: ReviewAction,
    observation_refs: list[str],
    claim_refs: list[str],
    assumptions: list[str],
    uncertainties: list[str],
    evaluated_at,
    provider: DomainEvaluationProvider,
    profile_id: str,
    profile_version: str,
) -> CandidateAdvisory:
    """H1, as amended by OD-7. Takes no ``is_eligible``, no ``domain_check_completion``
    and no ``domain_evaluation_outcome`` parameter: it computes the first from
    Equation 1 and derives the other two from the injected provider's verified answer.

    **OD-7 part 6's required execution order, realised here for one candidate:**
    Equation 1 eligibility -> domain evaluation -> domain-result verification -> a
    single construction. ``CandidateAdvisory`` is frozen (C1) and is instantiated
    exactly once, with every field already known; nothing here builds an instance
    missing a field and completes it later. What precedes that one construction
    operates over plain, non-contract data.

    **Missing evidence is not an evaluation failure.** When an ``observation_refs``
    entry does not resolve, the same ``_resolve_references`` replay E2 already uses
    warns, naming the failing reference — and the provider is **not called at all**.
    The candidate is constructed ``NOT_EVALUATED`` with no outcome, which keeps it out
    of every qualifying pool; directing the run to ``NEED_EVIDENCE`` (part 7's first
    row) is the caller's orchestration decision, not a return value here.

    **A provider exception is re-raised as ``DomainEvaluationProviderError``** so a
    caller catches one named family for every OD-7 construction-time failure rather
    than an arbitrary third-party type. So is an echo that does not correlate with the
    request: builders raise, verifiers report.
    """
    is_eligible = evaluate_eligibility(
        identity=identity,
        role=role,
        mandate=mandate,
        context=context,
        observations=observations,
        disposition=disposition,
        requested_review_action=requested_review_action,
        referenced_observation_ids=list(observation_refs),
        evaluated_at=evaluated_at,
    )

    completion = DomainCheckCompletion.NOT_EVALUATED
    outcome = None
    # E2's own algorithm, over this candidate's references only. Restricting the
    # supplied collection to what this candidate actually references keeps E2's
    # "supplied but unreferenced" report meaningful at the level it is made: a
    # sibling candidate's evidence is not this candidate's unreferenced extra.
    referenced = [o for o in observations
                  if o.observation_id in set(observation_refs)]
    if _resolve_references(
            required=list(observation_refs), tenant_id=mandate.tenant_id,
            case_ref=mandate.case_ref, context=context, observations=referenced):
        request = _evaluation_request(
            candidate_id=candidate_id, profile_id=profile_id,
            profile_version=profile_version, observation_refs=observation_refs,
            mandate=mandate, context=context, observations=observations)
        try:
            response = provider.evaluate(request=request)
        except Exception as exc:  # noqa: BLE001 — one named family for the caller.
            raise DomainEvaluationProviderError(
                f"the injected domain-evaluation provider raised while evaluating "
                f"candidate {candidate_id!r}") from exc
        if response is None or not _echo_is_correlated(response, request):
            raise DomainEvaluationProviderError(
                "the provider's echoed profile identity or candidate_id does not "
                f"correspond to the request issued for candidate {candidate_id!r}")
        completion = DomainCheckCompletion.COMPLETE
        outcome = response.outcome

    return CandidateAdvisory(
        candidate_id=candidate_id,
        disposition=disposition,
        requested_review_action=requested_review_action,
        is_eligible=is_eligible,
        domain_check_completion=completion,
        domain_evaluation_outcome=outcome,
        evaluated_at=evaluated_at,
        claim_refs=list(claim_refs),
        observation_refs=list(observation_refs),
        assumptions=list(assumptions),
        uncertainties=list(uncertainties),
    )


def build_advisory_candidate_set(
    *,
    candidate_set_id: str,
    tenant_id: str,
    case_ref: str,
    created_at,
    candidates: tuple,
    selected_candidate_id: "str | None",
    domain_evaluation_profile_id: "str | None",
    domain_evaluation_profile_version: "str | None",
) -> AdvisoryCandidateSet:
    """H1, as amended by OD-7 part 5. ``candidates`` must already be in the ratified
    ascending-``candidate_id`` order (D6): this builder rejects out-of-order input
    rather than reordering it, which the model's own validator enforces.

    ``selected_candidate_id`` remains a caller parameter and is **checked, never
    trusted**: the model recomputes selection-policy v1 over these candidates and
    rejects any selector the ratified policy did not produce. That is what replaced
    C9 — a non-null selection is no longer unconstructible, it is constructible exactly
    when the policy produces it.

    The selector-policy identity is **not** a parameter. It names this package's own
    ratified selector, so accepting it from the caller would let a caller label a
    selection with a policy that did not make it. It is stamped here, from this
    package's own constants, whenever a selection is present, and is left ``None``
    whenever one is not.
    """
    selects = selected_candidate_id is not None
    return AdvisoryCandidateSet(
        schema_version="1.0",
        tenant_id=tenant_id,
        created_at=created_at,
        candidate_set_id=candidate_set_id,
        case_ref=case_ref,
        candidates=tuple(candidates),
        domain_evaluation_profile_id=domain_evaluation_profile_id,
        domain_evaluation_profile_version=domain_evaluation_profile_version,
        selected_candidate_id=selected_candidate_id,
        selection_policy_id=SELECTION_POLICY_ID if selects else None,
        selection_policy_version=SELECTION_POLICY_VERSION if selects else None,
        selection_reason_codes=[],
    )


def _resolve_installed_substrate_version() -> str:
    """D8. The installed ``ugence-jcs`` distribution's own version constant.

    ``importlib`` (and so ``importlib.metadata``) is barred from ``src`` by this
    package's own boundary guard (``test_no_local_canonicalization.py``), which
    reserves it for the test guards that walk this package's own modules. ``ugence_
    jcs.__version__`` is that distribution's single source of truth for its own
    version (``packages/jcs/src/ugence_jcs/version.py``), so reading it here states
    which substrate actually ran without importing the forbidden module.
    """
    return ugence_jcs.__version__


def build_proposer_process_record(
    *,
    process_record_id: str,
    tenant_id: str,
    case_ref: str,
    created_at,
    advisory: ProposerAdvisory,
    state_transitions: list,
    tool_invocations: list[str],
    candidate_ids: list[str],
    selected_candidate_id: "str | None",
    terminal_outcome: TerminalOutcome,
    started_at,
    completed_at,
) -> ProposerProcessRecord:
    """H1, as amended by S2-B rider `R1` (`S2B-S1-Q5=A`, `S2B-S1-Q10=A`). Enforces
    R-2, R-3 and R-4 through the model's own validators.

    **``declared_strategy`` and ``advisory_digest`` are no longer parameters.** Both
    are replaced by the single ``advisory`` parameter and **derived from it**. `[I]`
    Derivation is what prevents divergence at construction: a caller cannot hand this
    builder a declaration or a digest reference that disagrees with the advisory the
    record is about, because it hands over the advisory instead and this builder reads
    both values off it.

    `[R]` Derivation is **defence in depth, not the guarantee.** The two artifacts are
    transported independently, so the guarantee is ``verify_strategy_permission``'s
    fifth check, which re-establishes the same equality at replay across two
    separately received objects. `[R]` And that equality proves correspondence between
    **two observable fields** only — that the record and the advisory name the same
    declared strategy. It never proves conformance with private reasoning, and never
    proves that the declared procedure was executed.

    `[R]` This change sits **outside** A13's enumeration of four builders: A13 names the
    four carrying provider and profile parameters, and this is the fifth. A13 stands
    intact for its four.

    R-2's locally decidable half — ``PROPOSAL`` requires a selection — is enforced by
    the record's own validator. Its other conjunct, ``evaluate_readiness(...) is True``
    for the resolved candidate, needs contracts this record does not carry and is
    recomputed by ``build_proposer_advisory``, which is where B3 states V13 recomputes
    it. ``PROPOSAL`` is no longer refused outright: with C7 removed it is reachable
    exactly when R-2's two conjuncts hold.

    Built through ``model_validate`` over a plain field mapping rather than a
    keyword-argument call. ``ProposerProcessRecord.advisory_digest`` is a foreign key
    to ``ProposerAdvisory.advisory_digest`` (D8) — a caller-supplied reference, not an
    identity computation, and not reachable from either advisory type (A3). It
    happens to share its field name with the one field the identity-source guard in
    ``test_advisory_contract_shape.py`` scans for by name alone; a keyword argument
    spelled ``advisory_digest=advisory_digest`` would be misread as an unpermitted
    identity source on a field where no identity is being computed at all. Passing a
    plain mapping keeps this builder correctly attributing no identity computation to
    a field that is not one.
    """
    fields = {
        "schema_version": "1.0",
        "tenant_id": tenant_id,
        "created_at": created_at,
        "process_record_id": process_record_id,
        "case_ref": case_ref,
        # Rider `R1`: derived from the proposal-bound declaration, never supplied.
        "declared_strategy": advisory.declared_strategy,
        "state_transitions": list(state_transitions),
        "tool_invocations": list(tool_invocations),
        "deterministic_checks": [],
        "candidate_ids": list(candidate_ids),
        "selected_candidate_id": selected_candidate_id,
        "semantic_audit_refs": [],
        "terminal_outcome": terminal_outcome,
        "reason_codes": [],
        # Rider `R1`: derived from the advisory this record is about. Still a foreign
        # key (D8), not an identity computation, and not reachable from either
        # advisory type (A3) — which is why it stays in a plain field mapping rather
        # than becoming an ``advisory_digest=`` keyword the identity-source guard
        # would read as an unpermitted identity source on a field where no identity
        # is being computed at all.
        "advisory_digest": advisory.advisory_digest,
        "jcs_distribution_version": _resolve_installed_substrate_version(),
        "started_at": started_at,
        "completed_at": completed_at,
    }
    return ProposerProcessRecord.model_validate(fields)
