"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package (and thus its dependencies).
"""

from __future__ import annotations

__version__ = "0.2.0"

#: Frozen contract identity of the record shapes.
#:
#: Moved to v2 in 0.2.0: an incident now names the published vocabulary its severity
#: label was written against (VV-A to VV-E, authorized by PUB-2). The binding is in the
#: record digest (VV-B) and deliberately **not** in the derived id (VV-C): an incident's
#: identity is its tenant, subject, evidence and instant, and the label never took part
#: in it.
CONTRACT_VERSION = "incident_response.v2"

#: The record shape before the binding. **No store ships here** (D-4), so this exists
#: for records whose digests were taken by somebody else and kept: those digests stay
#: valid under this version and are never recomputed under the v2 projection (VV-B).
#: It is not a mode a caller may select to skip a binding on new work.
LEGACY_CONTRACT_VERSION = "incident_response.v1"

#: Maturity, stated once and machine-readable. Records only: the package emits
#: records and proposals and acts on nothing.
MATURITY = "CONTRACTS_ONLY"
ENFORCEMENT_ENABLED = False
