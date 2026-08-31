"""The resolver's failure taxonomy. One root, six leaves, no disposition.

`[R]` **None of these names, and no message any of them carries, emits a denial,
an abstention, a reserved authority term, a terminal outcome or a candidate
disposition.** They name resolution and integrity facts only. Which component
maps a structural permission failure to an operational outcome — abstention,
hold, escalation or referral — is deliberately unruled, and nothing here maps
one.

**The reason token discipline, and why it is not cosmetic.** A Policy Authority
``PolicyResolutionReason`` reaches a caller through
:attr:`StrategyPolicyUnresolvedError.reason` and **through nothing else**: never
interpolated into a message, never rendered into prose. The Agentic Proposer's
refusal guard uppercases text and tests substring containment, and its reserved
authority vocabulary contains ``EXPIRED``, ``UNSUPPORTED`` and ``SUPPORTED`` — so
the reason ``EXPIRED`` is a reserved term verbatim, and
``SUPERSESSION_REFERENCE_UNSUPPORTED`` contains two of them. Interpolating the
authority's own reason into a message would make this package emit reserved
authority vocabulary without anyone choosing to. A caller that wants the reason
reads the attribute, where it is machine-readable and costs nothing.
"""

from __future__ import annotations

from typing import Optional

__all__ = [
    "StrategyPermissionResolverError",
    "UnknownStrategyPolicyReferenceError",
    "StrategyPolicyTenantScopeError",
    "StrategyPolicyUnresolvedError",
    "StrategyPolicyArtifactError",
    "StrategyPolicyReferenceBindingError",
    "StrategyPolicyVocabularyError",
]


class StrategyPermissionResolverError(Exception):
    """Root of this resolver's error taxonomy.

    Every failure path raises one of these. Nothing degraded, partial or
    defaulted is ever returned: a response exists only when the authority
    answered with a resolution, which is the whole of the evidence this boundary
    offers.
    """

    #: The authority's machine-readable cause, when one exists. ``None`` on the
    #: failures this resolver detects itself, before or after the authority call.
    reason = None


class UnknownStrategyPolicyReferenceError(StrategyPermissionResolverError):
    """The reference map holds no coordinate for this tenant and reference."""


class StrategyPolicyTenantScopeError(StrategyPermissionResolverError):
    """The configured coordinate's scope and tenant do not agree with the request."""


class StrategyPolicyUnresolvedError(StrategyPermissionResolverError):
    """The authority answered, and the answer was not a resolution.

    ``reason`` carries the authority's ``PolicyResolutionReason`` verbatim. It is
    the only channel through which that token reaches a caller.
    """

    def __init__(self, message: str, *, reason: Optional[object] = None) -> None:
        super().__init__(message)
        self.reason = reason


class StrategyPolicyArtifactError(StrategyPermissionResolverError):
    """The artifact the authority returned is not this family's artifact."""


class StrategyPolicyReferenceBindingError(StrategyPermissionResolverError):
    """The reference the policy is signed as answering to is not the request's."""


class StrategyPolicyVocabularyError(StrategyPermissionResolverError):
    """The policy carries a token outside the strategy vocabulary."""
