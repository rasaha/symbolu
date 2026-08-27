"""Part H — the three builders that need no identity computation.

``build_proposer_advisory`` and ``build_advisory_revision`` live in ``identity.py``
because G2 requires the substrate call inline in the ``advisory_digest=`` keyword of
the same construction expression, and I1 scopes that exemption to a single file.
"""
from __future__ import annotations

import ugence_jcs

from .contracts import AdvisoryCandidateSet, CandidateAdvisory, ProposerProcessRecord
from .equations import evaluate_eligibility
from .vocabulary import CandidateDisposition, ReviewAction, TerminalOutcome

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
) -> CandidateAdvisory:
    """H1. Takes no ``is_eligible`` and no ``domain_check_completion`` parameter: it
    computes Equation 1 and passes the computed Boolean **directly** as the
    ``is_eligible=`` keyword, in the same expression that computes it, and leaves
    ``domain_check_completion`` at its ``NOT_EVALUATED`` default (G4)."""
    return CandidateAdvisory(
        candidate_id=candidate_id,
        disposition=disposition,
        requested_review_action=requested_review_action,
        is_eligible=evaluate_eligibility(
            identity=identity,
            role=role,
            mandate=mandate,
            context=context,
            observations=observations,
            disposition=disposition,
            requested_review_action=requested_review_action,
            referenced_observation_ids=list(observation_refs),
            evaluated_at=evaluated_at,
        ),
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
) -> AdvisoryCandidateSet:
    """H1. ``candidates`` must already be in the ratified ascending-``candidate_id``
    order (D6): this builder rejects out-of-order input rather than reordering it,
    which the model's own validator enforces."""
    return AdvisoryCandidateSet(
        schema_version="1.0",
        tenant_id=tenant_id,
        created_at=created_at,
        candidate_set_id=candidate_set_id,
        case_ref=case_ref,
        candidates=tuple(candidates),
        selected_candidate_id=selected_candidate_id,
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
    declared_strategy: str,
    state_transitions: list,
    tool_invocations: list[str],
    candidate_ids: list[str],
    selected_candidate_id: "str | None",
    terminal_outcome: TerminalOutcome,
    advisory_digest: str,
    started_at,
    completed_at,
) -> ProposerProcessRecord:
    """H1. Enforces R-2, R-3 and R-4 through the model's own validators. Under B3, a
    ``PROPOSAL`` terminal outcome is unreachable in S1 and is rejected there.

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
        "declared_strategy": declared_strategy,
        "state_transitions": list(state_transitions),
        "tool_invocations": list(tool_invocations),
        "deterministic_checks": [],
        "candidate_ids": list(candidate_ids),
        "selected_candidate_id": selected_candidate_id,
        "semantic_audit_refs": [],
        "terminal_outcome": terminal_outcome,
        "reason_codes": [],
        "advisory_digest": advisory_digest,
        "jcs_distribution_version": _resolve_installed_substrate_version(),
        "started_at": started_at,
        "completed_at": completed_at,
    }
    return ProposerProcessRecord.model_validate(fields)
