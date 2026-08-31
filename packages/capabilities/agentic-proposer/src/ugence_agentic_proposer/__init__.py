"""Ugence Agentic Proposer.

The Agentic Proposer is an ADVISORY capability. It proposes; it decides nothing.
It mints no agent identity, authors no organizational role, admits no evidence,
authorizes no action, grants no clearance and executes nothing. Owner decisions
D1-D10 and the ratification addenda are recorded in
``docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md``; the canonical S1
contract and equation specification is
``docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md``.

This package exports the full H3 public surface as amended by OD-7: the eight
canonical contracts, the two nested public shapes, the three OD-7 call-boundary shapes
(``DomainEvaluationRequest``, ``DomainEvaluationResponse`` and the
``DomainEvaluationProvider`` protocol — none of them a contract, none stored,
transported or identity-bearing), all eleven ratified enums, the five builders, the two
equation functions, the two identity functions, the five verifiers, the three
exceptions this package defines (OD-6(ii) added ``CrossContractViolationError``
alongside ``EligibilityMismatchError``; OD-7 added ``DomainEvaluationProviderError``),
and the four ratified constants — forty-six names at 0.2.0.

S2-B adds five at ``0.3.0``, taking the curated surface to fifty-one: the closed
``ReasoningStrategy`` vocabulary, the ``StrategyPolicyResolver`` protocol this package
owns and does not implement, its ``StrategyPolicyRequest`` and
``StrategyPolicyResponse`` call shapes, and ``verify_strategy_permission``. Reasoning
Strategy Permission asks **which declared reasoning procedure a role is permitted to
use**; it is advisory on the same terms as everything else here. `[R]` It does **not**
claim that a model's private reasoning becomes deterministic, that a declared strategy
proves the model internally followed it, that Ugence can inspect or replay private
chain-of-thought, that a declared procedure was executed, or that permission to use a
strategy authorizes additional compute, tools, evidence access or consequential
execution. A permission failure is **structural**: no artifact is constructed, replay
returns ``False``, and **no disposition and no reserved authority term is emitted**.

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
    DomainEvaluationProvider,
    DomainEvaluationRequest,
    DomainEvaluationResponse,
    ProposerAdvisory,
    ProposerProcessRecord,
    ProposerProcessStateTransition,
    StrategyPolicyRequest,
    StrategyPolicyResolver,
    StrategyPolicyResponse,
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
    DomainEvaluationProviderError,
    EligibilityMismatchError,
    verify_advisory_selection,
    verify_candidate_eligibility,
    verify_deterministic_selection,
    verify_domain_evaluation,
    verify_observation_resolution,
    verify_strategy_permission,
)
from .version import __version__
from .vocabulary import (
    RESERVED_AUTHORITY_VOCABULARY,
    AgentLifecycleState,
    CandidateDisposition,
    DomainCheckCompletion,
    DomainEvaluationOutcome,
    ProposerProcessState,
    ReasoningStrategy,
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
    # OD-7 call-boundary shapes (2) and the injected-evaluator protocol (1). Not
    # contracts: no C2 common field, no identity role, never stored or transported.
    "DomainEvaluationRequest",
    "DomainEvaluationResponse",
    "DomainEvaluationProvider",
    # S2-B strategy-policy call-boundary shapes (2) and the injected-resolver protocol
    # (1). Not contracts, on exactly OD-7's terms: no C2 common field, no identity
    # role, never stored or transported. This package OWNS the protocol and implements
    # no resolver (S2B-D1=A excludes it as an issuer).
    "StrategyPolicyRequest",
    "StrategyPolicyResponse",
    "StrategyPolicyResolver",
    # Enums (12)
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
    "DomainEvaluationOutcome",
    "ReasoningStrategy",
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
    # Verifiers (6)
    "verify_candidate_eligibility",
    "verify_advisory_selection",
    "verify_observation_resolution",
    "verify_domain_evaluation",
    "verify_deterministic_selection",
    "verify_strategy_permission",
    # Exceptions (3)
    "EligibilityMismatchError",
    "CrossContractViolationError",
    "DomainEvaluationProviderError",
    # Constants (4)
    "RESERVED_AUTHORITY_VOCABULARY",
    "ADVISORY_KIND",
    "ADVISORY_IDENTITY_SET_PATHS",
    "ADVISORY_IDENTITY_NFC_PATHS",
    # Metadata (1)
    "__version__",
]
