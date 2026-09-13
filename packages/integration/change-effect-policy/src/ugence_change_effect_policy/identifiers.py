"""Stable identifiers for the change-effect policy family.

Every constant here is bound into a digest, a coordinate, or both. Moving one moves an
artifact digest, which is the point: these are identity, not configuration.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "CHANGE_EFFECT_ADAPTER_ID",
    "CHANGE_EFFECT_POLICY_FAMILY",
    "CHANGE_EFFECT_POLICY_TYPE",
    "MAPPING_POLICY_FAMILY",
    "PROTECTED_REGISTRY_IDS",
    "POLICY_SCOPE_GLOBAL",
    "POLICY_SCOPE_TENANT",
    "ADMITTED_POLICY_SCOPES",
    "LIFECYCLE_DRAFT",
    "LIFECYCLE_APPROVED_ACTIVE",
    "LIFECYCLE_SUPERSEDED",
    "LIFECYCLE_WITHDRAWN",
    "ADMITTED_LIFECYCLE_STATES",
    "ACTIVE_LIFECYCLE_STATE",
]

#: Stable adapter identity, framed into every body digest this adapter produces.
CHANGE_EFFECT_ADAPTER_ID: Final[str] = "ugence.change-effect.policy/v1"

#: The ``policy_family`` component of every coordinate this family issues. The shared
#: authority identifies a version by coordinate, so two families must never collide in
#: that space; this value collides with no family shipped today.
CHANGE_EFFECT_POLICY_FAMILY: Final[str] = "change_effect.classification_policy"

#: The ``policy_type`` framed into the body digest alongside the adapter id. A constant,
#: so a class rename is a deliberate digest-moving act rather than a silent one.
CHANGE_EFFECT_POLICY_TYPE: Final[str] = "ChangeEffectClassificationPolicy"

#: The family a ClosureBundleMapping coordinate must name. **This package defines no
#: mapping artifact and ships no mapping content.** The constant exists so a coordinate
#: pointing at some other family is refused rather than silently carried: a reference to
#: the wrong thing is not better than a reference to nothing.
MAPPING_POLICY_FAMILY: Final[str] = "change_effect.closure_bundle_mapping"

#: The seven protected registries, by identifier. The list is *which registries are
#: protected*; it states no effect class, no route and no outcome, because what a change
#: to one of them means is measured by a classifier that does not exist, under rules this
#: artifact does not carry.
PROTECTED_REGISTRY_IDS: Final[tuple[str, ...]] = (
    "subject_classes",
    "governance_roles",
    "observables",
    "context_predicates",
    "constraint_inputs",
    "identity_links",
    "obligated_actions",
)

POLICY_SCOPE_GLOBAL: Final[str] = "GLOBAL"
POLICY_SCOPE_TENANT: Final[str] = "TENANT"
ADMITTED_POLICY_SCOPES: Final[frozenset[str]] = frozenset(
    {POLICY_SCOPE_GLOBAL, POLICY_SCOPE_TENANT}
)

LIFECYCLE_DRAFT: Final[str] = "DRAFT"
LIFECYCLE_APPROVED_ACTIVE: Final[str] = "APPROVED_ACTIVE"
LIFECYCLE_SUPERSEDED: Final[str] = "SUPERSEDED"
LIFECYCLE_WITHDRAWN: Final[str] = "WITHDRAWN"
ADMITTED_LIFECYCLE_STATES: Final[frozenset[str]] = frozenset(
    {LIFECYCLE_DRAFT, LIFECYCLE_APPROVED_ACTIVE, LIFECYCLE_SUPERSEDED, LIFECYCLE_WITHDRAWN}
)

#: The one lifecycle state that is operative. Ruling 6: an artifact without a valid
#: mapping coordinate may not enter it.
ACTIVE_LIFECYCLE_STATE: Final[str] = LIFECYCLE_APPROVED_ACTIVE
