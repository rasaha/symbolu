"""The Phase 5B-0B identifiers, and the separations that keep them apart.

Who owns the policy trust anchor, and why it is not a parameter
---------------------------------------------------------------
D-5B0B-4 is ratified as **option (a)**: policy signatures are verified through the Policy
Authority's own :class:`~ugence_policy_authority.api.PolicyKeyRing`, never through a
Trusted Evidence Authority trust anchor. Two measured asymmetries decided it, and both are
executable here rather than merely documented:

* **Tenant.** ``PolicyVerificationKey`` carries ``tenant_id`` and ``PolicyKeyRing.verify``
  enforces it (``WRONG_TENANT``). TEV's ``TrustAnchorRecord`` carries no tenant field, by
  ratified refusal. An artifact whose whole subject is "valid **for this tenant**" cannot be
  verified under an anchor that cannot express a tenant.
* **Entitlement granularity.** ``KeyEntitlement`` separates ``ISSUE_POLICY`` from
  ``REVOKE_POLICY`` on one key, and the Policy Authority requires the latter to honour a
  revocation. TEV's ``TrustAnchorCapability`` is single-valued per anchor, so the same
  distinction would need two anchors.

The consequence for this package: the required entitlement is the constant
:data:`REQUIRED_KEY_ENTITLEMENT` and is **not** a parameter. There is nothing for a caller
to pass that would let a revoke-only key stand in for an issuing key, and
:data:`FORBIDDEN_KEY_ENTITLEMENT` is asserted distinct from it at import time.

**No second trust store is introduced.** This package holds no keys, no key ring and no
anchor records. It resolves nothing itself: it delegates to a
:class:`~.resolution_port.PolicyResolutionPort` the composition root wires, which is the
Policy Authority's own resolution path. Two trust systems now sit in one authorization
chain — TEV's, for producer attestations (5B-0A), and the Policy Authority's, for policy —
and that is correct separation, because they answer questions with different owners and
different rotation authority. What would be a defect is two systems for the *same*
question, which this is not.

Domain separation, and where it lives
-------------------------------------
This package produces no signature. The only bytes it originates are its own verification
artifact's integrity digest, and those are domain-separated by
:data:`POLICY_AUTHENTICITY_DIGEST_DOMAIN` bound as an ordinary canonical field, under the
Policy Authority's canonicalization version. A policy-body digest and a verification-artifact
digest therefore cannot collide, and neither can be read as the other.

Three inequalities are asserted **at import time**, failing closed:

#. the verification profile is not the Policy Authority's protocol identifier — this package
   is a consumer of that protocol, not a version of it;
#. the digest domain is not the Policy Authority's policy-body digest domain;
#. the required entitlement is not the revocation entitlement.

Two digest namespaces, never mixed
----------------------------------
D-5B0B-2 measured that Policy Authority digests are **bare lowercase 64-hex** while Phase 5A
requires **``sha256:`` + 64 hex**, and that a Policy Authority digest therefore cannot be
placed in Phase 5A's ``policy_artifact_digest`` field at all. This package carries values
from both namespaces and validates each by its own predicate — see :mod:`.canonical`. It
never converts between them, because a converted digest is a digest nobody signed.
"""

from __future__ import annotations

from typing import Final

from ugence_cloud_scaling_authorization_contracts import (
    POLICY_TARGET_BINDING_SCHEMA_VERSION as _PHASE_5A_BINDING_SCHEMA_VERSION,
)
from ugence_policy_authority.api import (
    AUTHORITY_PROTOCOL_ID,
    CANONICALIZATION_VERSION,
    POLICY_BODY_DIGEST_DOMAIN,
    SIGNATURE_ALG,
    HistoricalResolutionRule,
    KeyEntitlement,
)

__all__ = [
    "VERIFICATION_PROFILE",
    "VERIFICATION_PROFILE_VERSION",
    "POLICY_AUTHENTICITY_DIGEST_DOMAIN",
    "POLICY_AUTHENTICITY_VERIFIED_FACTS_DOMAIN",
    "POLICY_AUTHENTICITY_RECORDED_FACTS_DOMAIN",
    "POLICY_TRUST_CONFIGURATION_DIGEST_DOMAIN",
    "REQUIRED_KEY_ENTITLEMENT",
    "FORBIDDEN_KEY_ENTITLEMENT",
    "REQUIRED_HISTORICAL_RESOLUTION_RULE",
    "SUPPORTED_SIGNATURE_ALGORITHMS",
    "POLICY_TRUST_ANCHOR_OWNER",
    "PHASE_5A_BINDING_SCHEMA_VERSION",
    "POLICY_AUTHORITY_PROTOCOL_ID",
    "POLICY_AUTHORITY_CANONICALIZATION_VERSION",
]

#: The routine that reached a determination. Bound into every verified artifact and into
#: its digest, so an artifact produced by a future, different routine is not mistaken for
#: one produced by this one.
VERIFICATION_PROFILE: Final[str] = "ugence.cloud-scaling/policy-authenticity/v1"

#: The profile's own version. Bumped when a gate is added, removed or reordered.
VERIFICATION_PROFILE_VERSION: Final[str] = "v1"

