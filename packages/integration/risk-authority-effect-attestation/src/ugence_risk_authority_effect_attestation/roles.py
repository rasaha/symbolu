"""The two attester roles (SE-2), and the trust-anchor capability each resolves under (SE-4).

Both roles may attest an external effect. They are **not interchangeable**: the
role is a signed field, it selects the capability in the anchor coordinate, and
an anchor authorized for one role is at a different coordinate from the other,
so it can never satisfy it. Neither role is the Trusted Evidence Authority's
evidence-production, receipt-issuance or Cloud Scaling capability, and neither
is derived from them: five disjoint entitlements in one store.

What each role establishes is bounded and stated here once, so every result
carries the sentence rather than leaving it to a reader's inference.
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Final, Mapping

from ugence_trusted_evidence_authority import TrustAnchorCapability

from .canonical import require_exact_type
from .errors import EffectAttestationContractError as _Error

__all__ = [
    "EffectAttesterRole",
    "EFFECT_ATTESTER_ROLE_CAPABILITY",
    "EFFECT_ATTESTER_ROLE_ESTABLISHES",
    "capability_for_role",
    "require_role",
]


class EffectAttesterRole(str, Enum):
    """Who is attesting. Exactly two members, exactly compared."""

    #: The party that executed the authorized action and reports the effect it
    #: observed. A verified signature under this role proves **which provider
    #: reported** the effect. It does not independently prove that the effect
    #: occurred, and it is not independent effect verification.
    EXECUTING_PROVIDER = "EXECUTING_PROVIDER"
    #: A party other than the executing provider that observed the effect. A
    #: verified signature under this role proves the **identity and authorized
    #: role of the observer**, not the truth of its observation.
    INDEPENDENT_OBSERVER = "INDEPENDENT_OBSERVER"


#: Role -> the capability an attester's anchor must be filed under. The mapping
#: is total, injective, and touches no capability outside the two lent ones.
EFFECT_ATTESTER_ROLE_CAPABILITY: Final[Mapping[EffectAttesterRole, TrustAnchorCapability]] = (
    MappingProxyType(
        {
            EffectAttesterRole.EXECUTING_PROVIDER: (
                TrustAnchorCapability.EFFECT_ATTESTATION_EXECUTING_PROVIDER
            ),
            EffectAttesterRole.INDEPENDENT_OBSERVER: (
                TrustAnchorCapability.EFFECT_ATTESTATION_INDEPENDENT_OBSERVER
            ),
        }
    )
)

#: What a VERIFIED result under each role establishes — and does not.
EFFECT_ATTESTER_ROLE_ESTABLISHES: Final[Mapping[EffectAttesterRole, str]] = MappingProxyType(
    {
        EffectAttesterRole.EXECUTING_PROVIDER: (
            "which executing provider reported this effect; not that the effect "
            "occurred, and not independent verification of it"
        ),
        EffectAttesterRole.INDEPENDENT_OBSERVER: (
            "the identity and authorized observer role of the party that signed; "
            "not the truth of its observation"
        ),
    }
)


def require_role(name: str, value: object) -> EffectAttesterRole:
    """Exactly a member of :class:`EffectAttesterRole`; a bare string that spells
    one is not one."""

    return require_exact_type(name, value, EffectAttesterRole)


def capability_for_role(role: EffectAttesterRole) -> TrustAnchorCapability:
    """The one capability this role resolves under. Never a caller parameter."""

    require_role("role", role)
    capability = EFFECT_ATTESTER_ROLE_CAPABILITY[role]
    if capability in (
        TrustAnchorCapability.EVIDENCE_PRODUCTION,
        TrustAnchorCapability.RECEIPT_ISSUANCE,
        TrustAnchorCapability.CLOUD_SCALING_RECOMMENDATION_ATTESTATION,
    ):  # pragma: no cover - unreachable while the mapping above stands
        raise _Error("an effect-attester role may never resolve under a foreign capability")
    return capability


# Import-time separations, failing closed.
assert len(set(EFFECT_ATTESTER_ROLE_CAPABILITY.values())) == len(EffectAttesterRole) == 2
assert set(EFFECT_ATTESTER_ROLE_CAPABILITY) == set(EffectAttesterRole)
assert set(EFFECT_ATTESTER_ROLE_CAPABILITY.values()).isdisjoint(
    {
        TrustAnchorCapability.EVIDENCE_PRODUCTION,
        TrustAnchorCapability.RECEIPT_ISSUANCE,
        TrustAnchorCapability.CLOUD_SCALING_RECOMMENDATION_ATTESTATION,
    }
)
