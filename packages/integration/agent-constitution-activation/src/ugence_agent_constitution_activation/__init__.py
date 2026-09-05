"""Agent Constitution **issuance & activation** — orchestration, not authority.

The family distribution makes a constitution issuable; the conformance
distribution resolves one and replays presented facts against it; the shared
Policy Authority issues, signs, registers, resolves and revokes policy. This
distribution is the composition layer the `ACC-IA` round ratified: it wires
those existing surfaces into one deployment root, dry-runs an issuance before
anything signs, derives the governed reference map from the issued record, and
restates each act as a key-material-free receipt — so the `ACC-FC-5` deployment
gates are closable by running shipped machinery rather than by writing new
authority code.

What it is not
--------------
* **Not an authority.** It defines no signing, approval, canonicalization,
  registry or resolution semantics; every such act is a call into
  ``ugence_policy_authority.api`` or the constitution distributions. When a
  policy is issued through the root, the acting authority is the Policy
  Authority under the operator's injected trust — never this package.
* **Not custody.** The signer and both verifiers arrive already constructed.
  Nothing here can mint, read or persist key material, and the suite proves
  that over the source. No signing key, trust root or approval artifact exists
  anywhere in this repository.
* **Not a lifecycle authority** (`OD-C4=A`). Activation derives a reference
  map and lists it on a receipt; it writes no agent, role or registry state.
  There is no revocation seam: revocation remains the authority's own signed
  act.
* **Not a disposition** (`OD-C3=B`). A failed preflight row and a refusal are
  reports and typed errors; nothing maps either to an operational outcome.
* **Not a clock, a socket, a store or a plugin host.** Every instant is
  caller-supplied and timezone-aware.

What a receipt proves, and what it does not
-------------------------------------------
An ``IssuanceReceipt`` restates what the authority's signed record bound; an
``ActivationReceipt`` lists exactly the reference-map entries one activation
derived. Neither is a signed artifact, grants anything, or substitutes for the
record and registry, which remain the evidence. A passing ``PreflightReport``
is evidence about the checked instant, never a reservation of a future
issuance.
"""

from __future__ import annotations

from .composition import ActivationRoot, build_activation_root
from .errors import (
    ActivationCompositionError,
    ActivationRequestError,
    AgentConstitutionActivationError,
    ReferenceMapConflictError,
    ReferenceMapDerivationError,
)
from .preflight import PreflightCheck, PreflightReport, preflight_issuance
from .receipts import ActivationReceipt, IssuanceReceipt
from .reference_map import populate_reference_map
from .version import __version__

#: The curated public surface (`ACC-IA-1`): the root and its builder, the two
#: standalone seams (population and preflight) with their shapes, the two
#: receipts, and the error family. Nothing else is supported.
__all__ = [
    "__version__",
    # The composition root
    "ActivationRoot",
    "build_activation_root",
    # Governed reference-map population
    "populate_reference_map",
    # Preflight
    "preflight_issuance",
    "PreflightCheck",
    "PreflightReport",
    # Receipts
    "IssuanceReceipt",
    "ActivationReceipt",
    # Errors
    "AgentConstitutionActivationError",
    "ActivationCompositionError",
    "ActivationRequestError",
    "ReferenceMapDerivationError",
    "ReferenceMapConflictError",
]
