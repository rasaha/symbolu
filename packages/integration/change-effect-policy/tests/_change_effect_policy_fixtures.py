"""Builders for a well-formed artifact, so each test varies one thing.

Every digest here is a *caller input* — that is the package's posture, not a shortcut:
nothing in the package computes a content digest, so a test that let the package supply
one would be testing a capability that deliberately does not exist. Values are arbitrary
but real-shaped: 64 lowercase hex characters, not a repeated character and not a
sentinel word, because both of those are refused.
"""

from __future__ import annotations

import hashlib

from ugence_policy_authority.api import PolicyCoordinate

from ugence_change_effect_policy import (
    ChangeEffectClassificationPolicy,
    ChangeEffectPolicyMetadata,
    LIFECYCLE_APPROVED_ACTIVE,
    LIFECYCLE_DRAFT,
    MAPPING_POLICY_FAMILY,
    POLICY_SCOPE_GLOBAL,
    PROTECTED_REGISTRY_IDS,
    ProtectedRegistryEntry,
)


def digest_of(label: str) -> str:
    """A real-shaped digest derived from a label, so fixtures stay readable."""

    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def registries() -> tuple[ProtectedRegistryEntry, ...]:
    """All seven, each with prose. A partial list is refused."""

    return tuple(
        ProtectedRegistryEntry(
            registry_id=registry_id,
            admission_rule=f"a member of {registry_id} is admitted by the governance "
            f"process that owns {registry_id}",
        )
        for registry_id in PROTECTED_REGISTRY_IDS
    )


def metadata(**overrides) -> ChangeEffectPolicyMetadata:
    fields = {
        "policy_id": "change-effect.classification.baseline",
        "version": "1.0.0",
        "content_digest": digest_of("baseline-content"),
        "scope": POLICY_SCOPE_GLOBAL,
        "lifecycle_state": LIFECYCLE_DRAFT,
    }
    fields.update(overrides)
    return ChangeEffectPolicyMetadata(**fields)


def mapping_coordinate(**overrides) -> PolicyCoordinate:
    fields = {
        "policy_family": MAPPING_POLICY_FAMILY,
        "policy_id": "change-effect.closure-bundle-mapping.baseline",
        "version": "1.0.0",
        "content_digest": digest_of("mapping-content"),
        "scope": POLICY_SCOPE_GLOBAL,
        "tenant_id": "",
    }
    fields.update(overrides)
    return PolicyCoordinate(**fields)


def policy(**overrides) -> ChangeEffectClassificationPolicy:
    """The initial shipped shape: non-operative, empty table, no coordinate."""

    fields = {
        "metadata": metadata(),
        "constitution_ref": "ugence.constitution/v1#change-effect",
        "intent_specification_refs": ("ugence.intent.recalibration/v1",),
        "protected_registries": registries(),
    }
    fields.update(overrides)
    return ChangeEffectClassificationPolicy(**fields)


def operative_policy(**overrides) -> ChangeEffectClassificationPolicy:
    """An artifact that *could* be operative: active state and a real coordinate.

    "Could be" is the whole claim. Nothing resolves it, so it grants nothing.
    """

    fields = {
        "metadata": metadata(lifecycle_state=LIFECYCLE_APPROVED_ACTIVE),
        "mapping_coordinate": mapping_coordinate(),
    }
    fields.update(overrides)
    return policy(**fields)
