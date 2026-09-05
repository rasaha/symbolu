"""The read seam, and the pure selectors behind it.

**Contracts only.** This module declares one read-only Protocol and the pure
functions that answer it over a caller-supplied collection. There is no store, no
adapter, no connector, no proxy and no engine anywhere in the distribution — which
is how the line is held: nothing here *could* reach data, a context or a model.

Every selector filters to declarations in force at the caller's instant first. A
declaration outside its window is **absent from the answer**, never returned with
a flag, so a lapsed declaration cannot be argued around downstream.

Nothing here decides. There is no admit, no authorize, no evaluate, no enforce:
a declaration is an input to somebody else's decision.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional, Protocol, runtime_checkable

from ._canon import optional_text, require_nonempty, require_tzaware
from .declaration import DataUseDeclaration, supersession_refusals

__all__ = [
    "DataUseDeclarationPort", "declared_at", "select_for_tenant", "select_for_data",
    "select_for_system", "select_by_classification", "select_by_purpose",
    "supersession_chain",
]


def _order(d: DataUseDeclaration) -> tuple:
    return (d.tenant_id, d.data_ref, d.system_id, d.system_version, d.declaration_id)


def declared_at(declarations: Iterable[DataUseDeclaration],
                as_of: datetime) -> tuple[DataUseDeclaration, ...]:
    """Only the declarations in force at ``as_of``, in a stable order."""

    require_tzaware(as_of, "as_of")
    return tuple(sorted((d for d in declarations if d.is_declared_at(as_of)), key=_order))


def select_for_tenant(declarations: Iterable[DataUseDeclaration], *, tenant_id: str,
                      as_of: datetime) -> tuple[DataUseDeclaration, ...]:
    """Everything one tenant currently has declared. Never another tenant's."""

    tenant = require_nonempty(tenant_id, "tenant_id")
    return declared_at((d for d in declarations if d.tenant_id == tenant), as_of)


def select_for_data(declarations: Iterable[DataUseDeclaration], *, tenant_id: str,
                    data_ref: str, as_of: datetime) -> tuple[DataUseDeclaration, ...]:
    """Every current declaration about one data reference, in one tenant."""

    tenant = require_nonempty(tenant_id, "tenant_id")
    ref = require_nonempty(data_ref, "data_ref")
    return declared_at((d for d in declarations
                        if d.tenant_id == tenant and d.data_ref == ref), as_of)


def select_for_system(declarations: Iterable[DataUseDeclaration], *, tenant_id: str,
                      system_id: str, system_version: str = "",
                      as_of: datetime) -> tuple[DataUseDeclaration, ...]:
    """One system's current declarations, optionally narrowed to one version."""

    tenant = require_nonempty(tenant_id, "tenant_id")
    system = require_nonempty(system_id, "system_id")
    version = optional_text(system_version, "system_version")
    return declared_at(
        (d for d in declarations
         if d.tenant_id == tenant and d.system_id == system
         and (not version or d.system_version == version)), as_of)


def select_by_classification(declarations: Iterable[DataUseDeclaration], *, tenant_id: str,
                             classification_label: str,
                             as_of: datetime) -> tuple[DataUseDeclaration, ...]:
    """Everything carrying one declared label.

    The label is matched **exactly and uninterpreted** (DE-3): the package knows no
    taxonomy, no ordering and no severity, so it can neither widen nor narrow a
    caller's query by reasoning about what a label means.
    """

    tenant = require_nonempty(tenant_id, "tenant_id")
    label = require_nonempty(classification_label, "classification_label")
    return declared_at((d for d in declarations
                        if d.tenant_id == tenant and d.classification_label == label), as_of)


def select_by_purpose(declarations: Iterable[DataUseDeclaration], *, tenant_id: str,
                      purpose_label: str, as_of: datetime) -> tuple[DataUseDeclaration, ...]:
    """Everything declared for one purpose, matched exactly and uninterpreted."""

    tenant = require_nonempty(tenant_id, "tenant_id")
    purpose = require_nonempty(purpose_label, "purpose_label")
    return declared_at((d for d in declarations
                        if d.tenant_id == tenant and d.purpose_label == purpose), as_of)


def supersession_chain(declarations: Iterable[DataUseDeclaration],
                       declaration_id: str) -> tuple[DataUseDeclaration, ...]:
    """The chain a declaration supersedes, newest first — history, not a current answer.

    Deliberately **not** filtered by instant: a superseded declaration is normally
    outside its window, and the chain exists to reconstruct what was declared when.

    **Only admissible links are walked.** A ``supersedes`` pointing at a declaration
    the package's own rule rejects — a different tenant, different data, or an
    unchanged declaration — ends the chain there rather than splicing an unrelated
    record into a history. A cycle terminates rather than looping.
    """

    by_id = {d.declaration_id: d for d in declarations}
    current = by_id.get(require_nonempty(declaration_id, "declaration_id"))
    chain: list[DataUseDeclaration] = []
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
class DataUseDeclarationPort(Protocol):
    """The read-only seam a composition root types against.

    **No implementation ships in 0.1.0.** A Protocol is a seam, not an adapter:
    declaring it lets a consumer depend on a stable surface while everything that
    could hold, reach or act on data stays outside this package.

    Every method takes the caller's instant and returns only declarations in force
    at it. There is no write method, by construction.
    """

    def get_declaration(self, declaration_id: str) -> Optional[DataUseDeclaration]: ...

    def declarations_for_tenant(self, *, tenant_id: str,
                                as_of: datetime) -> tuple[DataUseDeclaration, ...]: ...

    def declarations_for_data(self, *, tenant_id: str, data_ref: str,
                              as_of: datetime) -> tuple[DataUseDeclaration, ...]: ...

    def declarations_for_system(self, *, tenant_id: str, system_id: str,
                                system_version: str = "",
                                as_of: datetime) -> tuple[DataUseDeclaration, ...]: ...

    def declarations_by_classification(self, *, tenant_id: str, classification_label: str,
                                       as_of: datetime) -> tuple[DataUseDeclaration, ...]: ...
