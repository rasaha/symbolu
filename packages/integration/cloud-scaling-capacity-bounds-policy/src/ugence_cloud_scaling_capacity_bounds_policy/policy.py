"""The Cloud Scaling capacity-bounds policy artifact.

**Why this family exists.** No shipped policy family states a capacity bound. The
Cloud Scaling authorization candidate already carries ``max_permitted_magnitude``
and ``max_permitted_delta`` and already enforces ``requested <= max_permitted`` —
but those maxima are *self-asserted by the caller*, bound to no signed policy.
Until an authority can issue a bound, there is nothing authentic to reconcile
them against. This family is that issuable bound.

**What it is not.** It authorizes nothing, evaluates nothing, and reads no
runtime state. It is a declarative artifact the shared Policy Authority issues,
signs, registers, resolves and revokes like any other family. Whether a
particular requested magnitude is permitted is a question for a later
reconciliation subphase; this package does not answer it and holds no candidate
type with which to ask it.

**Selector semantics, stated once.** A bound applies to one ``action_type``
optionally narrowed by ``resource_class``. A bound whose ``resource_class`` is
empty is the family's default for that action type. Two bounds may not share a
selector — the applicable bound must be unambiguous by construction, not by a
resolution rule applied later. ``action_type`` is a free token here: this package
deliberately does **not** import the Phase 4C/D-4 canonical action-type set,
because doing so would drag the Risk Authority into a leaf policy family.
Reconciling this family's action tokens against that ratified set belongs to the
comparison subphase, and is recorded as deferred rather than silently assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple

from .errors import (
    CapacityBoundsDuplicateError,
    CapacityBoundsFieldError,
    CapacityBoundsOrderingError,
    CapacityBoundsRejectionReason as Reason,
)
from .identifiers import (
    CAPACITY_BOUNDS_POLICY_FAMILY,
    POLICY_SCOPE_GLOBAL,
    POLICY_SCOPE_TENANT,
    SUPPORTED_LIFECYCLE_STATES,
    SUPPORTED_POLICY_SCOPES,
)

__all__ = [
    "CapacityBound",
    "CapacityBoundsPolicy",
    "CapacityBoundsPolicyMetadata",
    "PLACEHOLDER_CONTENT_DIGEST",
]

_HEX = frozenset("0123456789abcdef")

#: The digest an artifact declares while its real digest is still being computed.
#: The adapter's projection *removes* ``metadata.content_digest`` entirely, so this
#: value never participates in a body digest and no fixed point is involved.
PLACEHOLDER_CONTENT_DIGEST = "0" * 64


def _require_token(value: object, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise CapacityBoundsFieldError(
            f"{name} must be a string", reason=Reason.FIELD_NOT_A_STRING
        )
    if not allow_empty and not value.strip():
        raise CapacityBoundsFieldError(
            f"{name} must be a non-empty string", reason=Reason.FIELD_EMPTY
        )
    return value


def _require_digest(value: object, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in _HEX for c in value):
        raise CapacityBoundsFieldError(
            f"{name} must be a lowercase 64-char sha-256 hex digest",
            reason=Reason.CONTENT_DIGEST_MALFORMED,
        )
    return value


def _require_bound_magnitude(value: object, name: str) -> int:
    """A non-negative, exactly-``int`` magnitude.

    ``bool`` is refused explicitly: it is a subclass of ``int``, and a bound of
    ``True`` silently meaning ``1`` is exactly the kind of coercion a policy
    artifact must not perform.
    """

    if isinstance(value, bool) or not isinstance(value, int):
        raise CapacityBoundsFieldError(
            f"{name} must be an int (bool is not an int here)",
            reason=Reason.MAGNITUDE_NOT_AN_INT,
        )
    if value < 0:
        raise CapacityBoundsFieldError(
            f"{name} must be >= 0, got {value}", reason=Reason.MAGNITUDE_NEGATIVE
        )
    return value


def _require_tzaware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise CapacityBoundsFieldError(
            f"{name} must be a datetime", reason=Reason.TIMESTAMP_NOT_A_DATETIME
        )
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise CapacityBoundsFieldError(
            f"{name} must be timezone-aware; a naive datetime is never assumed to be UTC",
            reason=Reason.TIMESTAMP_NAIVE,
        )
    return value


@dataclass(frozen=True)
class CapacityBound:
    """One authenticated ceiling for one action type, optionally narrowed.

    ``max_permitted_magnitude`` bounds the absolute resulting magnitude.
    ``max_permitted_delta`` bounds the absolute size of the change. Both are
    ceilings; neither implies the other, and a delta ceiling above the magnitude
    ceiling is incoherent rather than merely generous.
    """

    action_type: str
    max_permitted_magnitude: int
    max_permitted_delta: int
    resource_class: str = ""

    def __post_init__(self) -> None:
        _require_token(self.action_type, "CapacityBound.action_type")
        _require_token(self.resource_class, "CapacityBound.resource_class", allow_empty=True)
        _require_bound_magnitude(
            self.max_permitted_magnitude, "CapacityBound.max_permitted_magnitude"
        )
        _require_bound_magnitude(
            self.max_permitted_delta, "CapacityBound.max_permitted_delta"
        )
        if self.max_permitted_delta > self.max_permitted_magnitude:
            raise CapacityBoundsOrderingError(
                f"max_permitted_delta {self.max_permitted_delta} exceeds "
                f"max_permitted_magnitude {self.max_permitted_magnitude}: a change larger "
                "than the largest permitted result cannot be reached under this bound",
                reason=Reason.BOUND_ORDERING_INCOHERENT,
            )

    @property
    def selector(self) -> Tuple[str, str]:
        """What this bound claims. Two bounds may not share one."""

        return (self.action_type, self.resource_class)


@dataclass(frozen=True)
class CapacityBoundsPolicyMetadata:
    """The identity envelope the shared authority reads through the adapter.

    Deliberately this family's own type rather than UVI's
    ``PolicyArtifactMetadata``: the authority is family-neutral, and a Cloud
    Scaling family that borrowed UVI's envelope would make UVI a dependency of
    Cloud Scaling for no reason beyond field reuse.
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
        _require_token(self.policy_id, "CapacityBoundsPolicyMetadata.policy_id")
        _require_token(self.version, "CapacityBoundsPolicyMetadata.version")
        _require_digest(
            self.content_digest, "CapacityBoundsPolicyMetadata.content_digest"
        )
        _require_token(self.scope, "CapacityBoundsPolicyMetadata.scope")
        if self.scope not in SUPPORTED_POLICY_SCOPES:
            raise CapacityBoundsFieldError(
                f"scope {self.scope!r} is not one of {sorted(SUPPORTED_POLICY_SCOPES)}",
                reason=Reason.SCOPE_UNSUPPORTED,
            )
        _require_token(
            self.lifecycle_state, "CapacityBoundsPolicyMetadata.lifecycle_state"
        )
        if self.lifecycle_state not in SUPPORTED_LIFECYCLE_STATES:
            raise CapacityBoundsFieldError(
                f"lifecycle_state {self.lifecycle_state!r} is not one of "
                f"{sorted(SUPPORTED_LIFECYCLE_STATES)}",
                reason=Reason.LIFECYCLE_STATE_UNSUPPORTED,
            )
        _require_token(
            self.tenant_id, "CapacityBoundsPolicyMetadata.tenant_id", allow_empty=True
        )
        _require_token(
            self.supersedes_ref,
            "CapacityBoundsPolicyMetadata.supersedes_ref",
            allow_empty=True,
        )

        # Scope and tenant are one fact, not two. A GLOBAL policy carries the
        # authority's canonical empty tenant component; a TENANT policy that
        # named no tenant would resolve for the global tenant instead.
        if self.scope == POLICY_SCOPE_GLOBAL and self.tenant_id != "":
            raise CapacityBoundsFieldError(
                "a GLOBAL-scope policy must carry the canonical empty tenant component",
                reason=Reason.GLOBAL_SCOPE_CARRIES_TENANT,
            )
        if self.scope == POLICY_SCOPE_TENANT and not self.tenant_id.strip():
            raise CapacityBoundsFieldError(
                "a TENANT-scope policy must name a non-empty tenant",
                reason=Reason.TENANT_SCOPE_NAMES_NO_TENANT,
            )

        for name in ("effective_from", "effective_to"):
            value = getattr(self, name)
            if value is not None:
                _require_tzaware(value, f"CapacityBoundsPolicyMetadata.{name}")
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to <= self.effective_from
        ):
            raise CapacityBoundsOrderingError(
                "effective_to must be strictly after effective_from; the interval is "
                "half-open [from, to) and an empty one can never admit a resolution",
                reason=Reason.EFFECTIVE_INTERVAL_EMPTY,
            )

    @property
    def policy_family(self) -> str:
        return CAPACITY_BOUNDS_POLICY_FAMILY


