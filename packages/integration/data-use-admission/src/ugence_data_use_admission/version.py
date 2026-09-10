"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package (and thus its dependencies).
"""

from __future__ import annotations

__version__ = "0.3.0"

#: Frozen contract identity of the declaration record shape.
#:
#: Moved to v2 in 0.3.0: a declaration now names the published vocabulary each of its
#: two labels was written against (VV-A to VV-E, authorized by PUB-2). The bindings are
#: in the record digest (VV-B) and in the derived id (VV-C), so this is not an additive
#: change and does not pretend to be one.
CONTRACT_VERSION = "data_use_admission.v2"

#: The record shape before the bindings. Records written under it stay **readable** and
#: are never recomputed under the v2 projection (VV-B): their digests and derived ids
#: remain valid under this version. Nothing new is written under it — the store refuses
#: it — and it is not a compatibility mode that a caller may select to skip a binding.
LEGACY_CONTRACT_VERSION = "data_use_admission.v1"

#: Maturity, stated once and machine-readable. The package records what a declarer
#: asserted about data and admits, classifies and enforces nothing; since 0.2.0 it also
#: keeps those records in one tenant-bound local sqlite file (FD-12.2), which changes
#: where a declaration lives and nothing about what it means. 0.3.0 adds which
#: vocabulary each label was written against, which changes what a record *says* and
#: still nothing about what this package may *do* with it.
MATURITY = "CONTRACTS_PLUS_LOCAL_STORE"

#: What the record shape itself is, unchanged by the store: contracts only.
CONTRACT_MATURITY = "CONTRACTS_ONLY"
ENFORCEMENT_ENABLED = False
