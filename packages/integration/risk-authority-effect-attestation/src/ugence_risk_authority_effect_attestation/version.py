"""Single source of truth for the distribution version.

``0.1.0`` is the contracts-first slice ratified by
``docs/architecture/ADR_UGENCE_SIGNED_EFFECT_ATTESTATION_SCOPING.md`` (SE-1 to
SE-5): the effect-attestation wrapper, the two attester roles, the verification
port and its typed result, one verifier over the Trusted Evidence Authority's
anchors, and a reference signer for tests. Maturity is REFERENCE-GRADE / NOT
PRODUCTION-READY, and nothing here is wired into RA-8.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.2.0"
