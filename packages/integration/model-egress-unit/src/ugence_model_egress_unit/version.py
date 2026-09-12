"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package (and thus its dependencies).
"""

from __future__ import annotations

__version__ = "0.5.0"

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

#: A MIRROR, for drift detection only, of ``MEU_LIVE_VALIDATION.json`` →
#: ``live_synthetic_validation_authorization``: ``NOT_GIVEN`` or the digest of the owner's
#: typed ``LiveSyntheticValidationAuthorization`` record. It never constitutes execution
#: authority (ADR §0.6): the gate validates the typed record against the canonical
#: commissioning record and consumes it durably; an altered constant admits nothing.
LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION_DIGEST = "NOT_GIVEN"

#: The two statuses under which a genuine call may be recorded: ``PENDING_VALIDATION``
#: (every step-8 obligation independently verified; the validation call is what happens
#: here) and ``MET`` (the outcome). Never ``BLOCKED_*`` and never ``NOT_MET``.
GENUINE_CALL_ADMITTING_STATUSES = ("PENDING_VALIDATION", "MET")


def status_admits_genuine_call() -> bool:
    """G1's mirror: whether the release constant's status is one that admits a genuine
    call. Used only to fail closed on drift; G1 itself is read from the canonical
    commissioning record by :func:`ugence_model_egress_unit.authorization.admit_genuine_call`."""

    return COMMISSIONING_STATUS in GENUINE_CALL_ADMITTING_STATUSES


#: No live vendor egress exists in this distribution, and none is configurable.
#: Asserted structurally by ``tests/test_boundaries.py`` over the whole source
#: tree rather than declared here and trusted.
LIVE_VENDOR_EGRESS = False
