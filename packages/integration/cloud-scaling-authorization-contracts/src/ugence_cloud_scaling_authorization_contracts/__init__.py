"""Ugence Cloud Scaling Authorization Contracts — Phase 5A.

**A candidate grants nothing.**

This package converts a reconciled Phase 4C projection and its Risk Authority binding
decision, together with producer-attestation evidence and a policy/target binding, into a
canonical, explicitly **non-authoritative** :class:`CapacityAuthorizationCandidate`.

What it does:

1. admits only **exact** Phase 4C and Risk Authority types;
2. **independently reconciles** the projection against the decision — every digest
   recomputed, never trusted, including ``decision_digest`` over ``decision_snapshot``;
3. structurally validates a **producer attestation** and binds it to the exact
   recommendation digest;
4. structurally validates a **policy/target binding** and an account-bound
   **execution target scope**, and enforces the magnitude and delta ceilings;
5. emits one canonical ``sha256:``-prefixed candidate digest over the whole chain.

What it does **not** do, and contains no capability to do:

* verify a producer signature, a policy signature, a key entitlement or an issuer;
* reconstruct, mint or re-request a ``RiskDecision``; call Decision Authority;
* construct, sign or issue a ``RiskAuthorizationEnvelope``; invoke ``EnvelopeIssuer``;
* invoke ActionGate or produce an ``ActionAuthorization``;
* issue, broker or handle a credential;
* import a cloud SDK or Kubernetes client, or call Cloud Scaling Operations;
* mutate infrastructure, or emit an execution or effect-verification receipt;
* read a clock, or decide that anything is currently valid or fresh;
* learn from an outcome.

Those exclusions are asserted structurally — over source imports, public exports, AST call
expressions, dependency metadata, the built wheel and the installed-wheel import closure —
not merely stated here.

**The two unverified states.** Both signature-bearing inputs report exactly
``PRESENT_BUT_NOT_TRUST_VERIFIED`` and there is no other state in the vocabulary. Phase 5A
binds signatures structurally and trust-verifies neither; Phase 5B performs independent
verification under a trusted clock before any envelope is issued. Live execution remains
structurally blocked until Phase 5X supplies short-lived, least-privilege credentials.
"""

from __future__ import annotations

from .attestation import (
    PRODUCER_ATTESTATION_SCHEMA_VERSION,
    SUPPORTED_SIGNATURE_ALGORITHMS,
    ProducerAttestationEvidence,
)
from .canonical import (
    DIGEST_PREFIX,
    canonical_digest,
    digest_of_snapshot,
    is_canonical_digest,
    is_policy_authority_digest,
)
from .candidate import (
    AUTHORIZATION_CANDIDATE_SCHEMA_VERSION,
    CapacityAuthorizationCandidate,
    build_capacity_authorization_candidate,
)
from .errors import (
    AuthorizationCandidateRejectionReason,
    CandidateConstructionError,
    CandidateDigestError,
    CanonicalFieldError,
    CloudScalingAuthorizationContractError,
    ExactTypeError,
    MagnitudeBoundError,
    PolicyTargetBindingError,
    ProducerAttestationError,
    ReconciliationError,
    TargetScopeError,
)
from .identifiers import (
    CANONICAL_ACTION_TYPES,
    DOMAIN_CLOUD_SCALING,
    PRODUCER_SIGNING_PURPOSE,
    PURPOSE_CAPACITY_ACTION,
    SUBJECT_TYPE_CAPACITY_SUBJECT,
    SUPPORTED_PRODUCER_SIGNING_PURPOSES,
)
from .reconciliation import (
    ALLOW_FAMILY_DISPOSITIONS,
    ReconciledPhase4Facts,
    reconcile_phase4,
)
from .target import (
    EXECUTION_TARGET_SCOPE_SCHEMA_VERSION,
    POLICY_COORDINATE_COMPONENTS,
    POLICY_SCOPE_TENANT,
    POLICY_TARGET_BINDING_SCHEMA_VERSION,
    POLICY_TARGET_BINDING_V2_SCHEMA_VERSION,
    ExecutionTargetScope,
    PolicyTargetBindingReference,
    PolicyTargetBindingReferenceV2,
)
from .trust import PHASE_5A_TRUST_STATE, EvidenceTrustState
from .version import __version__

__all__ = [
    "__version__",
    # --- production entry point ---
    "build_capacity_authorization_candidate",
    "CapacityAuthorizationCandidate",
    "AUTHORIZATION_CANDIDATE_SCHEMA_VERSION",
    # --- Phase 4 reconciliation ---
    "reconcile_phase4",
    "ReconciledPhase4Facts",
    "ALLOW_FAMILY_DISPOSITIONS",
    # --- producer attestation (structural only) ---
    "ProducerAttestationEvidence",
    "PRODUCER_ATTESTATION_SCHEMA_VERSION",
    "SUPPORTED_SIGNATURE_ALGORITHMS",
    # --- policy / execution target binding (structural only) ---
    "ExecutionTargetScope",
    "PolicyTargetBindingReference",
    "PolicyTargetBindingReferenceV2",
    "EXECUTION_TARGET_SCOPE_SCHEMA_VERSION",
    "POLICY_COORDINATE_COMPONENTS",
    "POLICY_SCOPE_TENANT",
    "POLICY_TARGET_BINDING_SCHEMA_VERSION",
    "POLICY_TARGET_BINDING_V2_SCHEMA_VERSION",
    # --- the single unverified trust state ---
    "EvidenceTrustState",
    "PHASE_5A_TRUST_STATE",
    # --- D-4 ratified identifiers (module-owned) ---
    "PURPOSE_CAPACITY_ACTION",
    "DOMAIN_CLOUD_SCALING",
    "SUBJECT_TYPE_CAPACITY_SUBJECT",
    "CANONICAL_ACTION_TYPES",
    "PRODUCER_SIGNING_PURPOSE",
    "SUPPORTED_PRODUCER_SIGNING_PURPOSES",
    # --- canonicalization (Risk Authority's scheme, public API only) ---
    "canonical_digest",
    "digest_of_snapshot",
    "is_canonical_digest",
    "is_policy_authority_digest",
    "DIGEST_PREFIX",
    # --- typed errors and rejection reasons ---
    "CloudScalingAuthorizationContractError",
    "CandidateConstructionError",
    "ExactTypeError",
    "CanonicalFieldError",
    "ReconciliationError",
    "ProducerAttestationError",
    "PolicyTargetBindingError",
    "TargetScopeError",
    "MagnitudeBoundError",
    "CandidateDigestError",
    "AuthorizationCandidateRejectionReason",
]
