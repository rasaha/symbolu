"""The read seam, and the pure selectors behind it.

**Contracts only (D-5).** This module declares one read-only Protocol and the pure
functions that answer it over a caller-supplied collection. There is no store, no
adapter, no connector and no admission engine anywhere in the distribution — which
is how the post-v1 line is held: nothing here *could* reach a system of record.

Every selector filters to registrations in force at the caller's instant first. A
registration outside its window is **absent from the answer**, never returned with a
flag, so a lapsed registration cannot be argued around downstream.

Nothing here decides. There is no admit, no register-into, no promote, no approve,
no gate and no resolve: a registration is an input to somebody else's decision.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional, Protocol, runtime_checkable

from ._canon import optional_text, require_nonempty, require_tzaware
from .registration import SystemRegistration

__all__ = [
    "SystemRegistryPort", "registered_at", "select_for_tenant", "select_for_system",
    "select_by_classification", "supersession_chain",
]


def registered_at(registrations: Iterable[SystemRegistration],
                  as_of: datetime) -> tuple[SystemRegistration, ...]:
    """Only the registrations in force at ``as_of``, in a stable order."""

    require_tzaware(as_of, "as_of")
    return tuple(sorted((r for r in registrations if r.is_registered_at(as_of)),
                        key=lambda r: (r.tenant_id, r.system_id, r.system_version,
                                       r.registration_id)))


def select_for_tenant(registrations: Iterable[SystemRegistration], *, tenant_id: str,
                      as_of: datetime) -> tuple[SystemRegistration, ...]:
    """Everything one tenant currently has registered."""

    tenant = require_nonempty(tenant_id, "tenant_id")
    return registered_at((r for r in registrations if r.tenant_id == tenant), as_of)


def select_for_system(registrations: Iterable[SystemRegistration], *, tenant_id: str,
                      system_id: str, system_version: str = "",
                      as_of: datetime) -> tuple[SystemRegistration, ...]:
    """One system's current registrations, optionally narrowed to one version."""

    tenant = require_nonempty(tenant_id, "tenant_id")
    system = require_nonempty(system_id, "system_id")
    version = optional_text(system_version, "system_version")
    return registered_at(
        (r for r in registrations
         if r.tenant_id == tenant and r.system_id == system
         and (not version or r.system_version == version)), as_of)


def select_by_classification(registrations: Iterable[SystemRegistration], *, tenant_id: str,
                             classification_label: str,
                             as_of: datetime) -> tuple[SystemRegistration, ...]:
    """Everything carrying one declared label.

    The label is matched **exactly and uninterpreted** (D-2): the package knows no
    taxonomy, no ordering and no severity, so it can neither widen nor narrow a
    caller's query by reasoning about what a label means.
    """

    tenant = require_nonempty(tenant_id, "tenant_id")
    label = require_nonempty(classification_label, "classification_label")
    return registered_at((r for r in registrations
                          if r.tenant_id == tenant and r.classification_label == label), as_of)


def supersession_chain(registrations: Iterable[SystemRegistration],
                       registration_id: str) -> tuple[SystemRegistration, ...]:
    """The chain a registration supersedes, newest first — history, not a current answer.

    Deliberately **not** filtered by instant: a superseded registration is normally
    outside its window, and the chain exists to reconstruct what was registered when.
    A cycle terminates rather than looping.
    """

    by_id = {r.registration_id: r for r in registrations}
    current = by_id.get(require_nonempty(registration_id, "registration_id"))
    chain: list[SystemRegistration] = []
    seen: set[str] = set()
    while current is not None and current.registration_id not in seen:
        chain.append(current)
        seen.add(current.registration_id)
        current = by_id.get(current.supersedes) if current.supersedes else None
    return tuple(chain)


@runtime_checkable
class SystemRegistryPort(Protocol):
    """The read-only seam a composition root types against.

    **No implementation ships in 0.1.0** (D-4). A Protocol is a seam, not an adapter:
    declaring it lets a consumer depend on a stable surface while the operational
    registry and its systems-of-record connectors stay post-v1 under D-5.

    Every method takes the caller's instant and returns only registrations in force
    at it. There is no write method, by construction.
    """

    def get_registration(self, registration_id: str) -> Optional[SystemRegistration]: ...

    def registrations_for_tenant(self, *, tenant_id: str,
                                 as_of: datetime) -> tuple[SystemRegistration, ...]: ...

    def registrations_for_system(self, *, tenant_id: str, system_id: str,
                                 system_version: str = "",
                                 as_of: datetime) -> tuple[SystemRegistration, ...]: ...

    def registrations_by_classification(self, *, tenant_id: str, classification_label: str,
                                        as_of: datetime) -> tuple[SystemRegistration, ...]: ...
