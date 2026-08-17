"""Error taxonomy for the trusted readiness orchestration boundary."""

from __future__ import annotations

from ..contracts.errors import ReadinessContractError

__all__ = ["ReadinessAssessmentError"]


class ReadinessAssessmentError(ReadinessContractError):
    """A readiness **assessment request** was structurally malformed.

    Subclasses :class:`ReadinessContractError` (and therefore ``ValueError``), so
    a caller already handling contract rejection keeps working.

    Raised only for inputs that **contradict themselves or cannot be
    orchestrated at all**: a non-``AssessmentContext`` context, a cross-tenant or
    cross-subject binding, a readiness reference of the wrong policy family, a
    naive / missing / non-``datetime`` evaluation time, a scalar substituted for
    a sequence, or an indicator result bound to another tenant, subject or
    context.

    An input that is merely **untrusted** is never an exception: an unresolved
    policy, an unverified gate result and an unverified condition all produce a
    :class:`~ugence_agent_value_readiness.orchestration.trace.ReadinessAssessmentOutcome`
    carrying stable trust-gap codes. Raising is never a readiness determination,
    and it never asserts that anything was verified.
    """
