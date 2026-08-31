"""Ugence Cloud Scaling Policy Authenticity — Phase 5B-0B.

**A verified policy proof grants nothing.** It establishes that one exact policy version was
authentically issued and is valid at an injected instant, and stops. It is not an
authorization, not an envelope, not an ActionGate admission, not a credential and not
permission to execute anything.

What this package closes
------------------------
Phase 5A carries a ``PolicyTargetBindingReference`` and says plainly that it never asks the
Policy Authority anything: its one trust state is ``PRESENT_BUT_NOT_TRUST_VERIFIED``. Phase
5B-0A closed the neighbouring hole — *did this recommendation come from a trusted producer?*
This package closes *did these policy limits come from the authoritative policy system,
unchanged and valid for this tenant at this instant?*

* :class:`PolicyAuthenticityVerifier` — the authoritative routine. It resolves one exact
  coordinate through the Policy Authority's own trusted-resolution path and then applies four
  gates the authority does not apply for a consumer: a historical answer is refused, a port
  that answered another question is refused, a record whose coordinate does not name its own
  signed body is refused, and an algorithm outside the closed set is refused.
* :class:`PolicyAuthorityResolutionPort` — the one production-grade seam to the authority.
  It pins the fail-closed historical rule, reports the identity of the trust configuration it
  resolves under, and declines the production opt-in while standing on the authority's
  explicitly reference-grade in-memory registry.
* :class:`VerifiedPolicyAuthenticity` — the exact-typed, immutable, non-authoritative result,
  constructible only by that routine and revalidated at every consumption boundary.

The four rulings this implementation is built on
-------------------------------------------------
* **D-5B0B-1** — the verified artifact is a ``PolicyResolution`` that is ``RESOLVED`` *and*
  non-historical. A historical resolution can never back an authorization.
* **D-5B0B-2** — ``policy_body_digest`` is the content binding, not ``content_digest``. Phase
  5A's ``policy_artifact_digest`` corresponds to neither and cannot hold a Policy Authority
  digest at all: the two digest namespaces are kept apart and never converted.
* **D-5B0B-4, ratified as option (a)** — policy signatures are verified through the Policy
  Authority's own ``PolicyKeyRing``, not through a Trusted Evidence Authority trust anchor.
  ``TrustAnchorRecord`` carries no tenant field by ratified refusal, while
  ``PolicyVerificationKey`` carries one and enforces it; and TEV's capability is single-valued
  per anchor while the Policy Authority splits ``ISSUE_POLICY`` from ``REVOKE_POLICY`` on one
  key. This package therefore imports the Policy Authority and does **not** import TEV.
* **D-5B0B-6** — the proof travels **alongside** the candidate. Phase 5A stays at ``0.1.0``,
  unmodified, with all ten frozen digests unmoved. **Superseded by 5B-1**: the policy
  coordinate now travels *inside* the candidate, Phase 5A is at ``0.2.0``, and one of
  its (now eleven) frozen digests moved.

What it deliberately does not do
--------------------------------
It does not bind the verified policy to a recommendation, an execution target scope or a
candidate — ADR residual R-4, 5B-1's decision-scope repair. A candidate may be supplied and
its digest is recorded as the scope of the determination, but it is **never reconciled**: a
Phase 5A binding carries three of the coordinate's six components and cannot name a
coordinate. It does not extract bounds from the policy body into a candidate. It does not
authorize a caller, mint an envelope, sign anything, hold a key, read a clock or persist
policy.

**The instant is unvalidated.** ADR residual **R-2** — whose clock supplies ``as_of``, and
what makes it trustworthy — is open, and this implementation proceeds with ``as_of`` injected
and unvalidated by explicit owner authorization. Five gates in the resolution depend on it, so
a determination reached at an attacker-chosen instant can resolve a policy that is revoked,
expired or not yet effective now. Binding ``as_of`` to a trusted time source is 5B-2's work.

A verified producer attestation and a verified policy proof are **two verified facts, not a
permission**.
"""

from __future__ import annotations

