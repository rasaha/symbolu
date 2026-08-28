"""Ratified Agentic Proposer vocabulary (owner decision D4).

Every term here is an ADVISORY PROPOSER CLASSIFICATION. None of them constitutes
evidence admission, a business decision, authorization, clearance or execution
permission. The proposer proposes; other capabilities decide:

  * binding business decision            -> Decision Authority
  * exact-action authorization           -> ActionGate
  * operational clearance                -> Action Clearance
  * agent eligibility, ranking, team composition, proposed permission bounds
                                         -> Agent Workforce Composer
  * execution                            -> Agent Runtime
  * evidence admission                   -> Trusted Evidence Authority / TAP

D4 also reserves a vocabulary this capability must never emit: CLEAR, HOLD, BLOCK,
AUTHORIZED, AUTHORIZED_WITH_CONSTRAINTS, DENIED, INDETERMINATE, SUPPORTED,
UNSUPPORTED, CONSTRAINED, EXPIRED, or any equivalent authority claim.

One term appears on both sides of D4 and the split is deliberate: INDETERMINATE is
reserved as a terminal outcome and as a candidate disposition — where it would read
as an authority claim — and is ratified only as a semantic-auditor finding status,
where it describes the auditor's reading of a document and claims nothing about
authorization. ``tests/test_vocabulary.py`` pins that split.

This module defines the ratified enums and nothing else. It contains no scoring,
no threshold, no gate, no policy-decision point, and no confidence-to-outcome
conversion.

S1 (`docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md`) adds seven closed vocabularies
alongside the three D4 enums above: ``ReviewAction`` (B8), ``DomainCheckCompletion``
(C7), ``AgentLifecycleState`` (D1), ``RoleActivationStatus`` (D2), ``ToolOperationClass``
and ``ToolObservationAdmissionStatus`` (D5), and ``ProposerProcessState`` (D8, R-3).
Each is a closed membership vocabulary for a contract field; none is an authority
claim, and none grants, clears, admits evidence or decides anything.

OD-7 (part 3) adds an eighth, ``DomainEvaluationOutcome``. It carries the *result* of a
domain evaluation, which ``DomainCheckCompletion`` deliberately does not encode: the
latter still states only whether every check the applicable profile requires reached a
determinate per-check reading. ``DomainEvaluationOutcome`` is not an authority claim
either — it is the injected evaluator's advisory reading of one candidate against one
versioned profile, and it grants, clears, admits and decides nothing.
"""
from __future__ import annotations

from enum import Enum

__all__ = [
    "TerminalOutcome",
    "CandidateDisposition",
    "SemanticAuditorFindingStatus",
    "RESERVED_AUTHORITY_VOCABULARY",
    "ReviewAction",
    "DomainCheckCompletion",
    "AgentLifecycleState",
    "RoleActivationStatus",
    "ToolOperationClass",
    "ToolObservationAdmissionStatus",
    "ProposerProcessState",
    "DomainEvaluationOutcome",
]


class TerminalOutcome(str, Enum):
    """How a proposer run ends. Advisory; never an authorization or a decision."""

    #: The proposer produced a recommendation for a human or downstream authority.
    PROPOSAL = "PROPOSAL"
    #: The proposer cannot proceed without further evidence it may not itself admit.
    NEED_EVIDENCE = "NEED_EVIDENCE"
    #: The proposer declines to recommend. This is not a denial and must never be
    #: consumed as one; nothing downstream may treat it as a decision to replan.
    ABSTAIN = "ABSTAIN"
    #: The proposer refers the matter to a human or an owning authority.
    ESCALATE = "ESCALATE"


class CandidateDisposition(str, Enum):
    """The proposer's advisory reading of a single candidate."""

    #: Recommend that an approving authority consider this matched candidate. The
    #: approval is the authority's; this term grants nothing.
    RECOMMEND_MATCHED_FOR_APPROVAL = "RECOMMEND_MATCHED_FOR_APPROVAL"
    #: Recommend withholding this candidate from approval. Not a denial.
    RECOMMEND_WITHHOLD = "RECOMMEND_WITHHOLD"
    #: Ask for evidence about this candidate.
    REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
    #: Refer this candidate's exception to a human or an owning authority.
    ESCALATE_EXCEPTION = "ESCALATE_EXCEPTION"


class SemanticAuditorFindingStatus(str, Enum):
    """Status of a semantic-auditor finding.

    Defined now, used at a later stage. Each value describes the relationship
    between documents the auditor read. None of them authorizes, clears, admits
    evidence or decides anything.
    """

    #: The documents agree.
    CONSISTENT = "CONSISTENT"
    #: The documents disagree.
    INCONSISTENT = "INCONSISTENT"
    #: The documents do not settle the question. Scoped to the auditor's reading;
    #: never a terminal outcome and never a candidate disposition.
    INDETERMINATE = "INDETERMINATE"
    #: The documents assert mutually exclusive things.
    CONFLICTING = "CONFLICTING"


#: Terms D4 forbids this capability from emitting as an outcome or a disposition.
#: Held here so the boundary tests can assert the prohibition directly rather than
#: restating it. ``INDETERMINATE`` is reserved in those two positions only; see the
#: module docstring and ``SemanticAuditorFindingStatus.INDETERMINATE``.
RESERVED_AUTHORITY_VOCABULARY = frozenset({
    "CLEAR",
    "HOLD",
    "BLOCK",
    "AUTHORIZED",
    "AUTHORIZED_WITH_CONSTRAINTS",
    "DENIED",
    "INDETERMINATE",
    "SUPPORTED",
    "UNSUPPORTED",
    "CONSTRAINED",
    "EXPIRED",
})


