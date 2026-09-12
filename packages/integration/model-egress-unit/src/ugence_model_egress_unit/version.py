"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package (and thus its dependencies).
"""

from __future__ import annotations

__version__ = "0.4.1"

#: Frozen identity of the exchange contract this package reads and writes.
CONTRACT_VERSION = "model_egress_unit.exchange.v1"

#: Maturity, stated once and machine-readable.
#:
#: **This package cannot call a model vendor.** It carries no HTTP client, no SDK,
#: no credential reader and no destination configuration, and the only provider it
#: ships computes its answer from a hash. The exchange, the roles, the row-level
#: security and the reconciliation are real and tested against PostgreSQL; the
#: egress is not present at all. That is the whole posture: the boundary is built
#: so that a live provider, if one is ever ratified, has somewhere to land.
MATURITY = "REFERENCE_GRADE_SHADOW_ONLY"

#: This package never enforces. It records what was asked, what came back, and
#: what could not be determined. Authority over whether a request may be made at
#: all belongs upstream, and is deliberately not wired here — see the ADR.
ENFORCEMENT_ENABLED = False

#: The commissioning record's status, as a release constant (LP-4). Pinned by a test to
#: ``MEU_LIVE_VALIDATION.json`` (``meu_live_status``). ``MET`` is the *outcome* of the
#: validation and is reached only by the owner's separate acceptance statement; it is
#: never a prerequisite of the validation call itself (ADR §0.5).
COMMISSIONING_STATUS = "BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS"

#: The owner's separate, explicit authorization for the first live synthetic validation
#: call (LP-7 ruling 12), as a release constant mirroring
#: ``MEU_LIVE_VALIDATION.json`` (``live_synthetic_validation_authorization``).
#: ``NOT_GIVEN`` until the owner's authorization record is released into this constant
#: by its identifier; no configuration and no adapter can supply it.
LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION = "NOT_GIVEN"

#: The two statuses under which a genuine call may be recorded: ``PENDING_VALIDATION``
#: (every step-8 obligation independently verified; the validation call is what happens
#: here) and ``MET`` (the outcome). Never ``BLOCKED_*`` and never ``NOT_MET``.
GENUINE_CALL_ADMITTING_STATUSES = ("PENDING_VALIDATION", "MET")


def genuine_call_admitted() -> bool:
    """The application gate for ``genuine_call: true`` (ADR §0.5): both predecessor gates
    hold — the status admits a genuine call and the live synthetic validation is
    authorized. Reads the release constants at call time so a test can prove each gate
    alone is insufficient. Row 12 of the validation matrix requires exactly this, plus a
    production-authoritative custody lease, ``UNTRUSTED_EVIDENCE`` trust and the row-18
    correlation; it never requires ``MET``."""

    return (COMMISSIONING_STATUS in GENUINE_CALL_ADMITTING_STATUSES
            and LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION != "NOT_GIVEN")

#: No live vendor egress exists in this distribution, and none is configurable.
#: Asserted structurally by ``tests/test_boundaries.py`` over the whole source
#: tree rather than declared here and trusted.
LIVE_VENDOR_EGRESS = False
