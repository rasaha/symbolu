"""The concrete strategy-permission ``StrategyPolicyResolver``.

The Agentic Proposer owns the resolver protocol, the request and response shapes,
the call and the replay. It owns no policy and resolves nothing. The shared Policy
Authority issues, signs, registers, resolves and revokes policy and knows no
strategy vocabulary. This distribution is the one component that speaks to both:
it maps a reference to an exact policy coordinate, resolves that coordinate
through the authority, and answers with the proposer's ratified response shape.

Together with the strategy-permission family package, it is what makes Reasoning
Strategy Permission runnable end to end. On its own it resolves nothing — it holds
no policy, mints no coordinate and configures no trust.

What it is not
--------------
* **Not an authorizer.** Permission grants no compute, no tools, no evidence
  access and no consequential execution. Nothing here authorizes a runtime action;
  consequential execution remains with Risk Authority, ActionGate and Decision
  Authority.
* **Not a policy source.** It issues nothing, signs nothing and stores nothing.
  The reachable coordinate set is deployment trust configuration, injected.
* **Not a clock, a socket, a store or a plugin host.** ``as_of`` is the caller's.
* **Not a disposition.** What a permission failure should cause operationally is
  deliberately unruled, and nothing here maps one.

What a successful call proves, and what it does not
---------------------------------------------------
Under the trust roots the call was configured with, and at the caller's explicit
``as_of``: the artifact was signed by an authorized, entitled, un-revoked key over
exactly this canonical body; external approval evidence verified, and still
verifies now; the lifecycle and effective period admit it; no unstructured
supersession is declared; and no verified revocation applies.

It proves nothing about whether the permitted set is wise, correct or lawful; it
establishes nothing about private reasoning; it does not prove any declared
procedure was executed; and it cannot detect a dishonest resolver, since the
reference echo is a correlation check rather than a defence.
"""

from __future__ import annotations

from .composition import build_strategy_policy_resolver
from .errors import (
    StrategyPermissionResolverError,
    StrategyPolicyArtifactError,
    StrategyPolicyReferenceBindingError,
    StrategyPolicyTenantScopeError,
    StrategyPolicyUnresolvedError,
    StrategyPolicyVocabularyError,
    UnknownStrategyPolicyReferenceError,
)
from .resolver import PolicyAuthorityStrategyPolicyResolver
from .version import __version__

#: The curated public surface, exactly as ratified: the resolver, its error
#: family, and one composition helper.
#:
#: `with_strategy_permission_adapter` and `HISTORICAL_RESOLUTION` were exported here
#: in an earlier draft and are **internal** by owner ruling `SURFACE=B`. Neither is
#: re-exported from this module; each lives in the module that owns it, and
#: `build_strategy_policy_resolver` is the supported way to reach the first. The
#: ratified surface is §8's delta table, which names one composition helper and no
#: constant.
__all__ = [
    "__version__",
    # The resolver
    "PolicyAuthorityStrategyPolicyResolver",
    # Composition
    "build_strategy_policy_resolver",
    # Errors
    "StrategyPermissionResolverError",
    "UnknownStrategyPolicyReferenceError",
    "StrategyPolicyTenantScopeError",
    "StrategyPolicyUnresolvedError",
    "StrategyPolicyArtifactError",
    "StrategyPolicyReferenceBindingError",
    "StrategyPolicyVocabularyError",
]