class ReviewAction(str, Enum):
    """B8. Exactly the two ratified review-routing actions."""

    ROUTE_APPROVAL_BUNDLE = "ROUTE_APPROVAL_BUNDLE"
    CREATE_EXCEPTION_REVIEW_BUNDLE = "CREATE_EXCEPTION_REVIEW_BUNDLE"


class DomainCheckCompletion(str, Enum):
    """C7, as amended by OD-7 part 3. ``COMPLETE`` closes the enum and makes Equation 2
    total, and it gates **only whether evaluation ran** — never what it concluded.

    OD-7 supplies the substantive reading C7 itself never stated: ``COMPLETE`` means
    every check the applicable versioned domain-evaluation profile requires reached a
    *per-check* determinate reading — none left pending, none erroring, none timed
    out — regardless of whether those readings, taken together, resolve to a clean pass
    or fail. The aggregate result is carried separately by ``DomainEvaluationOutcome``,
    which is why ``COMPLETE`` and ``INCONCLUSIVE`` are compatible rather than
    contradictory.

    C7's own S1 ceiling — a validator rejecting ``COMPLETE`` unconditionally — is
    **removed**, in the single change set that added ``DomainEvaluationOutcome``, the
    ``CandidateAdvisory.domain_evaluation_outcome`` field and its coupling validator,
    the ``AdvisoryCandidateSet``/``ProposerAdvisory`` profile and selector-policy
    fields, the ``DomainEvaluationProvider`` boundary, the two replay functions and
    Equation 2's seventh term (OD-7 part 8). The coupling validator and those replay
    functions are what took over C7's fail-closed role.
    """

    NOT_EVALUATED = "NOT_EVALUATED"
    COMPLETE = "COMPLETE"


class DomainEvaluationOutcome(str, Enum):
    """OD-7 part 3. The *result* of a completed domain evaluation, for one candidate,
    under one versioned profile. Never an authorization, a clearance or a decision.

    ``INDETERMINATE`` is deliberately **not** reused: D4 reserves that spelling to two
    authority-adjacent positions and ratifies it in exactly one non-authority position
    (``SemanticAuditorFindingStatus``). A third position was not ratified, so
    ``INCONCLUSIVE`` is used instead; ``tests/test_vocabulary.py`` pins that the two
    spellings never collide (I8.8).
    """

    #: Every check the profile requires ran, and the aggregation resolves to a pass.
    SATISFIED = "SATISFIED"
    #: Every check ran, and the aggregation resolves to a fail.
    NOT_SATISFIED = "NOT_SATISFIED"
    #: Every check ran and each individually resolved, and the profile's aggregation
    #: rule states, definitely, that they do not converge. Recording this is a
    #: determinate act about *process*; the answer it records is an absence of
    #: substantive convergence. It is compatible with ``DomainCheckCompletion.COMPLETE``
    #: for exactly that reason (OD-7 part 3).
    INCONCLUSIVE = "INCONCLUSIVE"


class AgentLifecycleState(str, Enum):
    """D1's closed vocabulary. An externally issued fact; never computed here."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class RoleActivationStatus(str, Enum):
    """D2's closed vocabulary. An input fact, never computed by this package."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ToolOperationClass(str, Enum):
    """D5's closed vocabulary. The proposer reads read-only tool evidence only."""

    READ_ONLY = "READ_ONLY"


class ToolObservationAdmissionStatus(str, Enum):
    """D5's closed vocabulary. No code path in this package sets a value other than
    ``NOT_EVALUATED``."""

    NOT_EVALUATED = "NOT_EVALUATED"


class ProposerProcessState(str, Enum):
    """D8/R-3's process lifecycle: the five in-progress states, in ratified order,
    followed by the four terminal outcomes R-3's own chain names as the states a
    process may end in.

    The specification (D8's nested-shape table and H3) types
    ``ProposerProcessStateTransition.state`` as ``ProposerProcessState`` and states R-3's
    chain literally as
    ``RECEIVED -> VALIDATED -> OBSERVING -> RECONCILING -> EVALUATING ->
    {PROPOSAL, NEED_EVIDENCE, ABSTAIN, ESCALATE}``. R-3's chain notation names the four
    terminal outcomes as the values ``state`` takes at the end of the very sequence it
    is the type of, and R-4 presupposes that ``ProposerProcessRecord.terminal_outcome``
    can be compared against "the terminal ``ProposerProcessState``" — both make sense
    only if the four terminal outcomes are themselves members of this enum, which is
    why the nine-member membership was always entailed rather than chosen.

    What the specification did not itself state — the four terminal members' wire
    values and R-4's comparison basis — is ratified as specification text by OD-6(iii)
    (``docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md``): the four
    terminal members carry exactly ``TerminalOutcome``'s wire values, so the two enums
    compare equal and serialise identically on that overlap, and R-4's "equals" is
    value equality. ``[V]``, ratified; see
    ``tests/test_process_ordering_obligation.py`` for the pinning coverage.
    """

    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    OBSERVING = "OBSERVING"
    RECONCILING = "RECONCILING"
    EVALUATING = "EVALUATING"
    PROPOSAL = "PROPOSAL"
    NEED_EVIDENCE = "NEED_EVIDENCE"
    ABSTAIN = "ABSTAIN"
    ESCALATE = "ESCALATE"
