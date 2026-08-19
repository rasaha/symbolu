"""Seal the contract-type registry, exactly once, at package import.

Imported last by :mod:`..contracts`. Importing every module that registers a
contract type and *then* sealing is what guarantees the registry is closed before
any application code can run: after this module finishes, no further registration
is possible from anywhere — including from inside this package, including from
code holding a reference to the "private" registration function.

The four registering modules are imported explicitly rather than relied on
transitively. A transitive import is an accident waiting to be refactored away,
and a module that stopped being imported would silently drop its classes out of
the registry — where they would then be refused by the encoder as unregistered,
which is a confusing failure a long way from its cause.
"""

from __future__ import annotations

from . import chain, envelopes, read_payloads, requests
from .canonical import _seal_contract_types

#: The four modules whose import populates the contract-type registry, named
#: rather than merely imported so the sealing dependency is explicit and a
#: linter can see that each one is load-bearing.
REGISTERING_MODULES = (chain, envelopes, read_payloads, requests)

_seal_contract_types()

#: Set once the registry is closed. :mod:`..contracts` imports this name, which
#: is what makes "seal last" a dependency the import graph enforces rather than
#: a comment a future edit could reorder past.
CONTRACT_TYPE_REGISTRY_SEALED = True
