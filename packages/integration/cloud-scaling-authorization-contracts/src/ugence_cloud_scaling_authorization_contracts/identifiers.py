"""The D-4 ratified identifiers, re-anchored — never re-minted — for Phase 5A.

Phase 4C ratified the Cloud Scaling risk-boundary vocabulary. Phase 5A **reuses those
exact values** and owns them as module constants. Three properties matter:

* **No caller controls them.** They are not constructor fields on any Phase 5A artifact.
  A caller cannot present a candidate for ``cloud_scaling.capacity_action`` while
  actually binding some other purpose, because there is no parameter to divert.
* **No synonyms, no translation table.** Phase 5A introduces no ``capacity.authorize``
  alias and no Phase-5 spelling of a Phase-4 value. A translation table is precisely
  where an action substitution would eventually hide, so there is none.
* **Drift fails closed at import.** The values are asserted against the Phase 4C
  originals *and* against the controller's canonical ``ActionKind`` set when this module
  is imported. A rename upstream stops this package from importing at all, rather than
  letting it silently bind an unratified identifier into a candidate digest.

The action-type set is the controller's own ``ActionKind`` value set, reached through
Phase 4C's ``CANONICAL_ACTION_TYPES``. Phase 5A adds nothing to it.
"""

from __future__ import annotations

from typing import Final

from ugence_cloud_scaling_controller.planning.candidates import ActionKind
from ugence_cloud_scaling_risk_integration import (
    CANONICAL_ACTION_TYPES as _PHASE4C_ACTION_TYPES,
)
from ugence_cloud_scaling_risk_integration import (
    DOMAIN_CLOUD_SCALING as _PHASE4C_DOMAIN,
)
from ugence_cloud_scaling_risk_integration import (
    PURPOSE_CAPACITY_ACTION as _PHASE4C_PURPOSE,
)
from ugence_cloud_scaling_risk_integration import (
    SUBJECT_TYPE_CAPACITY_SUBJECT as _PHASE4C_SUBJECT_TYPE,
)

__all__ = [
    "PURPOSE_CAPACITY_ACTION",
    "DOMAIN_CLOUD_SCALING",
    "SUBJECT_TYPE_CAPACITY_SUBJECT",
    "CANONICAL_ACTION_TYPES",
    "CANONICAL_CLOUD_PROVIDERS",
    "CLOUD_PROVIDER_AZURE",
    "PRODUCER_SIGNING_PURPOSE",
    "SUPPORTED_PRODUCER_SIGNING_PURPOSES",
]

#: ``requested_purpose`` — identical to the D-4 ratified Phase 4C value.
PURPOSE_CAPACITY_ACTION: Final[str] = "cloud_scaling.capacity_action"

#: ``requested_domain`` — identical to the D-4 ratified Phase 4C value.
DOMAIN_CLOUD_SCALING: Final[str] = "cloud_scaling"

#: ``subject_type`` — identical to the D-4 ratified Phase 4C value.
SUBJECT_TYPE_CAPACITY_SUBJECT: Final[str] = "cloud_scaling.capacity_subject"

#: The controller's exact canonical ``ActionKind`` values. No aliases, no translation.
CANONICAL_ACTION_TYPES: Final[frozenset[str]] = frozenset(
    {"no_change", "scale_up", "scale_down", "coordinated"}
)

#: The **dedicated producer-signing purpose**. Deliberately distinct from any Policy
#: Authority policy-signing purpose: a key entitled to sign a controller recommendation
#: must not thereby be entitled to sign policy, and vice versa. Phase 5A checks only that
#: an attestation names this purpose; Phase 5B decides whether the key was entitled to it.
PRODUCER_SIGNING_PURPOSE: Final[str] = "cloud_scaling.recommendation_producer_attestation"

#: The closed set of signing-purpose identifiers Phase 5A will admit structurally. An
#: attestation naming anything else — including a policy-signing purpose — is rejected.
SUPPORTED_PRODUCER_SIGNING_PURPOSES: Final[frozenset[str]] = frozenset(
    {PRODUCER_SIGNING_PURPOSE}
)


def _assert_no_drift() -> None:
    """Fail closed at import if any ratified identifier drifted from its Phase 4C origin.

    Kept as a function so the identical assertions can be re-run as a test at test time
    (ADR Phase 5 §9 requires both import-time and test-time drift assertions).
    """

    pairs = (
        ("PURPOSE_CAPACITY_ACTION", PURPOSE_CAPACITY_ACTION, _PHASE4C_PURPOSE),
        ("DOMAIN_CLOUD_SCALING", DOMAIN_CLOUD_SCALING, _PHASE4C_DOMAIN),
        (
            "SUBJECT_TYPE_CAPACITY_SUBJECT",
            SUBJECT_TYPE_CAPACITY_SUBJECT,
            _PHASE4C_SUBJECT_TYPE,
        ),
        ("CANONICAL_ACTION_TYPES", CANONICAL_ACTION_TYPES, _PHASE4C_ACTION_TYPES),
    )
    for name, ours, theirs in pairs:
        if ours != theirs:
            raise ImportError(
                f"D-4 identifier drift: Phase 5A {name}={ours!r} is not the ratified "
                f"Phase 4C value {theirs!r}; Phase 5A fails closed rather than binding "
                "an unratified identifier into a candidate digest"
            )
    controller_actions = frozenset(kind.value for kind in ActionKind)
    if controller_actions != CANONICAL_ACTION_TYPES:
        raise ImportError(
            "ActionKind drift: the controller's canonical action values "
            f"{sorted(controller_actions)} are not the D-4 ratified set "
            f"{sorted(CANONICAL_ACTION_TYPES)}; Phase 5A fails closed"
        )
    # The producer-signing purpose must never collide with the D-4 routing purpose: they
    # are different kinds of identifier and a collision would let one stand in for the
    # other in an audit record.
    if PRODUCER_SIGNING_PURPOSE == PURPOSE_CAPACITY_ACTION:
        raise ImportError(
            "the producer-signing purpose must not equal the D-4 routing purpose"
        )


_assert_no_drift()


#: The closed cloud-provider vocabulary, ratified ETS-3/ETS-10 (2026-09-01). Unlike
#: :data:`CANONICAL_ACTION_TYPES`, which Phase 5A re-exports from Phase 4C unchanged,
#: this vocabulary is **new to Phase 5A**: Phase 4's ``CapacitySubject`` is deliberately
#: provider-neutral and names no cloud, so there is nothing upstream to inherit.
#:
#: ``self-hosted`` is the repository's existing spelling (``ObservationProvenance``'s
#: provider label), admitted under ETS-10 so a Kubernetes target that belongs to no cloud
#: is buildable. Its presence means ``cloud_provider`` names a field whose value is
#: sometimes not a cloud; renaming it was not ratified and would be a second breaking
#: change, so the name stands.
#:
#: Membership is the whole of the check. ETS-11 ruled the pair
#: ``(cloud_provider, account_id)`` the governed account identity and explicitly kept
#: per-provider *grammar* out of this package: a 12-digit AWS account, a GCP project
#: number and an Azure subscription GUID are all validated here only as canonical
#: identifiers. Format knowledge belongs to governed adapters.
CANONICAL_CLOUD_PROVIDERS: Final[frozenset[str]] = frozenset(
    {"aws", "gcp", "azure", "self-hosted"}
)

#: Named rather than spelled inline: the Azure resource-group rule reads it twice, and a
#: bare string literal in a conditional is how a vocabulary quietly grows a synonym.
CLOUD_PROVIDER_AZURE: Final[str] = "azure"

