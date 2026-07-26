"""Hiring-domain audit partition — canonical labeling of hiring event names.

The kernel classifies every :class:`AuditEventType` into a neutral namespace
(``KERNEL`` / ``LEGACY`` / ``DOMAIN``) without renaming any value (see
``decision_governance.audit.namespace``). This module names the hiring domain's
slice of that partition: the ``DOMAIN`` runtime events (evidence, capability,
rubric, assessment) plus the ``LEGACY`` foundation events (workflow, evaluation,
recommendation, decision) that the hiring domain owns.

The invariant enforced here — checked at import — is that **no hiring-owned
event is a kernel event**: the governance kernel's neutral lifecycle never emits
a hiring-domain event name.
"""

from __future__ import annotations

from decision_governance.api.audit import AuditEventType
from decision_governance.api.audit import (
    DOMAIN_EVENTS,
    KERNEL_EVENTS,
    LEGACY_EVENTS,
    is_kernel_event,
)

# Event names owned by the hiring domain: its domain-runtime events plus the
# legacy foundation vocabulary it originated. Disjoint from the kernel events.
HIRING_EVENTS: frozenset[AuditEventType] = DOMAIN_EVENTS | LEGACY_EVENTS

# Enforced invariant: nothing the hiring domain owns is emitted by the kernel.
assert not (HIRING_EVENTS & KERNEL_EVENTS), "hiring events must not overlap kernel events"


def is_hiring_event(event_type: AuditEventType) -> bool:
    """True iff this audit event name is owned by the hiring domain."""
    return event_type in HIRING_EVENTS


__all__ = ["HIRING_EVENTS", "is_hiring_event", "is_kernel_event"]
