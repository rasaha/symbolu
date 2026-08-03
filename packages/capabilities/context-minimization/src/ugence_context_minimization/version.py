"""Single source of truth for package + contract versions."""

from __future__ import annotations

#: Distribution version (SemVer). Bump on any public-surface change.
__version__ = "0.1.1"

#: The minimization contract version. Governs the shape/meaning of
#: :class:`MinimizationResult`, the reason-code vocabulary, and the neutral oracle
#: protocol. Consumers can assert against this independently of the package version.
#:
#: 1.0.1 (v0.1.1): inclusive oracle expiry; mandatory evaluation_time when a validity
#: horizon is supplied; mandatory correlation binding (two specific reason codes);
#: requested_reduction preserved verbatim; new requested_token_budget field; two
#: fingerprints (outcome_fingerprint + run_fingerprint) with fingerprint retained as a
#: byte-identical deprecated alias of outcome_fingerprint. Additive + fail-closed
#: tightening; the outcome_fingerprint digest is unchanged from 1.0.0.
CONTRACT_VERSION = "1.0.1"
