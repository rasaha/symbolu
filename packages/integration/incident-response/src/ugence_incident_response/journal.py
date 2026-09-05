"""The read seam and the pure rules over a caller-held collection.

**Records only (D-4).** No store ships: the platform already has six durable
append-only event stores plus the kernel's audit port, and a seventh — for a package
whose entire output is a record somebody else acts on — would deepen exactly the
fragmentation gap G4 had to work around. An incident's durability is its
``AuditReference`` into a store that already exists.

So these are pure functions over a collection the caller holds, plus one read-only
Protocol a composition root can type against. Nothing here persists, decides, or
acts.
"""

from __future__ import annotations

from typing import Iterable, Optional, Protocol, runtime_checkable

from ._canon import require_nonempty
from .records import (
    IncidentRecord,
    lift_refusals,
    require_admissible_lift,
)
from .states import OPEN_STATES, IncidentState

#: ``lift_refusals`` and ``require_admissible_lift`` live in :mod:`.records`, next
#: to the records they judge — :class:`~.records.IncidentRecord.containment_lifted`
#: is their only in-package caller and importing them back would be a cycle. They
#: are re-exported here because the read seam is where a composition root looks.
__all__ = [
    "IncidentJournalPort", "open_incidents", "incidents_for_subject",
    "contained_incidents", "lift_refusals", "require_admissible_lift",
]


def open_incidents(incidents: Iterable[IncidentRecord], *,
                   tenant_id: str) -> tuple[IncidentRecord, ...]:
    """Every incident still live for one tenant, in a stable order."""

    tenant = require_nonempty(tenant_id, "tenant_id")
    return tuple(sorted((i for i in incidents
                         if i.tenant_id == tenant and i.state in OPEN_STATES),
                        key=lambda i: (i.opened_at, i.incident_id)))


def incidents_for_subject(incidents: Iterable[IncidentRecord], *, tenant_id: str,
                          subject_ref: str) -> tuple[IncidentRecord, ...]:
    """Every incident recorded against one subject, open or closed — this is history."""

    tenant = require_nonempty(tenant_id, "tenant_id")
    subject = require_nonempty(subject_ref, "subject_ref")
    return tuple(sorted((i for i in incidents
                         if i.tenant_id == tenant and i.subject_ref == subject),
                        key=lambda i: (i.opened_at, i.incident_id)))


def contained_incidents(incidents: Iterable[IncidentRecord], *,
                        tenant_id: str) -> tuple[IncidentRecord, ...]:
    """Incidents whose containment is still asked for.

    Deliberately **not** filtered to open incidents: a closed incident whose
    containment was never lifted is exactly the case an operator must be able to
    see, and the one a lifecycle-driven view would hide.
    """

    tenant = require_nonempty(tenant_id, "tenant_id")
    return tuple(sorted((i for i in incidents if i.tenant_id == tenant and i.is_contained),
                        key=lambda i: (i.opened_at, i.incident_id)))


@runtime_checkable
class IncidentJournalPort(Protocol):
    """The read-only seam a composition root types against.

    **No implementation ships** (D-4): a Protocol is a seam, not a store. There is
    no write method, by construction — recording an incident is the caller's act,
    and this package supplies the record shape, not the place to put it.
    """

    def get_incident(self, incident_id: str) -> Optional[IncidentRecord]: ...

    def open_incidents(self, *, tenant_id: str) -> tuple[IncidentRecord, ...]: ...

    def incidents_for_subject(self, *, tenant_id: str,
                              subject_ref: str) -> tuple[IncidentRecord, ...]: ...

    def contained_incidents(self, *, tenant_id: str) -> tuple[IncidentRecord, ...]: ...
