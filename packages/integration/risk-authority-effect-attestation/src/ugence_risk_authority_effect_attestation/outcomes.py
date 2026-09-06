"""The closed outcome and refusal vocabularies of effect-attestation verification.

Two outcomes and no third: a success-shaped ``UNKNOWN``, ``PARTIAL`` or
``PENDING`` member would be read optimistically by exactly the consumer this
vocabulary is written to protect. Every refusal names one stable typed reason,
in the order the verifier checks them, so identical inputs yield the identical
reason.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["EffectAttestationVerificationOutcome", "EffectAttestationRefusalReason"]


class EffectAttestationVerificationOutcome(str, Enum):
    #: The signature verified under a currently usable anchor at the exact
    #: coordinate the attestation names, over the bytes recomputed from the
    #: caller's own observation. **Provenance and integrity only.**
    VERIFIED = "VERIFIED"
    #: Fail-closed, with exactly one typed reason.
    REFUSED = "REFUSED"


class EffectAttestationRefusalReason(str, Enum):
    # --- 1. admission of the inputs themselves ---------------------------------
    ATTESTATION_ABSENT = "ATTESTATION_ABSENT"
    UNSUPPORTED_EXACT_TYPE = "UNSUPPORTED_EXACT_TYPE"
    # --- 2. contract admission (schema, domain, algorithm, profile, encoding) ---
    UNSUPPORTED_SCHEMA_VERSION = "UNSUPPORTED_SCHEMA_VERSION"
    UNSUPPORTED_SIGNING_DOMAIN = "UNSUPPORTED_SIGNING_DOMAIN"
    UNSUPPORTED_ALGORITHM = "UNSUPPORTED_ALGORITHM"
    UNSUPPORTED_PROFILE = "UNSUPPORTED_PROFILE"
    UNSUPPORTED_ENCODING = "UNSUPPORTED_ENCODING"
    # --- 3. reconciliation against the caller's own facts ----------------------
    ROLE_MISMATCH = "ROLE_MISMATCH"
    WRONG_TENANT = "WRONG_TENANT"
    OBSERVATION_MISMATCH = "OBSERVATION_MISMATCH"
    # --- 4. anchor resolution at the exact coordinate --------------------------
    ANCHOR_UNKNOWN = "ANCHOR_UNKNOWN"
    ANCHOR_UNAVAILABLE = "ANCHOR_UNAVAILABLE"
    ANCHOR_COORDINATE_MISMATCH = "ANCHOR_COORDINATE_MISMATCH"
    WRONG_CAPABILITY = "WRONG_CAPABILITY"
    # --- 5. anchor lifecycle at the trusted instant, in TEA's order -------------
    ANCHOR_REVOKED = "ANCHOR_REVOKED"
    ANCHOR_DISABLED = "ANCHOR_DISABLED"
    ANCHOR_NOT_YET_VALID = "ANCHOR_NOT_YET_VALID"
    ANCHOR_EXPIRED = "ANCHOR_EXPIRED"
    ANCHOR_REVISION_MISMATCH = "ANCHOR_REVISION_MISMATCH"
    # --- 6. key admission and the signature itself -----------------------------
    KEY_MATERIAL_INVALID = "KEY_MATERIAL_INVALID"
    PAYLOAD_MISMATCH = "PAYLOAD_MISMATCH"
    MALFORMED_SIGNATURE = "MALFORMED_SIGNATURE"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    # --- 7. the fail-closed terminal ------------------------------------------
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"
