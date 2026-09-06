"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package (and thus its dependencies).
"""

from __future__ import annotations

__version__ = "0.1.0"

#: Frozen contract identity of the exported artifact shape.
CONTRACT_VERSION = "clearance_export.artifact.v1"

#: Maturity, stated once and machine-readable. Contracts only: a record type, a
#: read-only Protocol, refusal reasons and one pure verifier (CE-2). There is no
#: store, adapter, connector, clock or network here, so an export cannot reach a
#: clearance, a policy, a key or a runtime.
MATURITY = "CONTRACTS_ONLY"

#: This package never enforces. It serializes a clearance somebody else evaluated
#: and reports what a reader can check about it.
ENFORCEMENT_ENABLED = False
