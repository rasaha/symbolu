"""The Procurement policy artifact this family compiles from.

A Policy Authority resolution returns a *family* artifact. Only the family knows
what its artifact says, which is why ruling CR-2 puts this mapping here rather than
in the composition root or the compiler.

The parser is strict and total. It refuses an unknown key rather than ignoring it —
an ignored key is a governance statement silently dropped — and it refuses a missing
required one rather than defaulting it. Nothing is inferred: every value in the
resulting pack traces to a value the artifact stated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Tuple


class ProcurementArtifactError(ValueError):
    """The artifact does not state what a Procurement policy must state."""


@dataclass(frozen=True)
class ApprovalRole:
    """One ordered approval the policy requires."""

    role_label: str
    decision_scope: str


@dataclass(frozen=True)
class EvidenceRequirement:
    """One fact the policy requires before a decision may be made."""

    fact_key: str
    description: str = ""


@dataclass(frozen=True)
class ProhibitedFact:
    """A condition the policy forbids outright."""

    fact_key: str
    comparator: str
    value: Any


@dataclass(frozen=True)
class ProcurementPolicyArtifact:
    """Everything a Procurement policy states, and nothing more.

    ``declared_*`` fields are optional source-declared semantics. They reach the
    compiled workflow only when the policy states them; absent, they stay absent.
    """

    policy_id: str
    title: str
    document_version: str
    action_type: str
    amount_fact_key: str
    approval_threshold: int
    hard_limit: int
    approval_roles: Tuple[ApprovalRole, ...] = ()
    evidence_requirements: Tuple[EvidenceRequirement, ...] = ()
    prohibited_facts: Tuple[ProhibitedFact, ...] = ()
    declared_data_classifications: Tuple[str, ...] = ()
    declared_permission_intents: Tuple[str, ...] = ()
    declared_required_tools: Tuple[str, ...] = ()
    authority_level: str = ""

    def __post_init__(self) -> None:
        for name in ("policy_id", "title", "document_version", "action_type",
                     "amount_fact_key"):
            if not str(getattr(self, name)).strip():
                raise ProcurementArtifactError(f"artifact is missing '{name}'")
        if self.approval_threshold < 0 or self.hard_limit < 0:
            raise ProcurementArtifactError("bounds must be non-negative")
        if self.hard_limit < self.approval_threshold:
            raise ProcurementArtifactError(
                "the hard limit is below the approval threshold; the policy would "
                "forbid the very amounts it also routes for approval"
            )


_REQUIRED_KEYS = frozenset(
    {"policy_id", "title", "document_version", "action_type", "amount_fact_key",
     "approval_threshold", "hard_limit"}
)
_OPTIONAL_KEYS = frozenset(
    {"approval_roles", "evidence_requirements", "prohibited_facts",
     "declared_data_classifications", "declared_permission_intents",
     "declared_required_tools", "authority_level"}
)


def artifact_from_projection(projection: Mapping[str, Any]) -> ProcurementPolicyArtifact:
    """Parse a resolved artifact's canonical projection. Strict and total.

    An unknown key is a refusal, not something to ignore: the projection is the
    policy's own statement of itself, and quietly dropping part of it would compile
    a workflow that governs less than the policy says.
    """
    if not isinstance(projection, Mapping):
        raise ProcurementArtifactError("the artifact projection must be a mapping")
    keys = set(projection)
    unknown = sorted(keys - _REQUIRED_KEYS - _OPTIONAL_KEYS)
    if unknown:
        raise ProcurementArtifactError(
            f"the artifact states {unknown} which this builder does not model; "
            f"a governance statement must never be silently dropped"
        )
    missing = sorted(_REQUIRED_KEYS - keys)
    if missing:
        raise ProcurementArtifactError(f"the artifact does not state {missing}")

    return ProcurementPolicyArtifact(
        policy_id=str(projection["policy_id"]),
        title=str(projection["title"]),
        document_version=str(projection["document_version"]),
        action_type=str(projection["action_type"]),
        amount_fact_key=str(projection["amount_fact_key"]),
        approval_threshold=int(projection["approval_threshold"]),
        hard_limit=int(projection["hard_limit"]),
        approval_roles=tuple(
            ApprovalRole(role_label=str(r["role_label"]),
                         decision_scope=str(r["decision_scope"]))
            for r in projection.get("approval_roles", ())
        ),
        evidence_requirements=tuple(
            EvidenceRequirement(fact_key=str(e["fact_key"]),
                                description=str(e.get("description", "")))
            for e in projection.get("evidence_requirements", ())
        ),
        prohibited_facts=tuple(
            ProhibitedFact(fact_key=str(p["fact_key"]),
                           comparator=str(p["comparator"]), value=p.get("value"))
            for p in projection.get("prohibited_facts", ())
        ),
        declared_data_classifications=tuple(
            str(v) for v in projection.get("declared_data_classifications", ())
        ),
        declared_permission_intents=tuple(
            str(v) for v in projection.get("declared_permission_intents", ())
        ),
        declared_required_tools=tuple(
            str(v) for v in projection.get("declared_required_tools", ())
        ),
        authority_level=str(projection.get("authority_level", "")),
    )


__all__ = [
    "ProcurementPolicyArtifact",
    "ApprovalRole",
    "EvidenceRequirement",
    "ProhibitedFact",
    "ProcurementArtifactError",
    "artifact_from_projection",
]
