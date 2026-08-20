"""Seal the contract-type registry, exactly once, at package import.

Imported last by :mod:`..contracts`. Importing every module that registers a
contract type and *then* sealing is what guarantees the registry is closed before
any application code can run: after this module finishes, no further registration
is possible from anywhere — including from inside this package, including from
code holding a reference to the "private" registration function.

The five registering modules are imported explicitly rather than relied on
transitively. A transitive import is an accident waiting to be refactored away,
and a module that stopped being imported would silently drop its classes out of
the registry — where they would then be refused by the encoder as unregistered,
which is a confusing failure a long way from its cause.

BR-2B's :mod:`.kernel` is registered here for exactly that reason. Its three
contracts are canonicalizable, so they must reach the registry before it closes;
a kernel module that registered nothing would produce plans the encoder refuses
to render, which is the confusing failure this explicit list exists to prevent.
"""

from __future__ import annotations

from . import chain, envelopes, kernel, read_payloads, requests
from .canonical import _seal_contract_types

#: The five modules whose import populates the contract-type registry, named
#: rather than merely imported so the sealing dependency is explicit and a
#: linter can see that each one is load-bearing.
REGISTERING_MODULES = (chain, envelopes, kernel, read_payloads, requests)

_seal_contract_types()

#: Set once the registry is closed. :mod:`..contracts` imports this name, which
#: is what makes "seal last" a dependency the import graph enforces rather than
#: a comment a future edit could reorder past.
CONTRACT_TYPE_REGISTRY_SEALED = True