#: Domain tag bound into this package's verification-artifact digest.
POLICY_AUTHENTICITY_DIGEST_DOMAIN: Final[str] = (
    "ugence.cloud-scaling/policy-authenticity/artifact/v1"
)

#: Domain tag of the **verified** half of a verification artifact's digest payload: the facts
#: a gate actually checked (D-5B0B-7).
POLICY_AUTHENTICITY_VERIFIED_FACTS_DOMAIN: Final[str] = (
    "ugence.cloud-scaling/policy-authenticity/artifact/verified/v1"
)

#: Domain tag of the **recorded** half: facts carried and digest-covered, but never attested.
#: Four members today, for three distinct reasons — ``resolved_as_of_fact`` (R-2: the instant
#: is injected and unvalidated), ``candidate_digest_fact`` (R-4: recorded, never reconciled),
#: ``policy_type`` (absent from the signed issuance payload and never compared at resolution)
#: and ``trust_configuration_digest`` (reported by the resolution port about itself). See
#: :data:`~.verified.RECORDED_FACT_NAMES`, which carries each reason in full.
POLICY_AUTHENTICITY_RECORDED_FACTS_DOMAIN: Final[str] = (
    "ugence.cloud-scaling/policy-authenticity/artifact/recorded/v1"
)

#: Domain tag bound into the trust-configuration digest a resolution port reports.
POLICY_TRUST_CONFIGURATION_DIGEST_DOMAIN: Final[str] = (
    "ugence.cloud-scaling/policy-authenticity/trust-configuration/v1"
)

#: The entitlement an issuing key must hold. A constant, never a parameter (see above).
REQUIRED_KEY_ENTITLEMENT: Final[KeyEntitlement] = KeyEntitlement.ISSUE_POLICY

#: The entitlement that must **not** stand in for it. Named so the distinction is
#: executable rather than implied by the absence of a parameter.
FORBIDDEN_KEY_ENTITLEMENT: Final[KeyEntitlement] = KeyEntitlement.REVOKE_POLICY

#: The historical-resolution rule a production port pins. ``DENY_ALWAYS`` is the Policy
#: Authority's own fail-closed default; this package does not offer the knob, and refuses a
#: historical answer at admission even if one somehow arrives (D-5B0B-1).
REQUIRED_HISTORICAL_RESOLUTION_RULE: Final[HistoricalResolutionRule] = (
    HistoricalResolutionRule.DENY_ALWAYS
)

#: The closed set of issuance signature algorithms this boundary admits. One member today.
SUPPORTED_SIGNATURE_ALGORITHMS: Final[frozenset] = frozenset({SIGNATURE_ALG})

#: The ratified owner of the policy trust anchor (D-5B0B-4, option (a)). A documentation
#: constant carried into the verified artifact's digest, so a deployment that later moved
#: policy trust elsewhere could not silently reuse artifacts minted under this ruling.
POLICY_TRUST_ANCHOR_OWNER: Final[str] = "ugence.policy-authority/policy-key-ring"

#: Phase 5A's frozen policy-binding schema tag, re-exported so a caller can name the
#: contract this package does **not** verify, widen or reinterpret.
PHASE_5A_BINDING_SCHEMA_VERSION: Final[str] = _PHASE_5A_BINDING_SCHEMA_VERSION

#: The Policy Authority protocol and canonicalization this package consumes. Carried into
#: the verified artifact so the determination names the rule set it was reached under.
POLICY_AUTHORITY_PROTOCOL_ID: Final[str] = AUTHORITY_PROTOCOL_ID
POLICY_AUTHORITY_CANONICALIZATION_VERSION: Final[str] = CANONICALIZATION_VERSION


# --- import-time separations, failing closed ------------------------------------------- #
if VERIFICATION_PROFILE == POLICY_AUTHORITY_PROTOCOL_ID:  # pragma: no cover - import guard
    raise AssertionError(
        "the Phase 5B-0B verification profile must not equal the Policy Authority protocol "
        "identifier: this package consumes that protocol and is not a version of it"
    )
if POLICY_AUTHENTICITY_DIGEST_DOMAIN == POLICY_BODY_DIGEST_DOMAIN:  # pragma: no cover
    raise AssertionError(
        "the verification-artifact digest domain must not equal the Policy Authority's "
        "policy-body digest domain: a verification artifact is not a policy body"
    )
if (  # pragma: no cover - import guard
    len(
        {
            POLICY_AUTHENTICITY_DIGEST_DOMAIN,
            POLICY_AUTHENTICITY_VERIFIED_FACTS_DOMAIN,
            POLICY_AUTHENTICITY_RECORDED_FACTS_DOMAIN,
        }
    )
    != 3
):
    raise AssertionError(
        "the artifact, verified-facts and recorded-facts domains must be three distinct "
        "tags: collapsing any two would let a recorded fact occupy an attested frame"
    )
if REQUIRED_KEY_ENTITLEMENT is FORBIDDEN_KEY_ENTITLEMENT:  # pragma: no cover - import guard
    raise AssertionError(
        "issuing and revoking entitlements must remain distinct; collapsing them would let "
        "a revoke-only key authenticate an issued policy"
    )
