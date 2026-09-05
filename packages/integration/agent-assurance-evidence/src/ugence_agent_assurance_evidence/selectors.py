"""The read seam, and the pure selectors behind it.

**Contracts only.** This module declares one read-only Protocol and the pure
functions that answer it over a caller-supplied collection. There is no probe
runner, no corpus, no scorer, no admission engine and no store anywhere in the
distribution — which is how the line is held: nothing here *could* produce a
finding, judge one, or hand one to anybody.

Every selector filters to declarations in force at the caller's instant first. A
declaration outside its window is **absent from the answer**, never returned with
a flag, so a lapsed finding cannot be argued around downstream.

Nothing here decides. There is no admit, no evaluate, no score, no cite: a
declaration is an input to somebody else's decision, and the two consumer routes
AE-4 names both begin outside this package.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional, Protocol, runtime_checkable

from ._canon import optional_text, require_nonempty, require_tzaware
from .declaration import AssuranceFindingDeclaration, supersession_refusals

__all__ = [
    "AssuranceFindingPort", "declared_at", "select_for_tenant", "select_for_system",
    "select_for_evidence", "select_by_finding", "select_by_exercise",
    "supersession_chain",
]


def _order(d: AssuranceFindingDeclaration) -> tuple:
    return (d.tenant_id, d.system_id, d.system_version, d.evidence_id, d.declaration_id)


def declared_at(declarations: Iterable[AssuranceFindingDeclaration],
                as_of: datetime) -> tuple[AssuranceFindingDeclaration, ...]:
    """Only the declarations in force at ``as_of``, in a stable order."""

    require_tzaware(as_of, "as_of")
    return tuple(sorted((d for d in declarations if d.is_declared_at(as_of)), key=_order))


def select_for_tenant(declarations: Iterable[AssuranceFindingDeclaration], *, tenant_id: str,
                      as_of: datetime) -> tuple[AssuranceFindingDeclaration, ...]:
    """Everything one tenant currently has declared. Never another tenant's."""

    tenant = require_nonempty(tenant_id, "tenant_id")
    return declared_at((d for d in declarations if d.tenant_id == tenant), as_of)


def select_for_system(declarations: Iterable[AssuranceFindingDeclaration], *, tenant_id: str,
                      system_id: str, system_version: str = "",
                      as_of: datetime) -> tuple[AssuranceFindingDeclaration, ...]:
    """One system's current findings, optionally narrowed to one version."""

    tenant = require_nonempty(tenant_id, "tenant_id")
    system = require_nonempty(system_id, "system_id")
    version = optional_text(system_version, "system_version")
    return declared_at(
        (d for d in declarations
         if d.tenant_id == tenant and d.system_id == system
         and (not version or d.system_version == version)), as_of)


def select_for_evidence(declarations: Iterable[AssuranceFindingDeclaration], *, tenant_id: str,
                        evidence_id: str, as_of: datetime) -> tuple[AssuranceFindingDeclaration, ...]:
    """Every current declaration carrying one evidence reference, by its own id.

    This is the lookup both AE-4 routes share: a consumer holding an evidence id
    finds the declaration that binds it, and nothing else.
    """

    tenant = require_nonempty(tenant_id, "tenant_id")
    ref = require_nonempty(evidence_id, "evidence_id")
    return declared_at((d for d in declarations
                        if d.tenant_id == tenant and d.evidence_id == ref), as_of)


def select_by_finding(declarations: Iterable[AssuranceFindingDeclaration], *, tenant_id: str,
                      finding_label: str, as_of: datetime) -> tuple[AssuranceFindingDeclaration, ...]:
    """Everything carrying one declared finding.

    The label is matched **exactly and uninterpreted** (AE-3): the package knows no
    taxonomy, no severity and no ordering, so it can neither widen nor narrow a
    caller's query by reasoning about what a finding means.
    """

    tenant = require_nonempty(tenant_id, "tenant_id")
    label = require_nonempty(finding_label, "finding_label")
    return declared_at((d for d in declarations
                        if d.tenant_id == tenant and d.finding_label == label), as_of)


def select_by_exercise(declarations: Iterable[AssuranceFindingDeclaration], *, tenant_id: str,
                       exercise_ref: str, as_of: datetime) -> tuple[AssuranceFindingDeclaration, ...]:
    """Everything one exercise produced, matched exactly by its reference."""

    tenant = require_nonempty(tenant_id, "tenant_id")
    ref = require_nonempty(exercise_ref, "exercise_ref")
    return declared_at((d for d in declarations
                        if d.tenant_id == tenant and d.exercise_ref == ref), as_of)


def supersession_chain(declarations: Iterable[AssuranceFindingDeclaration],
                       declaration_id: str) -> tuple[AssuranceFindingDeclaration, ...]:
    """The chain a declaration supersedes, newest first — history, not a current answer.

    Deliberately **not** filtered by instant: a superseded declaration is normally
    outside its window, and the chain exists to reconstruct what was declared when.

    **Only admissible links are walked.** A ``supersedes`` pointing at a declaration
    the package's own rule rejects — a different tenant, a different system, or an
    unchanged declaration — ends the chain there rather than splicing an unrelated
    record into a history. A cycle terminates rather than looping.
    """

    by_id = {d.declaration_id: d for d in declarations}
    current = by_id.get(require_nonempty(declaration_id, "declaration_id"))
    chain: list[AssuranceFindingDeclaration] = []
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
class AssuranceFindingPort(Protocol):
    """The read-only seam a composition root types against.

    **No implementation ships in 0.1.0.** A Protocol is a seam, not an adapter:
    declaring it lets a consumer depend on a stable surface while everything that
    could produce, judge or forward a finding stays outside this package.

    Every method takes the caller's instant and returns only declarations in force
    at it. There is no write method, by construction.
    """

    def get_declaration(self, declaration_id: str) -> Optional[AssuranceFindingDeclaration]: ...

    def declarations_for_tenant(self, *, tenant_id: str,
                                as_of: datetime) -> tuple[AssuranceFindingDeclaration, ...]: ...

    def declarations_for_system(self, *, tenant_id: str, system_id: str,
                                system_version: str = "",
                                as_of: datetime) -> tuple[AssuranceFindingDeclaration, ...]: ...

    def declarations_for_evidence(self, *, tenant_id: str, evidence_id: str,
                                  as_of: datetime) -> tuple[AssuranceFindingDeclaration, ...]: ...

    def declarations_by_finding(self, *, tenant_id: str, finding_label: str,
                                as_of: datetime) -> tuple[AssuranceFindingDeclaration, ...]: ...
