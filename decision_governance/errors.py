"""Base error types for the Decision Governance kernel.

Every kernel failure derives from :class:`GovernanceError`. None of these
subclass ``ValueError``, so when raised inside a pydantic validator they
propagate as-is rather than being wrapped into a ``pydantic.ValidationError`` —
callers always receive the precise domain error type.

Consuming applications may alias :class:`GovernanceError` to a domain-specific
base and add their own typed error families; doing so preserves ``isinstance``
across the whole hierarchy.
"""

from __future__ import annotations


class GovernanceError(Exception):
    """Base class for every Decision Governance kernel error."""


class DomainValidationError(GovernanceError):
    """A governance contract invariant was violated."""


# --- Neutral governance error families (extracted in Phase 5B) -----------
# --- Repository ------------------------------------------------------------
class RepositoryError(GovernanceError):
    """Base class for persistence-layer errors."""


class RecordNotFoundError(RepositoryError):
    """A referenced record does not exist."""


class VersionConflictError(RepositoryError):
    """An immutable record version already exists, or a stale version was saved."""


class DuplicateDecisionError(RepositoryError):
    """A binding decision already exists for this subject/stage."""


class AppendOnlyViolationError(RepositoryError):
    """An attempt was made to mutate an append-only store."""



# --- Phase 4A: DecisionCase aggregate & lifecycle (additive) ---------------
class DecisionCaseError(GovernanceError):
    """Base for DecisionCase aggregate and lifecycle failures."""


class DecisionCaseNotFoundError(DecisionCaseError):
    """No decision case exists for the given id."""


class CaseVersionNotFoundError(DecisionCaseError):
    """The requested case version does not exist."""


class InvalidCaseTransitionError(DecisionCaseError):
    """A requested lifecycle transition is not structurally legal."""


class CaseFinalizedError(DecisionCaseError):
    """The case snapshot is terminal (superseded/cancelled/closed) and immutable."""


class AssessmentNotLinkableError(DecisionCaseError):
    """An assessment cannot be linked (missing, cross-tenant, or not finalized)."""


class RecommendationNotFoundError(DecisionCaseError):
    """No recommendation exists for the given id on this case."""


class RecommendationValidationError(DecisionCaseError):
    """A recommendation failed provenance, reference, or policy validation."""


class DecisionReadinessError(DecisionCaseError):
    """The case is not structurally ready for a decision to be recorded."""


class ReviewTaskNotFoundError(DecisionCaseError):
    """No review task exists for the given id on this case."""


class RequiredReviewIncompleteError(DecisionCaseError):
    """A required review task is outstanding and blocks decision readiness."""


class DecisionAuthorityError(DecisionCaseError):
    """The recorded authority is invalid, out of scope, or unauthorized."""


class AIDecisionAuthorityError(DecisionAuthorityError):
    """An AI principal attempted to author a binding decision."""


class DelegatedPolicyScopeError(DecisionAuthorityError):
    """A delegated policy acted outside its explicit, published bounds."""


class SegregationOfDutiesError(DecisionAuthorityError):
    """The same actor attempted two roles that must be separated (e.g. self-approval)."""


class UnauthorizedOverrideError(DecisionAuthorityError):
    """An override was attempted without the authority permitting it."""


class DecisionCaseAuthorizationError(DecisionCaseError):
    """The actor is not authorized for the requested case operation."""


class CrossTenantCaseAccessError(DecisionCaseAuthorizationError):
    """A cross-tenant decision-case access was attempted and denied."""


# --- Phase 4B: governed action request & CER binding (additive) ------------
class ActionRequestError(GovernanceError):
    """Base for governed action-request and CER-binding failures."""


class ActionRequestNotFoundError(ActionRequestError):
    """No action request exists for the given id."""


class InvalidActionRequestTransitionError(ActionRequestError):
    """A requested action-request lifecycle transition is not structurally legal."""


class DecisionNotActionableError(ActionRequestError):
    """The decision outcome does not produce an action (no published mapping)."""


class DecisionSupersededError(ActionRequestError):
    """The referenced decision is superseded or void and cannot produce an action."""


class ActionMappingNotFoundError(ActionRequestError):
    """No action mapping exists for the given id/selector."""


class ActionMappingNotPublishedError(ActionRequestError):
    """The selected action mapping is not in PUBLISHED status."""


