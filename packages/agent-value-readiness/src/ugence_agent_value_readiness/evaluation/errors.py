"""Error taxonomy for the GV-3R-b readiness-determination evaluator."""

from __future__ import annotations

from ..contracts.errors import ReadinessContractError

__all__ = ["ReadinessEvaluationError"]


class ReadinessEvaluationError(ReadinessContractError):
    """A readiness *evaluation input* was structurally malformed or contradictory.

    Subclasses :class:`ReadinessContractError` (and therefore ``ValueError``), so
    a caller already handling contract rejection keeps working.

    Raised only for inputs that **contradict themselves** — a gate bound to a
    different ``ReadinessPolicy`` than the one supplied, a gate result whose
    embedded ``PolicyGate`` is not the policy's gate of that id, duplicate gate /
    condition / result identifiers, cross-tenant or cross-subject binding, a
    policy reference that does not match the supplied policy body, or a naive
    ``evaluation_time``.

    An *incomplete but otherwise valid* assessment (a missing required gate
    result, a missing indicator family, an unbound readiness policy) is **not**
    an error: it is evaluated and returns ``NOT_ASSESSABLE`` with stable reason
    codes. Raising is never a readiness determination, and it never asserts that
    any policy, condition, or evidence was verified.
    """
