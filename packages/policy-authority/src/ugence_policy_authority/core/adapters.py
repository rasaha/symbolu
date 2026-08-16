"""The policy-family adapter seam (ADR §10).

This is the boundary that keeps the authority *shared*. The generic core knows
nothing about any policy family: it never imports a family type, never branches
on one, and never canonicalizes a family artifact itself. Everything
family-specific arrives through a registered :class:`PolicyFamilyAdapter`.

Adding a second policy family means registering a second adapter. It requires
**no** change to issuance, signing, registry, resolution, or revocation code —
a property an automated test proves by registering a synthetic second family.

Family-neutral identity
-----------------------
The core identifies a policy version by a :class:`PolicyCoordinate`: a plain,
immutable tuple of strings. It is deliberately *not* any family's reference
type — the UVI adapter maps its ``PolicyReference`` onto a coordinate and back,
and a future family maps its own. Every component is part of the identity, so
resolution is exact and a floating reference is unrepresentable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from .canonical import framed_body_digest, require_nfc, require_tzaware
from .errors import PolicyAuthorityRequestError, UnsupportedPolicyArtifactError

__all__ = [
    "GLOBAL_TENANT",
    "PolicyCoordinate",
    "PolicyArtifactDescriptor",
    "PolicyFamilyAdapter",
    "AdapterRegistry",
]

#: The canonical tenant component of a GLOBAL-scope coordinate: the empty
#: string. A GLOBAL policy is not "tenant-less" in the sense of matching every
#: tenant — it carries exactly this component and matches only a request that
#: presents exactly this component.
GLOBAL_TENANT = ""

_HEX = frozenset("0123456789abcdef")


def _require_token(value: object, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise PolicyAuthorityRequestError(f"{name} must be a string")
    if not allow_empty and not value.strip():
        raise PolicyAuthorityRequestError(f"{name} must be a non-empty string")
    return require_nfc(value, path=name)


def _require_digest(value: object, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in _HEX for c in value):
        raise PolicyAuthorityRequestError(
            f"{name} must be a lowercase 64-char sha-256 hex digest"
        )
    return value


@dataclass(frozen=True)
class PolicyCoordinate:
    """The complete, exact, family-neutral identity of one policy version.

    Immutable and hashable. Every component participates in identity, so an
    exact-match lookup is the only lookup the registry can perform.
    """

    policy_family: str
    policy_id: str
    version: str
    content_digest: str
    scope: str
    tenant_id: str = GLOBAL_TENANT

    def __post_init__(self) -> None:
        _require_token(self.policy_family, "PolicyCoordinate.policy_family")
        _require_token(self.policy_id, "PolicyCoordinate.policy_id")
        _require_token(self.version, "PolicyCoordinate.version")
        _require_digest(self.content_digest, "PolicyCoordinate.content_digest")
        _require_token(self.scope, "PolicyCoordinate.scope")
        _require_token(self.tenant_id, "PolicyCoordinate.tenant_id", allow_empty=True)

    @property
    def identity_slot(self) -> tuple[str, str, str, str, str]:
        """The version *slot* this coordinate occupies, excluding the digest.

        Two coordinates sharing a slot but differing in digest are a conflict,
        not two coexisting versions.
        """

        return (self.policy_family, self.policy_id, self.version, self.scope, self.tenant_id)


@dataclass(frozen=True)
class PolicyArtifactDescriptor:
    """Everything the core needs to know about a family artifact.

    Produced by the adapter; consumed by the core. The core reads only these
    fields — it never reaches back into the artifact.
    """

    adapter_id: str
    policy_type: str
    coordinate: PolicyCoordinate
    declared_content_digest: str
    canonical_projection: Mapping[str, Any]
    lifecycle_label: str
    lifecycle_is_active: bool
    supersedes_ref: str = ""
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None

    def __post_init__(self) -> None:
        _require_token(self.adapter_id, "PolicyArtifactDescriptor.adapter_id")
        _require_token(self.policy_type, "PolicyArtifactDescriptor.policy_type")
        if not isinstance(self.coordinate, PolicyCoordinate):
            raise PolicyAuthorityRequestError(
                "PolicyArtifactDescriptor.coordinate must be a PolicyCoordinate"
            )
        _require_digest(
            self.declared_content_digest, "PolicyArtifactDescriptor.declared_content_digest"
        )
        if not isinstance(self.canonical_projection, Mapping):
            raise PolicyAuthorityRequestError(
                "PolicyArtifactDescriptor.canonical_projection must be a mapping"
            )
        _require_token(self.lifecycle_label, "PolicyArtifactDescriptor.lifecycle_label")
        if not isinstance(self.lifecycle_is_active, bool):
            raise PolicyAuthorityRequestError(
                "PolicyArtifactDescriptor.lifecycle_is_active must be a bool"
            )
        if not isinstance(self.supersedes_ref, str):
            raise PolicyAuthorityRequestError(
                "PolicyArtifactDescriptor.supersedes_ref must be a string"
            )
        for name in ("effective_from", "effective_to"):
            value = getattr(self, name)
            if value is not None:
                require_tzaware(value, path=f"PolicyArtifactDescriptor.{name}")

    @property
    def declares_supersession(self) -> bool:
        """Whether a *semantically non-empty* supersession reference is present.

        Emptiness is defined by ``supersedes_ref.strip()``: absent, empty, and
        whitespace-only are all "no supersession". Anything else is a non-empty
        unstructured reference, which v0.1 refuses to issue.
        """

        return bool(self.supersedes_ref.strip())

    def body_digest(self) -> str:
        """The computed canonical body digest of this artifact."""

        return framed_body_digest(
            adapter_id=self.adapter_id,
            policy_type=self.policy_type,
            projection=self.canonical_projection,
        )


@runtime_checkable
class PolicyFamilyAdapter(Protocol):
    """Teaches the core about exactly one policy family.

    An adapter is the *only* place family semantics may live. It must be
    deterministic and side-effect free: the core may call it more than once for
    the same artifact and must get identical answers.
    """

    @property
    def adapter_id(self) -> str:
        """Stable identifier, bound into every body digest this adapter frames."""
        ...

    def recognizes(self, artifact: object) -> bool:
        """Whether this adapter owns ``artifact``'s exact runtime type."""
        ...

    def describe(self, artifact: object) -> PolicyArtifactDescriptor:
        """Validate ``artifact`` structurally and project it for the core.

        Raises a
        :class:`~ugence_policy_authority.core.errors.PolicyAuthorityRequestError`
        subclass if the artifact is malformed for this family.
        """
        ...

    def coordinate_for(self, reference: object) -> Optional[PolicyCoordinate]:
        """Map a family-native reference onto a coordinate, or ``None``.

        Lets callers keep using their family's own reference type at the public
        API without the core ever learning that type.
        """
        ...