class ActionTypeMismatchError(ActionRequestError):
    """The action type is not permitted for the decision outcome/mapping."""


class ActionParameterValidationError(ActionRequestError):
    """Requested parameters violate the mapping's parameter schema."""


class ProhibitedActionParameterError(ActionParameterValidationError):
    """A requested parameter is explicitly prohibited (or credential-like)."""


class TargetSystemNotPermittedError(ActionRequestError):
    """The declared target system is not permitted for the mapping."""


class CERBindingError(ActionRequestError):
    """The Context Envelope Record could not be constructed or is incomplete."""


class CERExpiredError(ActionRequestError):
    """The bound CER has expired and cannot be used for authorization."""


class ActionRequestNotReadyError(ActionRequestError):
    """The action request is not structurally ready for the requested step."""


class AuthorizationSubmissionError(ActionRequestError):
    """Submitting the request to the control plane failed (provider error)."""


class AuthorizationResponseMismatchError(ActionRequestError):
    """A control-plane response does not match the submitted request/CER."""


class DuplicateActionRequestError(ActionRequestError):
    """A different request already exists for the same idempotency key."""


class ActionRequestAlreadyAuthorizedError(ActionRequestError):
    """The request already carries a terminal authorization outcome."""


class ActionRequestSupersededError(ActionRequestError):
    """The action request snapshot has been superseded."""


class ActionRequestAuthorizationError(ActionRequestError):
    """The actor is not authorized for the requested action-request operation."""


class CrossTenantActionRequestError(ActionRequestAuthorizationError):
    """A cross-tenant action-request access was attempted and denied."""


# --- Phase 4C: external execution & reconciliation (additive) --------------
class ExecutionError(GovernanceError):
    """Base for external-execution, execution-record, and reconciliation failures."""


class ExecutionIntentNotFoundError(ExecutionError):
    """No execution intent exists for the given id."""


class ExecutionAttemptNotFoundError(ExecutionError):
    """No execution attempt exists for the given id."""


class ExecutionRecordNotFoundError(ExecutionError):
    """No execution record exists for the given id."""


class ActionRequestNotExecutableError(ExecutionError):
    """The action request is not in an executable (authorized) state."""


class AuthorizationNotExecutableError(ExecutionError):
    """The authorization outcome does not permit an execution attempt."""


class AuthorizationExpiredError(ExecutionError):
    """The control-plane authorization has expired; execution is blocked."""


class CERExpiredForExecutionError(ExecutionError):
    """The bound CER has expired; execution is blocked."""


class ExecutionParameterMismatchError(ExecutionError):
    """Execution parameters are not a subset of what was authorized."""


class ExecutionTargetMismatchError(ExecutionError):
    """The execution target system or action type does not match the authorization."""


class ExecutionIdempotencyConflictError(ExecutionError):
    """A different intent already exists for the same execution idempotency key."""


class UnsafeRetryError(ExecutionError):
    """A retry was requested without a safe/approved retry classification."""


class DuplicateExternalExecutionError(ExecutionError):
    """A duplicate external effect was detected for the same intent."""


class InvalidExecutionTransitionError(ExecutionError):
    """A requested execution lifecycle transition is not structurally legal."""


class ExternalDispatchError(ExecutionError):
    """The external adapter failed to dispatch (provider/transport error)."""


class MalformedExternalResponseError(ExecutionError):
    """An external response was malformed and is rejected (fail closed)."""


class ExternalRequestMismatchError(ExecutionError):
    """An observed outcome references a different external request than expected."""


class ExecutionOutcomeUnknownError(ExecutionError):
    """The business outcome is unknown and must not be treated as success/failure."""


class ReconciliationIncompleteError(ExecutionError):
    """Reconciliation cannot complete without the required observations."""


class ExecutionMismatchError(ExecutionError):
    """Observed effects materially differ from the authorized intent."""


class CompensationRequiredError(ExecutionError):
    """A compensation requirement must be created/resolved before proceeding."""


class CompensationNotFoundError(ExecutionError):
    """No compensation requirement exists for the given id."""


class ExecutionAuthorizationError(ExecutionError):
    """The actor is not authorized for the requested execution operation."""


class CrossTenantExecutionError(ExecutionAuthorizationError):
    """A cross-tenant execution access was attempted and denied."""