from .canonical import (
    CANONICALIZATION_VERSION,
    canonical_bytes,
    framed_digest,
    is_phase5a_digest,
    is_policy_digest,
    require_phase5a_digest,
    require_policy_digest,
)
from .errors import (
    CloudScalingPolicyAuthenticityError,
    PolicyAuthenticityConfigurationError,
    PolicyAuthenticityContractError,
    PolicyAuthenticityExactTypeError,
    PolicyAuthenticityFieldError,
    VerifiedPolicyArtifactIntegrityError,
)
from .identifiers import (
    FORBIDDEN_KEY_ENTITLEMENT,
    PHASE_5A_BINDING_SCHEMA_VERSION,
    POLICY_AUTHENTICITY_DIGEST_DOMAIN,
    POLICY_AUTHENTICITY_RECORDED_FACTS_DOMAIN,
    POLICY_AUTHENTICITY_VERIFIED_FACTS_DOMAIN,
    POLICY_AUTHORITY_CANONICALIZATION_VERSION,
    POLICY_AUTHORITY_PROTOCOL_ID,
    POLICY_TRUST_ANCHOR_OWNER,
    POLICY_TRUST_CONFIGURATION_DIGEST_DOMAIN,
    REQUIRED_HISTORICAL_RESOLUTION_RULE,
    REQUIRED_KEY_ENTITLEMENT,
    SUPPORTED_SIGNATURE_ALGORITHMS,
    VERIFICATION_PROFILE,
    VERIFICATION_PROFILE_VERSION,
)
from .outcomes import (
    REFUSAL_OUTCOMES,
    RESOLUTION_REASON_OUTCOMES,
    TEMPORAL_OUTCOMES,
    PolicyAuthenticityOutcome,
    resolution_reason_outcome,
)
from .resolution_port import (
    REFERENCE_GRADE_PORTS,
    REFERENCE_GRADE_REGISTRIES,
    DenyAllPolicyResolutionPort,
    PolicyAuthorityResolutionPort,
    PolicyResolutionPort,
    policy_trust_configuration_digest,
    require_production_resolution_port,
)
from .verification import (
    PolicyAuthenticityRefusal,
    PolicyAuthenticityResult,
    PolicyAuthenticityVerifier,
)
from .verified import (
    RECORDED_FACT_NAMES,
    VERIFIED_FACT_NAMES,
    VerifiedCapacityBound,
    VerifiedPolicyAuthenticity,
    require_verified_policy_authenticity,
)
from .version import __version__

__all__ = [
    "__version__",
    # --- the authoritative verification routine ---
    "PolicyAuthenticityVerifier",
    "PolicyAuthenticityResult",
    "PolicyAuthenticityRefusal",
    "VERIFICATION_PROFILE",
    "VERIFICATION_PROFILE_VERSION",
    # --- the resolution seam (Policy Authority's own path; no second trust store) ---
    "PolicyResolutionPort",
    "PolicyAuthorityResolutionPort",
    "DenyAllPolicyResolutionPort",
    "policy_trust_configuration_digest",
    "require_production_resolution_port",
    "REFERENCE_GRADE_PORTS",
    "REFERENCE_GRADE_REGISTRIES",
    # --- the verified artifact (non-authoritative; revalidated at consumption) ---
    "VerifiedCapacityBound",
    "VerifiedPolicyAuthenticity",
    "require_verified_policy_authenticity",
    # --- the ratified verified/recorded partition (D-5B0B-7) ---
    "VERIFIED_FACT_NAMES",
    "RECORDED_FACT_NAMES",
    "POLICY_AUTHENTICITY_VERIFIED_FACTS_DOMAIN",
    "POLICY_AUTHENTICITY_RECORDED_FACTS_DOMAIN",
    # --- typed outcomes ---
    "PolicyAuthenticityOutcome",
    "REFUSAL_OUTCOMES",
    "RESOLUTION_REASON_OUTCOMES",
    "TEMPORAL_OUTCOMES",
    "resolution_reason_outcome",
    # --- identifiers and the ratified trust-anchor ownership ---
    "POLICY_TRUST_ANCHOR_OWNER",
    "REQUIRED_KEY_ENTITLEMENT",
    "FORBIDDEN_KEY_ENTITLEMENT",
    "REQUIRED_HISTORICAL_RESOLUTION_RULE",
    "SUPPORTED_SIGNATURE_ALGORITHMS",
    "POLICY_AUTHENTICITY_DIGEST_DOMAIN",
    "POLICY_TRUST_CONFIGURATION_DIGEST_DOMAIN",
    "POLICY_AUTHORITY_PROTOCOL_ID",
    "POLICY_AUTHORITY_CANONICALIZATION_VERSION",
    "PHASE_5A_BINDING_SCHEMA_VERSION",
    # --- canonicalization: the Policy Authority's scheme, two namespaces kept apart ---
    "canonical_bytes",
    "framed_digest",
    "is_policy_digest",
    "require_policy_digest",
    "is_phase5a_digest",
    "require_phase5a_digest",
    "CANONICALIZATION_VERSION",
    # --- typed errors ---
    "CloudScalingPolicyAuthenticityError",
    "PolicyAuthenticityContractError",
    "PolicyAuthenticityExactTypeError",
    "PolicyAuthenticityFieldError",
    "VerifiedPolicyArtifactIntegrityError",
    "PolicyAuthenticityConfigurationError",
]
