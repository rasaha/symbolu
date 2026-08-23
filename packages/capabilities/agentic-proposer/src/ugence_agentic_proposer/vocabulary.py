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
"""
from __future__ import annotations

from enum import Enum

__all__ = [
    "TerminalOutcome",
    "CandidateDisposition",
    "SemanticAuditorFindingStatus",
    "RESERVED_AUTHORITY_VOCABULARY",
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
