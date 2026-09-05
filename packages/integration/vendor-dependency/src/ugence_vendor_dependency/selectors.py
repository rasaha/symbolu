"""The read seam, and the pure selectors behind it.

**Contracts only.** This module declares one read-only Protocol and the pure
functions that answer it over a caller-supplied collection. There is no store, no
connector, no gateway and no engine anywhere in the distribution — which is how
the line is held: nothing here *could* reach a vendor, a policy or a store.

Every selector filters to declarations in force at the caller's instant first. A
declaration outside its window is **absent from the answer**, never returned with
a flag, so a lapsed declaration cannot be argued around downstream.

Nothing here decides. There is no resolve, no verify, no score, no grade, no
approve: a declaration is an input to somebody else's decision.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional, Protocol, runtime_checkable

from ._canon import optional_text, require_nonempty, require_tzaware
from .declaration import VendorDependencyDeclaration, supersession_refusals

__all__ = [
    "VendorDependencyPort", "declared_at", "select_for_tenant", "select_for_vendor",
    "select_for_system", "select_by_risk_posture", "select_by_policy_ref",
    "supersession_chain",
]


def _order(d: VendorDependencyDeclaration) -> tuple:
    return (d.tenant_id, d.vendor_ref, d.system_id, d.system_version, d.declaration_id)


def declared_at(declarations: Iterable[VendorDependencyDeclaration],
                as_of: datetime) -> tuple[VendorDependencyDeclaration, ...]:
    """Only the declarations in force at ``as_of``, in a stable order."""

    require_tzaware(as_of, "as_of")
    return tuple(sorted((d for d in declarations if d.is_declared_at(as_of)), key=_order))


def select_for_tenant(declarations: Iterable[VendorDependencyDeclaration], *, tenant_id: str,
                      as_of: datetime) -> tuple[VendorDependencyDeclaration, ...]:
    """Everything one tenant currently has declared. Never another tenant's."""

    tenant = require_nonempty(tenant_id, "tenant_id")
    return declared_at((d for d in declarations if d.tenant_id == tenant), as_of)


def select_for_vendor(declarations: Iterable[VendorDependencyDeclaration], *, tenant_id: str,
                      vendor_ref: str, as_of: datetime) -> tuple[VendorDependencyDeclaration, ...]:
    """Every current declaration about one vendor reference, in one tenant."""

    tenant = require_nonempty(tenant_id, "tenant_id")
    ref = require_nonempty(vendor_ref, "vendor_ref")
    return declared_at((d for d in declarations
                        if d.tenant_id == tenant and d.vendor_ref == ref), as_of)


def select_for_system(declarations: Iterable[VendorDependencyDeclaration], *, tenant_id: str,
                      system_id: str, system_version: str = "",
                      as_of: datetime) -> tuple[VendorDependencyDeclaration, ...]:
    """One system's current vendor dependencies, optionally narrowed to one version."""

    tenant = require_nonempty(tenant_id, "tenant_id")
    system = require_nonempty(system_id, "system_id")
    version = optional_text(system_version, "system_version")
    return declared_at(
        (d for d in declarations
         if d.tenant_id == tenant and d.system_id == system
         and (not version or d.system_version == version)), as_of)


def select_by_risk_posture(declarations: Iterable[VendorDependencyDeclaration], *,
                           tenant_id: str, risk_posture_label: str,
                           as_of: datetime) -> tuple[VendorDependencyDeclaration, ...]:
    """Everything carrying one declared posture.

    The label is matched **exactly and uninterpreted** (VR-3): the package knows no
    grade, no ordering and no severity, so it can neither widen nor narrow a
    caller's query by reasoning about what a posture means.
    """

    tenant = require_nonempty(tenant_id, "tenant_id")
    label = require_nonempty(risk_posture_label, "risk_posture_label")
    return declared_at((d for d in declarations
                        if d.tenant_id == tenant and d.risk_posture_label == label), as_of)


def select_by_policy_ref(declarations: Iterable[VendorDependencyDeclaration], *, tenant_id: str,
                         policy_ref: str, as_of: datetime) -> tuple[VendorDependencyDeclaration, ...]:
    """Everything declared under one policy reference, matched exactly (VR-4).

    The reference is compared as text and nothing else: it is never resolved,
    verified or interpreted here.
    """

    tenant = require_nonempty(tenant_id, "tenant_id")
    ref = require_nonempty(policy_ref, "policy_ref")
    return declared_at((d for d in declarations
                        if d.tenant_id == tenant and d.policy_ref == ref), as_of)


def supersession_chain(declarations: Iterable[VendorDependencyDeclaration],
                       declaration_id: str) -> tuple[VendorDependencyDeclaration, ...]:
    """The chain a declaration supersedes, newest first — history, not a current answer.

    Deliberately **not** filtered by instant: a superseded declaration is normally
    outside its window, and the chain exists to reconstruct what was declared when.

    **Only admissible links are walked.** A ``supersedes`` pointing at a declaration
    the package's own rule rejects — a different tenant, a different vendor, or an
    unchanged declaration — ends the chain there rather than splicing an unrelated
    record into a history. A cycle terminates rather than looping.
    """

    by_id = {d.declaration_id: d for d in declarations}
    current = by_id.get(require_nonempty(declaration_id, "declaration_id"))
    chain: list[VendorDependencyDeclaration] = []
    seen: set[str] = set()
    while current is not None and current.declaration_id not in seen:
        chain.append(current)
        seen.add(current.declaration_id)
        if not current.supersedes:
            break
        predecessor = by_id.get(current.supersedes)
        if predecessor is None or supersession_refusals(current, predecessor):
            break
        current = predecessor
    return tuple(chain)


@runtime_checkable
class VendorDependencyPort(Protocol):
    """The read-only seam a composition root types against.

    **No implementation ships in 0.1.0.** A Protocol is a seam, not an adapter:
    declaring it lets a consumer depend on a stable surface while everything that
    could hold, reach or act on a vendor stays outside this package.

    Every method takes the caller's instant and returns only declarations in force
    at it. There is no write method, by construction.
    """

    def get_declaration(self, declaration_id: str) -> Optional[VendorDependencyDeclaration]: ...

    def declarations_for_tenant(self, *, tenant_id: str,
                                as_of: datetime) -> tuple[VendorDependencyDeclaration, ...]: ...

    def declarations_for_vendor(self, *, tenant_id: str, vendor_ref: str,
                                as_of: datetime) -> tuple[VendorDependencyDeclaration, ...]: ...

    def declarations_for_system(self, *, tenant_id: str, system_id: str,
                                system_version: str = "",
                                as_of: datetime) -> tuple[VendorDependencyDeclaration, ...]: ...

    def declarations_by_risk_posture(self, *, tenant_id: str, risk_posture_label: str,
                                     as_of: datetime) -> tuple[VendorDependencyDeclaration, ...]: ...
