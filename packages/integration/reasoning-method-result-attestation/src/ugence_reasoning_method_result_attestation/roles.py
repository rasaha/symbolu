"""The one attester role of this slice (SCR-1), and the trust-anchor capability it resolves under.

``COMPARISON_ENGINE`` is the party that ran the comparison and signs the result
it produced. The role is a signed field, it selects the capability in the anchor
coordinate, and an anchor filed under any other capability is at a different
coordinate, so it can never satisfy it. The role is not the Trusted Evidence
Authority's evidence-production, receipt-issuance, Cloud Scaling, effect or
set-publication capability, and is not derived from them: seven disjoint
entitlements in one store.

An independent-verifier role — a second signature by a party that re-ran the
comparison — is deliberately **not** scoped here (ADR §3); it is a later slice
with its own role and its own lent capability.

What the role establishes is bounded and stated here once, so every result
carries the sentence rather than leaving it to a reader's inference.
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Final, Mapping

from ugence_trusted_evidence_authority import TrustAnchorCapability

from .canonical import require_exact_type
from .errors import ComparisonResultAttestationContractError as _Error

__all__ = [
    "ComparisonResultAttesterRole",
    "COMPARISON_RESULT_ATTESTER_ROLE_CAPABILITY",
    "COMPARISON_RESULT_ATTESTER_ROLE_ESTABLISHES",
    "capability_for_role",
    "require_role",
]


class ComparisonResultAttesterRole(str, Enum):
    """Who is signing. Exactly one member in this slice, exactly compared."""

    #: The engine that produced the comparison result and signs it under its
    #: own identity. A verified signature under this role proves **which engine
    #: produced this result under which key**. It does not prove that the
    #: comparison is correct, that its inputs were genuine, or that any method
    #: is fit for any task.
    COMPARISON_ENGINE = "COMPARISON_ENGINE"


#: Role -> the capability a signer's anchor must be filed under. The mapping is
#: total, injective, and touches no capability outside the one lent here.
COMPARISON_RESULT_ATTESTER_ROLE_CAPABILITY: Final[
    Mapping[ComparisonResultAttesterRole, TrustAnchorCapability]
] = MappingProxyType(
    {
        ComparisonResultAttesterRole.COMPARISON_ENGINE: (
            TrustAnchorCapability.COMPARISON_RESULT_ATTESTATION
        ),
    }
)

#: What a VERIFIED result under the role establishes — and does not.
COMPARISON_RESULT_ATTESTER_ROLE_ESTABLISHES: Final[
    Mapping[ComparisonResultAttesterRole, str]
] = MappingProxyType(
    {
        ComparisonResultAttesterRole.COMPARISON_ENGINE: (
            "which engine produced this comparison result under which key; not that "
            "the comparison is correct, and not that any method is fit for any task"
        ),
    }
)

#: The capabilities this package must never resolve under. Stated as a tuple so
#: the import-time assertion and ``capability_for_role`` read the same list.
_FOREIGN_CAPABILITIES: Final[tuple] = (
    TrustAnchorCapability.EVIDENCE_PRODUCTION,
    TrustAnchorCapability.RECEIPT_ISSUANCE,
    TrustAnchorCapability.CLOUD_SCALING_RECOMMENDATION_ATTESTATION,
    TrustAnchorCapability.EFFECT_ATTESTATION_EXECUTING_PROVIDER,
    TrustAnchorCapability.EFFECT_ATTESTATION_INDEPENDENT_OBSERVER,
    TrustAnchorCapability.TRUST_ANCHOR_SET_PUBLICATION,
)


def require_role(name: str, value: object) -> ComparisonResultAttesterRole:
    """Exactly a member of :class:`ComparisonResultAttesterRole`; a bare string
    that spells one is not one."""

    return require_exact_type(name, value, ComparisonResultAttesterRole)


def capability_for_role(role: ComparisonResultAttesterRole) -> TrustAnchorCapability:
    """The one capability this role resolves under. Never a caller parameter."""

    require_role("role", role)
    capability = COMPARISON_RESULT_ATTESTER_ROLE_CAPABILITY[role]
    if capability in _FOREIGN_CAPABILITIES:  # pragma: no cover - unreachable while the mapping stands
        raise _Error("a comparison-result role may never resolve under a foreign capability")
    return capability


# Import-time separations, failing closed.
assert len(set(COMPARISON_RESULT_ATTESTER_ROLE_CAPABILITY.values())) == len(ComparisonResultAttesterRole) == 1
assert set(COMPARISON_RESULT_ATTESTER_ROLE_CAPABILITY) == set(ComparisonResultAttesterRole)
assert set(COMPARISON_RESULT_ATTESTER_ROLE_CAPABILITY.values()).isdisjoint(set(_FOREIGN_CAPABILITIES))
assert len(set(_FOREIGN_CAPABILITIES)) + 1 == len(TrustAnchorCapability)
