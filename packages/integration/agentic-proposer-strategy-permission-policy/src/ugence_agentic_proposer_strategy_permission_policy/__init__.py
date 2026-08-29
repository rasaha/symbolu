"""The Agentic Proposer **strategy-permission** policy family and its adapter.

Reasoning Strategy Permission was ratified with a resolver protocol, a request
and response shape and a six-check replay, and with **no policy family for a
resolver to resolve against**. This distribution is that policy family — the
shared Policy Authority's third, and the second registered from outside the
authority's own distribution.

What it establishes
-------------------
A ``StrategyPermissionPolicy`` is a declarative, versioned, digest-bound artifact
naming the reference it answers to, the strategies it permits, and the vocabulary
version those strategies are drawn from. Issued and signed through the shared
authority, it is the first artifact in the tree a strategy declaration could ever
be checked against.

What it deliberately does not do
--------------------------------
* **No resolution.** Issuance, signing, registry, resolution and revocation all
  belong to the shared authority; the concrete resolver is a separate
  distribution. This package holds no registry, no mapping and no resolver.
* **No authorization and no execution authority.** Permission grants no compute,
  no tools, no evidence access and no consequential execution. Nothing here
  authorizes a runtime action.
* **No signing.** This package supplies an artifact and an adapter, nothing else.
* **No operational disposition.** What a permission failure should cause is
  deliberately unruled, and nothing here maps one.
* **No clock, socket, storage or plugin loading.** Every instant is a caller's.

**Status.** This distribution alone does not make Reasoning Strategy Permission
executable: a family that can be issued still needs a concrete resolver before
anything runs end to end. That resolver ships separately.

Wiring is the composition root's job: register
:class:`StrategyPermissionPolicyFamilyAdapter` on an ``AdapterRegistry`` alongside
whatever other adapters that root configures.
"""

from __future__ import annotations

from .adapter import (
    StrategyPermissionPolicyFamilyAdapter,
    strategy_permission_coordinate,
)
from .errors import (
    StrategyPermissionDuplicateError,
    StrategyPermissionFieldError,
    StrategyPermissionOrderingError,
    StrategyPermissionPolicyError,
)
from .identifiers import (
    ACTIVE_LIFECYCLE_STATE,
    ADMITTED_LIFECYCLE_STATES,
    ADMITTED_POLICY_SCOPES,
    LIFECYCLE_APPROVED_ACTIVE,
    LIFECYCLE_DRAFT,
    LIFECYCLE_SUPERSEDED,
    LIFECYCLE_WITHDRAWN,
    POLICY_SCOPE_GLOBAL,
    POLICY_SCOPE_TENANT,
    STRATEGY_PERMISSION_ADAPTER_ID,
    STRATEGY_PERMISSION_POLICY_FAMILY,
    STRATEGY_PERMISSION_POLICY_TYPE,
    STRATEGY_VOCABULARY_VERSION,
)
from .policy import (
    ADMITTED_STRATEGY_TOKENS,
    PLACEHOLDER_CONTENT_DIGEST,
    StrategyPermissionPolicy,
    StrategyPermissionPolicyMetadata,
)
from .version import __version__

__all__ = [
    "__version__",
    # Identity
    "STRATEGY_PERMISSION_ADAPTER_ID",
    "STRATEGY_PERMISSION_POLICY_FAMILY",
    "STRATEGY_PERMISSION_POLICY_TYPE",
    "STRATEGY_VOCABULARY_VERSION",
    "POLICY_SCOPE_GLOBAL",
    "POLICY_SCOPE_TENANT",
    "ADMITTED_POLICY_SCOPES",
    "LIFECYCLE_DRAFT",
    "LIFECYCLE_APPROVED_ACTIVE",
    "LIFECYCLE_SUPERSEDED",
    "LIFECYCLE_WITHDRAWN",
    "ADMITTED_LIFECYCLE_STATES",
    "ACTIVE_LIFECYCLE_STATE",
    "ADMITTED_STRATEGY_TOKENS",
    # Artifact
    "StrategyPermissionPolicy",
    "StrategyPermissionPolicyMetadata",
    "PLACEHOLDER_CONTENT_DIGEST",
    # Adapter
    "StrategyPermissionPolicyFamilyAdapter",
    "strategy_permission_coordinate",
    # Errors
    "StrategyPermissionPolicyError",
    "StrategyPermissionFieldError",
    "StrategyPermissionOrderingError",
    "StrategyPermissionDuplicateError",
]
