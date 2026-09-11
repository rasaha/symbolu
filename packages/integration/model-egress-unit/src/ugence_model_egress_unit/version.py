"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package (and thus its dependencies).
"""

from __future__ import annotations

__version__ = "0.3.0"

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
#: ``MEU_LIVE_VALIDATION.json``. ``EgressResult`` refuses ``genuine_call: true`` unless
#: this reads ``MET``, so no configuration and no adapter can admit a genuine result
#: before the owner's separate acceptance statement, which is itself a release.
COMMISSIONING_STATUS = "BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS"

#: No live vendor egress exists in this distribution, and none is configurable.
#: Asserted structurally by ``tests/test_boundaries.py`` over the whole source
#: tree rather than declared here and trusted.
LIVE_VENDOR_EGRESS = False
