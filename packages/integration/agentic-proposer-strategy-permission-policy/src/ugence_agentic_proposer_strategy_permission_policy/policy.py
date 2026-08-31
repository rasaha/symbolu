"""The strategy-permission policy artifact.

**Why this family exists.** The Agentic Proposer owns a ratified
``StrategyPolicyResolver`` protocol and a six-check replay, but no policy family
existed for a resolver to resolve *against*, so Reasoning Strategy Permission
could not run end to end. This distribution is that policy family — the shared
Policy Authority's third, and the second registered from outside the authority's
own distribution.

**What it is.** A declarative, versioned, digest-bound statement that a role
reached by one exact ``strategy_policy_ref`` may declare exactly the strategies
in ``permitted_strategies``, drawn from one named vocabulary version.

**What it deliberately is not.**

* **No resolution.** Issuance, signing, registry, resolution and revocation all
  belong to the shared authority. This package supplies an artifact and an
  adapter, nothing else. It reads no clock, opens no socket, touches no storage
  and loads no plugin.
* **No composition, ordering or required strategy.** The permitted set is a
  permission, never an instruction: nothing here compels a procedure, orders one
  strategy before another, or names a subordinate strategy (`S2B-D3=A`).
* **No compute, quota, token count, capability tier or provider identity.**
  Permission grants no compute and no consequential execution authority.
* **No role identity.** Permission is role-level and the role *references* this
  policy; a role list inside the policy would invert the ratified direction.
* **No operational disposition.** What a permission failure should cause is
  deliberately unruled (`S2B-D5=A`), and nothing here names one.

**The permitted set, stated once.** Non-empty, free of duplicates, and stored in
ascending codepoint order — an unsorted tuple is **refused**, never silently
reordered, so the artifact a reader sees is the artifact its author wrote. Every
element is the exact string value of a member of the Agentic Proposer's
``ReasoningStrategy``, which is imported here as the single source of truth: no
second spelling of the vocabulary exists in this distribution to fork from.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from ugence_agentic_proposer import ReasoningStrategy

from .errors import (
    StrategyPermissionDuplicateError,
    StrategyPermissionFieldError,
    StrategyPermissionOrderingError,
)
from .identifiers import (
    ADMITTED_LIFECYCLE_STATES,
    ADMITTED_POLICY_SCOPES,
    POLICY_SCOPE_GLOBAL,
    POLICY_SCOPE_TENANT,
    STRATEGY_PERMISSION_POLICY_FAMILY,
    STRATEGY_VOCABULARY_VERSION,
)

__all__ = [
    "StrategyPermissionPolicy",
    "StrategyPermissionPolicyMetadata",
    "PLACEHOLDER_CONTENT_DIGEST",
    "ADMITTED_STRATEGY_TOKENS",
]

_HEX = frozenset("0123456789abcdef")

# C5b ``Token`` and C5a ``Identifier``, copied from the Agentic Proposer's ratified
# grammar. ``policy_id`` and ``version`` are stamped straight onto
# ``ProposerAdvisory``, so a policy that could not satisfy C5b would be lawfully
# issued and then unusable; checking the grammar at construction turns that into a
# refusal here rather than a failure at the advisory boundary.
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_MAX_IDENTIFIER_LENGTH = 200

#: The exact token set this family admits, derived from the imported vocabulary
#: rather than restated. A fork is structurally impossible: there is no second
#: spelling here to drift from.
ADMITTED_STRATEGY_TOKENS: frozenset = frozenset(member.value for member in ReasoningStrategy)

#: The digest an artifact declares while its real digest is still being computed.
#: The adapter's projection *removes* ``metadata.content_digest`` entirely, so this
#: value never participates in a body digest and no fixed point is involved.
PLACEHOLDER_CONTENT_DIGEST = "0" * 64


def _require_str(value: object, name: str, *, allow_empty: bool = False) -> str:
    if type(value) is not str:
        raise StrategyPermissionFieldError(f"{name} must be exactly a str")
    if not allow_empty and not value.strip():
        raise StrategyPermissionFieldError(f"{name} must be a non-empty str")
    return value


def _require_grammar(value: str, name: str, pattern, grammar: str) -> str:
    if len(value) > _MAX_IDENTIFIER_LENGTH:
        raise StrategyPermissionFieldError(
            f"{name} exceeds {_MAX_IDENTIFIER_LENGTH} characters"
        )
    if pattern.match(value) is None:
        raise StrategyPermissionFieldError(
            f"{name} does not satisfy the {grammar} grammar {pattern.pattern!r}"
        )
    return value


def _require_digest(value: object, name: str) -> str:
    if type(value) is not str or len(value) != 64 or any(c not in _HEX for c in value):
        raise StrategyPermissionFieldError(
            f"{name} must be a lowercase 64-char sha-256 hex digest"
        )
    return value


def _require_tzaware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise StrategyPermissionFieldError(f"{name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise StrategyPermissionFieldError(
            f"{name} must be timezone-aware; a naive datetime is never assumed to be UTC"
        )
    return value


@dataclass(frozen=True)
class StrategyPermissionPolicyMetadata:
    """The identity envelope the shared authority reads through the adapter.

    Deliberately this family's own type rather than a borrowed one: the authority
    is family-neutral, and a strategy-permission family that reused another
    family's envelope would take on that family's dependency for field reuse
    alone.

    ``policy_family`` is a **property, not a field**: it is fixed for this family,
    so it is not a value an author may set. It is bound into the signed identity
    through the ``PolicyCoordinate`` the adapter derives, which the issuance
    signature covers, rather than through the body projection.
    """

    policy_id: str
    version: str
    content_digest: str
    scope: str
    lifecycle_state: str
    tenant_id: str = ""
    supersedes_ref: str = ""
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None

    def __post_init__(self) -> None:
        _require_grammar(
            _require_str(self.policy_id, "StrategyPermissionPolicyMetadata.policy_id"),
            "StrategyPermissionPolicyMetadata.policy_id",
            _TOKEN_PATTERN,
            "C5b Token",
        )
        _require_grammar(
            _require_str(self.version, "StrategyPermissionPolicyMetadata.version"),
            "StrategyPermissionPolicyMetadata.version",
            _TOKEN_PATTERN,
            "C5b Token",
        )
        _require_digest(
            self.content_digest, "StrategyPermissionPolicyMetadata.content_digest"
        )
        _require_str(self.scope, "StrategyPermissionPolicyMetadata.scope")
        if self.scope not in ADMITTED_POLICY_SCOPES:
            raise StrategyPermissionFieldError(
                f"scope {self.scope!r} is not one of {sorted(ADMITTED_POLICY_SCOPES)}"
            )
        _require_str(
            self.lifecycle_state, "StrategyPermissionPolicyMetadata.lifecycle_state"
        )
        if self.lifecycle_state not in ADMITTED_LIFECYCLE_STATES:
            raise StrategyPermissionFieldError(
                f"lifecycle_state {self.lifecycle_state!r} is not one of "
                f"{sorted(ADMITTED_LIFECYCLE_STATES)}"
            )
        _require_str(
            self.tenant_id,
            "StrategyPermissionPolicyMetadata.tenant_id",
            allow_empty=True,
        )
        _require_str(
            self.supersedes_ref,
            "StrategyPermissionPolicyMetadata.supersedes_ref",
            allow_empty=True,
        )

        # Scope and tenant are one fact, not two. A GLOBAL policy carries the
        # authority's canonical empty tenant component; a TENANT policy that named
        # no tenant would resolve for the global tenant instead.
        if self.scope == POLICY_SCOPE_GLOBAL and self.tenant_id != "":
            raise StrategyPermissionFieldError(
                "a GLOBAL-scope policy must carry the canonical empty tenant component"
            )
        if self.scope == POLICY_SCOPE_TENANT and not self.tenant_id.strip():
            raise StrategyPermissionFieldError(
                "a TENANT-scope policy must name a non-empty tenant"
            )

        for name in ("effective_from", "effective_to"):
            value = getattr(self, name)
            if value is not None:
                _require_tzaware(value, f"StrategyPermissionPolicyMetadata.{name}")
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_to <= self.effective_from
        ):
            raise StrategyPermissionOrderingError(
                "effective_to must be strictly after effective_from; the interval is "
                "half-open [from, to) and an empty one can never admit a resolution"
            )

    @property
    def policy_family(self) -> str:
        return STRATEGY_PERMISSION_POLICY_FAMILY


@dataclass(frozen=True)
class StrategyPermissionPolicy:
    """A signed, versioned statement of which strategies a role may declare.

    ``strategy_policy_ref`` is **the reference this policy asserts it answers
    to**. It is what makes the reference-to-policy binding signed rather than
    deployment configuration: a resolver requires exact equality with the
    request's reference, so a caller-supplied value never becomes authoritative —
    it must *match* a value the issuing authority signed.

    ``vocabulary_version`` names the vocabulary the permitted tokens are drawn
    from, and is a fixed value by ruling. It participates in the projection, so
    it is part of the body digest and therefore part of the signed identity.
    """

    metadata: StrategyPermissionPolicyMetadata
    strategy_policy_ref: str
    permitted_strategies: Tuple[str, ...]
    vocabulary_version: str = STRATEGY_VOCABULARY_VERSION

    def __post_init__(self) -> None:
        if type(self.metadata) is not StrategyPermissionPolicyMetadata:
            raise StrategyPermissionFieldError(
                "StrategyPermissionPolicy.metadata must be exactly a "
                "StrategyPermissionPolicyMetadata"
            )
        _require_grammar(
            _require_str(
                self.strategy_policy_ref, "StrategyPermissionPolicy.strategy_policy_ref"
            ),
            "StrategyPermissionPolicy.strategy_policy_ref",
            _IDENTIFIER_PATTERN,
            "C5a Identifier",
        )
        _require_str(
            self.vocabulary_version, "StrategyPermissionPolicy.vocabulary_version"
        )
        if self.vocabulary_version != STRATEGY_VOCABULARY_VERSION:
            raise StrategyPermissionFieldError(
                f"vocabulary_version must be exactly {STRATEGY_VOCABULARY_VERSION!r}; "
                f"got {self.vocabulary_version!r}"
            )

        if type(self.permitted_strategies) is not tuple:
            raise StrategyPermissionFieldError(
                "StrategyPermissionPolicy.permitted_strategies must be a tuple — a list "
                "is mutable and this artifact is digested"
            )
        if not self.permitted_strategies:
            raise StrategyPermissionFieldError(
                "StrategyPermissionPolicy.permitted_strategies must name at least one "
                "strategy; a policy that permits nothing is expressed by revocation or "
                "by a lifecycle state, never by an empty set"
            )
        for index, token in enumerate(self.permitted_strategies):
            # Exactly ``str``: the artifact stays plain stdlib, so the projection
            # never depends on an enum coercion the authority would have to perform.
            if type(token) is not str:
                raise StrategyPermissionFieldError(
                    f"permitted_strategies[{index}] must be exactly a str, the string "
                    "value of a ReasoningStrategy member"
                )
            if token not in ADMITTED_STRATEGY_TOKENS:
                raise StrategyPermissionFieldError(
                    f"permitted_strategies[{index}] = {token!r} is not a member of the "
                    f"vocabulary {STRATEGY_VOCABULARY_VERSION!r}: "
                    f"{sorted(ADMITTED_STRATEGY_TOKENS)}"
                )
        if len(set(self.permitted_strategies)) != len(self.permitted_strategies):
            raise StrategyPermissionDuplicateError(
                "permitted_strategies names one strategy twice; membership must be "
                "unambiguous by construction"
            )
        if list(self.permitted_strategies) != sorted(self.permitted_strategies):
            raise StrategyPermissionOrderingError(
                "permitted_strategies must be stored in ascending codepoint order; an "
                "unsorted set is refused rather than reordered, so the artifact a "
                "reader sees is the artifact its author wrote"
            )

    def permits(self, strategy: object) -> bool:
        """Whether this policy names ``strategy``, by exact codepoint equality.

        Accepts a ``ReasoningStrategy`` member or its exact string value. There is
        no normalizer, no casefolding, no trimming and no splitting; anything that
        is not one of the vocabulary's exact spellings is simply not named.
        """

        if isinstance(strategy, ReasoningStrategy):
            return strategy.value in self.permitted_strategies
        if type(strategy) is str:
            return strategy in self.permitted_strategies
        raise StrategyPermissionFieldError(
            "permits(strategy) takes a ReasoningStrategy member or its exact str value"
        )
