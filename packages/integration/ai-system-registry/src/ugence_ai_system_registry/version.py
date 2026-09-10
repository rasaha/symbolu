"""Single source of truth for the package version and maturity posture.

Read statically by the build backend (``tool.setuptools.dynamic``) so building a
wheel never has to import the package (and thus its dependencies).
"""

from __future__ import annotations

__version__ = "0.3.0"

#: Frozen contract identity of the registration record shape.
#:
#: Moved to v2 in 0.3.0: a registration now names the published vocabulary its
#: classification label was written against (VV-A to VV-E, authorized by PUB-2). The
#: binding is in the record digest (VV-B) and deliberately **not** in the derived id
#: (VV-C): this record's identity is the binding, the owner and the window, and the
#: label never participated in it, so neither does the label's vocabulary.
CONTRACT_VERSION = "ai_system_registry.v2"

#: The record shape before the binding. Records written under it stay **readable** and
#: are never recomputed under the v2 projection (VV-B). Nothing new is written under it
#: — the store refuses it — and it is not a mode a caller may select to skip a binding.
LEGACY_CONTRACT_VERSION = "ai_system_registry.v1"

#: Maturity, stated once and machine-readable. The contract modules stay contracts
#: only; 0.2.0 adds the one ruled local store (front-door FD-9.2), a sqlite file the
#: composing deployment owns. The package still resolves, gates and attests to nothing.
MATURITY = "CONTRACTS_PLUS_LOCAL_STORE"
#: The contract modules' own posture, unchanged by the local store.
CONTRACT_MATURITY = "CONTRACTS_ONLY"
ENFORCEMENT_ENABLED = False
