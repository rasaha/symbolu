"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package (and thus its dependencies).
"""

from __future__ import annotations

__version__ = "0.3.0"

#: Frozen contract identity of the declaration record shape.
#:
#: Moved to v2 in 0.3.0: a declaration now names the published vocabulary its risk
#: posture was written against (VV-A to VV-E, authorized by PUB-2). The binding is in
#: the record digest (VV-B) **and in the derived id** (VV-C), because risk_posture
#: already participates in this record's identity — so the vocabulary it was read under
#: does too.
CONTRACT_VERSION = "vendor_dependency.v2"

#: The record shape before the binding. Records written under it stay **readable** and
#: are never recomputed under the v2 projection (VV-B): their digests and derived ids
#: remain valid under this version. Nothing new is written under it — the store refuses
#: it — and it is not a mode a caller may select to skip a binding.
LEGACY_CONTRACT_VERSION = "vendor_dependency.v1"

#: Maturity, stated once and machine-readable. Since 0.2.0 the package also keeps
#: those records in one tenant-bound local file (front-door ruling FD-13.2). It still
#: records what a declarer asserted about a vendor dependency and evaluates nothing.
MATURITY = "CONTRACTS_PLUS_LOCAL_STORE"

#: The contract surface itself is unchanged by the store: the record types, refusal
#: reasons, selectors and port are exactly what 0.1.0 shipped.
CONTRACT_MATURITY = "CONTRACTS_ONLY"
ENFORCEMENT_ENABLED = False
