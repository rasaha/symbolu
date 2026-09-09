"""Mirrored governed-role overlap detection — diagnostic evidence, never enforcement.

`ACC-OVL-2` splits this invariant deliberately: **Policy Authority owns
enforcement** at issuance and resolution; this package **mirrors the check and
produces diagnostic evidence**. The split is not redundancy for its own sake —
detection that lives where enforcement lives is a single point of failure, and
this package must remain unable to authorize anything.

What this module is, exactly
----------------------------
A **report**. :func:`governed_role_overlaps` reads constitutions a caller already
holds and says which governed roles are claimed by more than one of them over
overlapping effective periods. It returns findings; it raises nothing, refuses
nothing, and no caller of it is prevented from doing anything by it.

`[R]` **It is not enforcement and must not be mistaken for it.** Nothing here
issues, resolves, signs or stores. A deployment that consulted only this module
and skipped the authority would have no enforcement at all — which is precisely
why `ACC-OVL-2` states that conformance *cannot be the sole enforcement
boundary*. Enforcement is `ugence_policy_authority`'s
``PolicyExclusivityError`` at issuance and ``EXCLUSIVITY_CONFLICT`` at
resolution.

What its input is worth
-----------------------
`[G]` The constitutions handed to :func:`governed_role_overlaps` are **the
caller's assertion** about what is effective, exactly as presented role facts are
under `ACC-FACTS`. This module does not resolve them, does not check that they
were issued, and cannot tell whether one has since been revoked, superseded or
suspended. A clean report is therefore evidence about *what the caller
presented*, never a warrant that no overlap exists in the registry. The
authority's own refusal is the only statement that carries that weight.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence, Tuple

__all__ = ["GovernedRoleOverlap", "governed_role_overlaps"]


@dataclass(frozen=True)
class GovernedRoleOverlap:
    """One governed role claimed by two constitutions over overlapping periods.

    Carries the role and both coordinates' identifying parts, because a finding
    an operator cannot act on is not evidence. It carries **no disposition**: it
    does not say which constitution should win, and nothing in this package
    decides that (`OD-C3=B`).
    """

    governed_role_ref: str
    tenant_id: str
    scope: str
    first_policy_id: str
    first_version: str
    second_policy_id: str
    second_version: str


def _overlaps(
    a_from: Optional[datetime],
    a_to: Optional[datetime],
    b_from: Optional[datetime],
    b_to: Optional[datetime],
) -> bool:
    """Half-open ``[from, to)`` overlap — the authority's rule, mirrored.

    Deliberately the same comparison the authority makes, so a report here and a
    refusal there agree about what "simultaneously effective" means. A clean
    handover — one period ending exactly as the next begins — is not an overlap.
    """

    if a_to is not None and b_from is not None and a_to <= b_from:
        return False
    if b_to is not None and a_from is not None and b_to <= a_from:
        return False
    return True


def governed_role_overlaps(
    constitutions: Sequence[object],
) -> Tuple[GovernedRoleOverlap, ...]:
    """Report every governed role two of these constitutions both claim.

    ``constitutions`` are ``AgentConstitutionPolicy`` artifacts the caller
    presents. Only constitutions sharing a **tenant and scope** are compared,
    matching the authority's own key — a role governed in one tenant is untouched
    by the same name in another.

    Findings are returned in a deterministic order — by role, then by the two
    policy identities — so a report never depends on the order the caller
    happened to pass its inputs in. That is the same property `ACC-OVL-3` demands
    of enforcement, held here for a different reason: a diagnostic whose output
    reorders between runs is one nobody can diff.
    """

    holders: dict = {}
    for artifact in constitutions:
        metadata = getattr(artifact, "metadata", None)
        refs = getattr(artifact, "governed_role_refs", ()) or ()
        if metadata is None:
            continue
        for ref in refs:
            key = (ref, getattr(metadata, "tenant_id", ""), getattr(metadata, "scope", ""))
            holders.setdefault(key, []).append(metadata)

    findings = []
    for (ref, tenant_id, scope), entries in holders.items():
        for index, first in enumerate(entries):
            for second in entries[index + 1 :]:
                if not _overlaps(
                    getattr(first, "effective_from", None),
                    getattr(first, "effective_to", None),
                    getattr(second, "effective_from", None),
                    getattr(second, "effective_to", None),
                ):
                    continue
                pair = sorted(
                    [
                        (getattr(first, "policy_id", ""), getattr(first, "version", "")),
                        (getattr(second, "policy_id", ""), getattr(second, "version", "")),
                    ]
                )
                findings.append(
                    GovernedRoleOverlap(
                        governed_role_ref=ref,
                        tenant_id=tenant_id,
                        scope=scope,
                        first_policy_id=pair[0][0],
                        first_version=pair[0][1],
                        second_policy_id=pair[1][0],
                        second_version=pair[1][1],
                    )
                )

    return tuple(
        sorted(
            findings,
            key=lambda f: (
                f.governed_role_ref,
                f.tenant_id,
                f.scope,
                f.first_policy_id,
                f.first_version,
                f.second_policy_id,
                f.second_version,
            ),
        )
    )
