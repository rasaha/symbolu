"""Seal the contract-type registry, exactly once, at package import.

Imported last by :mod:`..contracts`. Importing every module that registers a
contract type and *then* sealing is what guarantees the registry is closed before
any application code can run: after this module finishes, no further registration
is possible from anywhere — including from inside this package, including from
code holding a reference to the "private" registration function.

The six registering modules are imported explicitly rather than relied on
transitively. A transitive import is an accident waiting to be refactored away,
and a module that stopped being imported would silently drop its classes out of
the registry — where they would then be refused by the encoder as unregistered,
which is a confusing failure a long way from its cause.

BR-2B's :mod:`.kernel` is registered here for exactly that reason. Its three
contracts are canonicalizable, so they must reach the registry before it closes;
a kernel module that registered nothing would produce plans the encoder refuses
to render, which is the confusing failure this explicit list exists to prevent.

BR-2C's :mod:`.trust` joins the list on the same ground, and D-24 and D-25
require it by name: each new root-canonicalizable type must be registered here
**before the seal closes**. Its four contracts include
:class:`~.trust.BenchmarkTrustAnchorRecord`, whose canonical digest D-25 makes
the **anchor revision** — an unregistered anchor record would be refused by the
encoder, and the revision it is supposed to carry would not exist.

:mod:`.trust` is imported here rather than left to reach the registry through
:mod:`.ports`, which imports it for its type annotations. A module that is
registered only as a side effect of another module's annotations is one
refactor away from silently dropping out.
"""

from __future__ import annotations

from . import chain, envelopes, kernel, read_payloads, requests, trust
from .canonical import _seal_contract_types

#: The six modules whose import populates the contract-type registry, named
#: rather than merely imported so the sealing dependency is explicit and a
#: linter can see that each one is load-bearing.
REGISTERING_MODULES = (chain, envelopes, kernel, read_payloads, requests, trust)

_seal_contract_types()

#: Set once the registry is closed. :mod:`..contracts` imports this name, which
#: is what makes "seal last" a dependency the import graph enforces rather than
#: a comment a future edit could reorder past.
CONTRACT_TYPE_REGISTRY_SEALED = True
