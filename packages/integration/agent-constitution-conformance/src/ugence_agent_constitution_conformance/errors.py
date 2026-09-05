"""The conformance boundary's failure taxonomy. One root, no disposition.

`[R]` **None of these names, and no message any of them carries, emits a denial,
an abstention, a reserved authority term, a terminal outcome or a candidate
disposition.** They name resolution and integrity facts only. Which component
maps a structural conformance failure to an operational outcome — abstention,
hold, escalation or referral — is deliberately unruled (`OD-C3=B`, continuing
`S2B-D5=A`), and nothing here maps one. The conformance verifier itself returns
``True`` or ``False`` and raises none of the resolution rows.

**The reason token discipline, and why it is not cosmetic.** A Policy Authority
``PolicyResolutionReason`` reaches a caller through
:attr:`ConstitutionUnresolvedError.reason` and **through nothing else**: never
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
    "AgentConstitutionConformanceError",
    "ConstitutionFactsError",
    "UnknownConstitutionReferenceError",
    "ConstitutionTenantScopeError",
    "ConstitutionUnresolvedError",
    "ConstitutionArtifactTypeError",
    "ConstitutionRoleBindingError",
    "ConstitutionVocabularyError",
    "ConstitutionReferenceBindingError",
]


class AgentConstitutionConformanceError(Exception):
    """Root of this boundary's error taxonomy.

    Every resolution failure path raises one of these. Nothing degraded, partial
    or defaulted is ever returned: a resolved constitution exists only when the
    authority answered with a resolution, which is the whole of the evidence
    this boundary offers.
    """

    #: The authority's machine-readable cause, when one exists. ``None`` on the
    #: failures this boundary detects itself, before or after the authority call.
    reason = None


class ConstitutionFactsError(AgentConstitutionConformanceError):
    """A presented input is absent, of the wrong exact type, or outside its grammar."""


class UnknownConstitutionReferenceError(AgentConstitutionConformanceError):
    """The reference map holds no coordinate for this tenant and role reference."""


class ConstitutionTenantScopeError(AgentConstitutionConformanceError):
    """The configured coordinate's scope and tenant do not agree with the request."""


class ConstitutionUnresolvedError(AgentConstitutionConformanceError):
    """The authority answered, and the answer was not a resolution.

    ``reason`` carries the authority's ``PolicyResolutionReason`` verbatim. It is
    the only channel through which that token reaches a caller.
    """

    def __init__(self, message: str, *, reason: Optional[object] = None) -> None:
        super().__init__(message)
        self.reason = reason


class ConstitutionArtifactTypeError(AgentConstitutionConformanceError):
    """The artifact under this coordinate is not exactly this family's artifact."""


class ConstitutionRoleBindingError(AgentConstitutionConformanceError):
    """The resolved constitution's signed role list does not contain this role."""


class ConstitutionVocabularyError(AgentConstitutionConformanceError):
    """The resolved constitution carries a bound token outside its source vocabulary."""


class ConstitutionReferenceBindingError(AgentConstitutionConformanceError):
    """The reference the constitution is signed as named by is not the presented one."""
