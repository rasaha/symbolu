"""Ugence Agentic Proposer.

The Agentic Proposer is an ADVISORY capability. It proposes; it decides nothing.
It mints no agent identity, authors no organizational role, admits no evidence,
authorizes no action, grants no clearance and executes nothing. Owner decisions
D1-D10 and the ratification addenda are recorded in
``docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md``; the canonical S1
contract and equation specification is
``docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md``.

This package now exports the full H3 public surface: the eight canonical contracts,
the two nested public shapes, all ten ratified enums, the five builders, the two
equation functions, the two identity functions, the three verifiers, the two
exceptions this package defines (OD-6(ii) added ``CrossContractViolationError``
alongside ``EligibilityMismatchError``), and the four ratified constants.

Proposal identity is computed only by a call into ``ugence_jcs``, inside the single
authorised identity module (``identity.py``). This package contains no
canonicalization code of any kind anywhere else — not in ``src``, not in ``tests``,
not behind a flag, not as a fallback, not as a temporary helper — and
``tests/test_no_local_canonicalization.py`` enforces that.
"""
from __future__ import annotations

from .builders import (
    build_advisory_candidate_set,
    build_candidate_advisory,
    build_proposer_process_record,
)
from .contracts import (
    ADVISORY_KIND,
    AdvisoryCandidateSet,
    AgentIdentityRef,
    BoundedContextEnvelope,
    CandidateAdvisory,
    CognitiveRoleContract,
    ProposerAdvisory,
    ProposerProcessRecord,
    ProposerProcessStateTransition,
    ToolObservation,
    WorkMandate,
)
from .equations import evaluate_eligibility, evaluate_readiness
from .identity import (
    ADVISORY_IDENTITY_NFC_PATHS,
    ADVISORY_IDENTITY_SET_PATHS,
    build_advisory_revision,
    build_proposer_advisory,
    compute_advisory_identity,
    verify_advisory_identity,
)
from .verification import (
    CrossContractViolationError,
    EligibilityMismatchError,
    verify_advisory_selection,
    verify_candidate_eligibility,
    verify_observation_resolution,
)
from .version import __version__
from .vocabulary import (
    RESERVED_AUTHORITY_VOCABULARY,
    AgentLifecycleState,
    CandidateDisposition,
    DomainCheckCompletion,
    ProposerProcessState,
    ReviewAction,
    RoleActivationStatus,
    SemanticAuditorFindingStatus,
    TerminalOutcome,
    ToolObservationAdmissionStatus,
    ToolOperationClass,
)

__all__ = [
    # Contracts (8)
    "AgentIdentityRef",
    "CognitiveRoleContract",
    "WorkMandate",
    "BoundedContextEnvelope",
    "ToolObservation",
    "AdvisoryCandidateSet",
    "ProposerAdvisory",
    "ProposerProcessRecord",
    # Nested public models (2)
    "CandidateAdvisory",
    "ProposerProcessStateTransition",
    # Enums (10)
    "TerminalOutcome",
    "CandidateDisposition",
    "SemanticAuditorFindingStatus",
    "ReviewAction",
    "DomainCheckCompletion",
    "AgentLifecycleState",
    "RoleActivationStatus",
    "ToolOperationClass",
    "ToolObservationAdmissionStatus",
    "ProposerProcessState",
    # Builders (5)
    "build_candidate_advisory",
    "build_advisory_candidate_set",
    "build_proposer_advisory",
    "build_advisory_revision",
    "build_proposer_process_record",
    # Equation functions (2)
    "evaluate_eligibility",
    "evaluate_readiness",
    # Identity functions (2)
    "compute_advisory_identity",
    "verify_advisory_identity",
    # Verifiers (3)
    "verify_candidate_eligibility",
    "verify_advisory_selection",
    "verify_observation_resolution",
    # Exceptions (2)
    "EligibilityMismatchError",
    "CrossContractViolationError",
    # Constants (4)
    "RESERVED_AUTHORITY_VOCABULARY",
    "ADVISORY_KIND",
    "ADVISORY_IDENTITY_SET_PATHS",
    "ADVISORY_IDENTITY_NFC_PATHS",
    # Metadata (1)
    "__version__",
]
