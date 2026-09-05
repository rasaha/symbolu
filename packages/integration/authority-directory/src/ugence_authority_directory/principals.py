"""Principals and scopes — references, never identities.

A :class:`PrincipalRef` is a **non-secret directory handle**: an id, a kind, and an
optional display reference. It is never a credential, never a token, and never proof
that anyone is who they claim. Authentication stays at the IdP, behind Decision
Authority's ``IdentityProvider``
(``packages/capabilities/decision-authority/.../identity/provider.py:24``); this
package never learns the answer and never returns an ``ActorType``.

``PrincipalKind`` deliberately carries the same member *values* as the approval
workflow's ``ApproverKind``
(``packages/integration/approval-workflow/.../eligibility.py:38``), so a projection of
a grant is structurally usable by that package's rules without either package
importing the other. Both are ``str`` enums, so equal values compare and hash equal.

A **scope** is a ``/``-separated path. One scope covers another when they are equal or
the other is a strict descendant; a sibling or an ancestor is never covered. That is
the whole of the subset rule delegation relies on.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ._canon import optional_text, require_nonempty
from .errors import ContractViolation

__all__ = ["PrincipalKind", "PrincipalRef", "SCOPE_SEPARATOR", "scope_covers", "require_scope"]

SCOPE_SEPARATOR = "/"


class PrincipalKind(str, Enum):
    """What kind of principal a grant is held by. Recorded, never authenticated."""

    HUMAN = "HUMAN"
    COMMITTEE = "COMMITTEE"
    DELEGATED_POLICY = "DELEGATED_POLICY"
    SERVICE = "SERVICE"
    AI = "AI"


def require_scope(value: object, name: str) -> str:
    """A scope is a non-empty ``/``-separated path with no empty or wildcard segment.

    There is no ``*``: a grant that would cover everything must say so by naming the
    root it covers, so no scope is ever silently unbounded.
    """

    text = require_nonempty(value, name)
    segments = text.split(SCOPE_SEPARATOR)
    for segment in segments:
        if not segment.strip():
            raise ContractViolation(f"{name} has an empty path segment: {text!r}")
        if segment.strip() != segment:
            raise ContractViolation(f"{name} has a padded path segment: {text!r}")
        if "*" in segment:
            raise ContractViolation(
                f"{name} may not contain a wildcard; name the scope you cover: {text!r}")
    return text


def scope_covers(outer: str, inner: str) -> bool:
    """True when ``outer`` is ``inner`` or a strict ancestor of it.

    ``a/b`` covers ``a/b`` and ``a/b/c``; it does not cover ``a``, ``a/bc``, or ``a/c``.
    """

    outer = require_scope(outer, "outer scope")
    inner = require_scope(inner, "inner scope")
    return inner == outer or inner.startswith(outer + SCOPE_SEPARATOR)


@dataclass(frozen=True)
class PrincipalRef:
    """A non-secret reference to a principal the directory reports on.

    ``quorum`` is meaningful only for a ``COMMITTEE`` — how many of its members the
    organization requires — and must be zero for every other kind. The directory
    **reports** the quorum; it never counts votes and never decides one was met.
    """

    principal_id: str
    principal_kind: PrincipalKind
    display_ref: str = ""
    quorum: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "principal_id",
                           require_nonempty(self.principal_id, "PrincipalRef.principal_id"))
        object.__setattr__(self, "display_ref",
                           optional_text(self.display_ref, "PrincipalRef.display_ref"))
        if not isinstance(self.principal_kind, PrincipalKind):
            raise ContractViolation("PrincipalRef.principal_kind must be a PrincipalKind member")
        if not isinstance(self.quorum, int) or isinstance(self.quorum, bool):
            raise ContractViolation("PrincipalRef.quorum must be an integer")
        if self.principal_kind is PrincipalKind.COMMITTEE:
            if self.quorum < 1:
                raise ContractViolation("a COMMITTEE requires a quorum of at least 1")
        elif self.quorum:
            raise ContractViolation(
                f"quorum is meaningless for {self.principal_kind.value} and must be 0")

    @property
    def is_committee(self) -> bool:
        return self.principal_kind is PrincipalKind.COMMITTEE

    def to_dict(self) -> dict:
        return {"principal_id": self.principal_id, "principal_kind": self.principal_kind.value,
                "display_ref": self.display_ref, "quorum": self.quorum}

    @classmethod
    def from_dict(cls, d: dict) -> "PrincipalRef":
        return cls(principal_id=d["principal_id"],
                   principal_kind=PrincipalKind(d["principal_kind"]),
                   display_ref=d.get("display_ref", ""), quorum=int(d.get("quorum", 0)))
