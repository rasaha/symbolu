"""The change-effect policy artifact: three members, atomically versioned.

    THIS PACKAGE CARRIES A POLICY ARTIFACT'S SHAPE. IT RESOLVES NOTHING, CLASSIFIES
    NOTHING, ROUTES NOTHING, PROJECTS NOTHING AND AUTHORIZES NOTHING.

Scoped by ``docs/architecture/ADR_UGENCE_CHANGE_EFFECT_CLASSIFIER_SCOPING.md`` (CEC-2 as
amended 2026-09-13) and Stage 1 §3.2. The artifact holds three members and they version
together, so changing any one of them requires a new artifact version:

1. the **protected-registry list** — which registries are protected, and what admits a
   member to each. It states no effect class, no route and no outcome;
2. the **delegation table** — **empty**, and in Stage 1 necessarily so. There is no entry
   type in this package to populate it with, which is the strongest available form of
   "D1, D3, D4 and D5 are not encoded";
3. a **mapping coordinate** — a complete, family-neutral ``PolicyCoordinate`` naming a
   separately governed ClosureBundleMapping. A *reference*, never the mapping. **No
   mapping content is defined, embedded or activated here**: no obligation-to-effect
   rules, no required-primitive table, no predicates, no D-entry semantics or parameters.

Two refusals are structural rather than advisory. A sentinel, placeholder or fabricated
mapping coordinate is refused, because a reference that names nothing real would pass
every check that merely tests presence. And an artifact with no valid mapping coordinate
cannot enter an operative lifecycle state (ruling 6): absence is legitimate and visible,
and what it forecloses is operation, not existence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ugence_policy_authority.api import PolicyCoordinate

from .errors import (
    ChangeEffectPolicyFieldError,
    DelegationEntryRefused,
    MappingCoordinateRefused,
    OperativeWithoutMappingRefused,
)
from .identifiers import (
    ACTIVE_LIFECYCLE_STATE,
    ADMITTED_LIFECYCLE_STATES,
    ADMITTED_POLICY_SCOPES,
    CHANGE_EFFECT_POLICY_FAMILY,
    MAPPING_POLICY_FAMILY,
    POLICY_SCOPE_GLOBAL,
    POLICY_SCOPE_TENANT,
    PROTECTED_REGISTRY_IDS,
)

__all__ = [
    "ProtectedRegistryEntry",
    "ChangeEffectPolicyMetadata",
    "ChangeEffectClassificationPolicy",
]

#: Tokens a placeholder tends to be spelled with. A coordinate whose policy identity or
#: version is one of these is refused: it is a promise to fill something in later wearing
#: the shape of a governed reference.
_SENTINEL_TOKENS = frozenset({
    "tbd", "todo", "none", "null", "nil", "unset", "unknown", "pending", "placeholder",
    "sentinel", "example", "sample", "dummy", "fake", "test", "xxx", "n/a", "na",
})


def _require_str(value: object, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ChangeEffectPolicyFieldError(f"{name} must be a string")
    if not allow_empty and not value.strip():
        raise ChangeEffectPolicyFieldError(f"{name} must not be empty")
    return value


def _require_digest(value: object, name: str) -> str:
    text = _require_str(value, name)
    if len(text) != 64 or any(c not in "0123456789abcdef" for c in text):
        raise ChangeEffectPolicyFieldError(
            f"{name} must be a full 64-character lowercase SHA-256 hex digest"
        )
    return text


def _require_tzaware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ChangeEffectPolicyFieldError(f"{name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise ChangeEffectPolicyFieldError(
            f"{name} must be timezone-aware; a naive datetime is never assumed to be UTC"
        )
    return value


@dataclass(frozen=True)
class ProtectedRegistryEntry:
    """One protected registry, and what admits a member to it.

    ``admission_rule`` is descriptive prose, not a predicate: it says what makes
    something a member, for a human reading the policy. Nothing here evaluates it, and
    nothing derives an effect class, a route or an outcome from it.
    """

    registry_id: str
    admission_rule: str

    def __post_init__(self) -> None:
        _require_str(self.registry_id, "ProtectedRegistryEntry.registry_id")
        if self.registry_id not in PROTECTED_REGISTRY_IDS:
            raise ChangeEffectPolicyFieldError(
                f"registry_id {self.registry_id!r} is not one of "
                f"{list(PROTECTED_REGISTRY_IDS)}"
            )
        _require_str(self.admission_rule, "ProtectedRegistryEntry.admission_rule")


@dataclass(frozen=True)
class ChangeEffectPolicyMetadata:
    """The identity envelope the shared authority reads through the adapter.

    This family's own type rather than a borrowed one: the authority is family-neutral,
    and a family that reused another family's envelope would take on that family's
    dependency for field reuse alone.

    ``policy_family`` is a **property, not a field**: it is fixed for this family, so it
    is not a value an author may set. It is bound into the signed identity through the
    ``PolicyCoordinate`` the adapter derives.
    """

    policy_id: str
    version: str
    content_digest: str
    scope: str
    lifecycle_state: str
    tenant_id: str = ""
    supersedes_ref: str = ""
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None

    def __post_init__(self) -> None:
        _require_str(self.policy_id, "ChangeEffectPolicyMetadata.policy_id")
        _require_str(self.version, "ChangeEffectPolicyMetadata.version")
        _require_digest(self.content_digest, "ChangeEffectPolicyMetadata.content_digest")
        _require_str(self.scope, "ChangeEffectPolicyMetadata.scope")
        if self.scope not in ADMITTED_POLICY_SCOPES:
            raise ChangeEffectPolicyFieldError(
                f"scope {self.scope!r} is not one of {sorted(ADMITTED_POLICY_SCOPES)}"
            )
        _require_str(self.lifecycle_state, "ChangeEffectPolicyMetadata.lifecycle_state")
        if self.lifecycle_state not in ADMITTED_LIFECYCLE_STATES:
            raise ChangeEffectPolicyFieldError(
                f"lifecycle_state {self.lifecycle_state!r} is not one of "
                f"{sorted(ADMITTED_LIFECYCLE_STATES)}"
            )
        _require_str(self.tenant_id, "ChangeEffectPolicyMetadata.tenant_id", allow_empty=True)
        _require_str(
            self.supersedes_ref, "ChangeEffectPolicyMetadata.supersedes_ref", allow_empty=True
        )

        # Scope and tenant are one fact, not two, exactly as the sibling family has it.
        if self.scope == POLICY_SCOPE_GLOBAL and self.tenant_id != "":
            raise ChangeEffectPolicyFieldError(
                "a GLOBAL-scope policy must carry the canonical empty tenant component"
            )
        if self.scope == POLICY_SCOPE_TENANT and not self.tenant_id.strip():
            raise ChangeEffectPolicyFieldError(
                "a TENANT-scope policy must name a non-empty tenant"
            )

        for name in ("effective_from", "effective_to"):
            value = getattr(self, name)
            if value is not None:
                _require_tzaware(value, f"ChangeEffectPolicyMetadata.{name}")
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to <= self.effective_from
        ):
            raise ChangeEffectPolicyFieldError(
                "effective_to must be strictly after effective_from; the interval is "
                "half-open [from, to) and an empty one can never admit a resolution"
            )

    @property
    def policy_family(self) -> str:
        return CHANGE_EFFECT_POLICY_FAMILY


def _refuse_sentinel_coordinate(coordinate: PolicyCoordinate) -> PolicyCoordinate:
    """Refuse a coordinate that names nothing real."""

    if coordinate.policy_family != MAPPING_POLICY_FAMILY:
        raise MappingCoordinateRefused(
            f"a mapping coordinate must name the {MAPPING_POLICY_FAMILY!r} family, not "
            f"{coordinate.policy_family!r}; a reference to the wrong thing is not better "
            f"than a reference to nothing"
        )
    for name in ("policy_id", "version"):
        token = getattr(coordinate, name).strip().lower()
        if token in _SENTINEL_TOKENS:
            raise MappingCoordinateRefused(
                f"mapping coordinate {name} {getattr(coordinate, name)!r} is a placeholder"
            )
    digest = coordinate.content_digest
    if len(set(digest)) == 1:
        raise MappingCoordinateRefused(
            "a mapping coordinate's content digest of one repeated character is a "
            "fabrication, not a digest"
        )
    return coordinate


@dataclass(frozen=True)
class ChangeEffectClassificationPolicy:
    """The artifact. Three members, one version, one content digest.

    ``mapping_coordinate`` is ``None`` in the initial shipped artifact and that is
    lawful (ruling 6). What it forecloses is operation: such an artifact cannot carry an
    operative lifecycle state, and supports no COMPLETED closure, because the closure's
    bundle would be derived by a mapping the artifact does not name.
    """

    metadata: ChangeEffectPolicyMetadata
    #: What the artifact applies under. Pinned, per CEC-2, so a reader can tell which
    #: constitution and which intent specification this version was issued against.
    constitution_ref: str
    intent_specification_refs: tuple[str, ...]
    protected_registries: tuple[ProtectedRegistryEntry, ...]
    #: **Empty, and in Stage 1 necessarily so.** No entry type exists in this package.
    delegation_table: tuple = ()
    #: A reference to a separately governed mapping, or ``None``. Never the mapping.
    mapping_coordinate: Optional[PolicyCoordinate] = None

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, ChangeEffectPolicyMetadata):
            raise ChangeEffectPolicyFieldError(
                "ChangeEffectClassificationPolicy must carry a ChangeEffectPolicyMetadata"
            )
        _require_str(self.constitution_ref, "constitution_ref")
        if not self.intent_specification_refs:
            raise ChangeEffectPolicyFieldError(
                "an artifact pins at least one intent specification it applies under"
            )
        for ref in self.intent_specification_refs:
            _require_str(ref, "intent_specification_refs[]")

        if len(self.protected_registries) != len(PROTECTED_REGISTRY_IDS):
            raise ChangeEffectPolicyFieldError(
                f"the protected-registry list carries all {len(PROTECTED_REGISTRY_IDS)} "
                f"registries; a partial list would silently unprotect the rest"
            )
        seen = [entry.registry_id for entry in self.protected_registries]
        if sorted(seen) != sorted(PROTECTED_REGISTRY_IDS):
            raise ChangeEffectPolicyFieldError(
                "the protected-registry list must name each registry exactly once"
            )

        if self.delegation_table != ():
            raise DelegationEntryRefused(
                "Stage 1 ships an empty delegation table, not one populated with inactive "
                "entries. D1, D3, D4 and D5 and their parameters, predicates and "
                "anticipated structures are outside Stage 1 and require separate review "
                "and activation."
            )

        if self.mapping_coordinate is not None:
            if not isinstance(self.mapping_coordinate, PolicyCoordinate):
                raise MappingCoordinateRefused(
                    "mapping_coordinate must be a PolicyCoordinate; a reduced ad-hoc "
                    "reference would omit tenant, scope, family or policy identity"
                )
            _refuse_sentinel_coordinate(self.mapping_coordinate)
        elif self.metadata.lifecycle_state == ACTIVE_LIFECYCLE_STATE:
            raise OperativeWithoutMappingRefused(
                "an artifact with no mapping coordinate cannot enter an operative "
                "lifecycle state, and supports no COMPLETED closure"
            )

    @property
    def is_operative(self) -> bool:
        """Whether this artifact could be operative at all. Not a resolution.

        A pure reading of two fields it already carries. It consults no registry, reads
        no trust configuration and grants nothing: an artifact that reports ``True`` is
        still inert until something resolves it, and nothing here resolves.
        """

        return (
            self.metadata.lifecycle_state == ACTIVE_LIFECYCLE_STATE
            and self.mapping_coordinate is not None
        )