@dataclass(frozen=True)
class AdapterRegistry:
    """An immutable, ordered set of registered policy-family adapters."""

    adapters: tuple[PolicyFamilyAdapter, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        coerced = tuple(self.adapters)
        seen: set[str] = set()
        for adapter in coerced:
            for attribute in ("adapter_id", "recognizes", "describe", "coordinate_for"):
                if not hasattr(adapter, attribute):
                    raise PolicyAuthorityRequestError(
                        f"{type(adapter).__name__} does not implement PolicyFamilyAdapter "
                        f"(missing {attribute!r})"
                    )
            if adapter.adapter_id in seen:
                raise PolicyAuthorityRequestError(
                    f"duplicate adapter_id {adapter.adapter_id!r}"
                )
            seen.add(adapter.adapter_id)
        object.__setattr__(self, "adapters", coerced)

    def with_adapter(self, adapter: PolicyFamilyAdapter) -> "AdapterRegistry":
        """Return a new registry with ``adapter`` appended."""

        return AdapterRegistry(self.adapters + (adapter,))

    def adapter_for(self, artifact: object) -> PolicyFamilyAdapter:
        """Return the one adapter that recognizes ``artifact``, or refuse."""

        for adapter in self.adapters:
            if adapter.recognizes(artifact):
                return adapter
        raise UnsupportedPolicyArtifactError(
            f"no registered policy-family adapter recognizes "
            f"{type(artifact).__name__!r} (registered: "
            f"{', '.join(a.adapter_id for a in self.adapters) or 'none'})"
        )

    def describe(self, artifact: object) -> PolicyArtifactDescriptor:
        """Describe ``artifact`` through its owning adapter."""

        descriptor = self.adapter_for(artifact).describe(artifact)
        if not isinstance(descriptor, PolicyArtifactDescriptor):
            raise PolicyAuthorityRequestError(
                "a policy-family adapter must return a PolicyArtifactDescriptor"
            )
        return descriptor

    def coordinate_for(self, reference: object) -> PolicyCoordinate:
        """Normalize a coordinate or a family-native reference into a coordinate."""

        if isinstance(reference, PolicyCoordinate):
            return reference
        for adapter in self.adapters:
            coordinate = adapter.coordinate_for(reference)
            if coordinate is not None:
                if not isinstance(coordinate, PolicyCoordinate):
                    raise PolicyAuthorityRequestError(
                        "a policy-family adapter must return a PolicyCoordinate"
                    )
                return coordinate
        raise UnsupportedPolicyArtifactError(
            f"no registered policy-family adapter maps {type(reference).__name__!r} "
            "onto a PolicyCoordinate"
        )