@dataclass(frozen=True)
class CapacityBoundsPolicy:
    """A signed, versioned statement of what capacity change is permitted.

    Carries at least one :class:`CapacityBound`. An empty policy is refused: a
    bounds artifact that bounds nothing would resolve ``RESOLVED`` and authorize
    the reader to conclude nothing, which is worse than having no policy at all
    because it looks like coverage.
    """

    metadata: CapacityBoundsPolicyMetadata
    bounds: Tuple[CapacityBound, ...] = field(default=())

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, CapacityBoundsPolicyMetadata):
            raise CapacityBoundsFieldError(
                "CapacityBoundsPolicy.metadata must be a CapacityBoundsPolicyMetadata",
                reason=Reason.METADATA_TYPE_MISMATCH,
            )
        if not isinstance(self.bounds, tuple):
            raise CapacityBoundsFieldError(
                "CapacityBoundsPolicy.bounds must be a tuple — a list is mutable and this "
                "artifact is digested",
                reason=Reason.BOUNDS_NOT_A_TUPLE,
            )
        if not self.bounds:
            raise CapacityBoundsFieldError(
                "CapacityBoundsPolicy.bounds must carry at least one bound",
                reason=Reason.BOUNDS_EMPTY,
            )
        for index, bound in enumerate(self.bounds):
            if type(bound) is not CapacityBound:
                raise CapacityBoundsFieldError(
                    f"CapacityBoundsPolicy.bounds[{index}] must be exactly a "
                    "CapacityBound",
                    reason=Reason.BOUND_TYPE_MISMATCH,
                )

        seen: set = set()
        for bound in self.bounds:
            if bound.selector in seen:
                raise CapacityBoundsDuplicateError(
                    f"two bounds claim selector {bound.selector!r}; the applicable bound "
                    "must be unambiguous by construction",
                    reason=Reason.DUPLICATE_SELECTOR,
                )
            seen.add(bound.selector)

    def bound_for(
        self, *, action_type: str, resource_class: str = ""
    ) -> Optional[CapacityBound]:
        """The most specific bound for a selector, or ``None``.

        Exact ``(action_type, resource_class)`` first, then the action type's
        default. Returning ``None`` means this policy states no bound for that
        selector — it never means "unbounded".
        """

        _require_token(action_type, "bound_for(action_type)")
        _require_token(resource_class, "bound_for(resource_class)", allow_empty=True)
        by_selector = {bound.selector: bound for bound in self.bounds}
        if (action_type, resource_class) in by_selector:
            return by_selector[(action_type, resource_class)]
        return by_selector.get((action_type, ""))
