"""Typed construction and registration errors for the Agent Constitution family.

Every failure is fail-closed: no ``AgentConstitutionPolicy`` is produced and no
registration is confirmed. A malformed artifact never reaches the authority, and
one that somehow does is refused again by the adapter.

`[R]` **None of these names, and no message any of them carries, emits a denial,
an abstention, a reserved authority term, a terminal outcome or a candidate
disposition.** They name construction and identity facts only. The
structural-failure operational-disposition owner remains deliberately unassigned
(`OD-C3=B`), and nothing here maps one.
"""

from __future__ import annotations

__all__ = [
    "AgentConstitutionPolicyError",
    "AgentConstitutionFieldError",
    "AgentConstitutionOrderingError",
    "AgentConstitutionDuplicateError",
    "AgentConstitutionFamilyCollisionError",
]


class AgentConstitutionPolicyError(Exception):
    """Root of this family's error taxonomy."""


class AgentConstitutionFieldError(AgentConstitutionPolicyError):
    """A field is absent, of the wrong exact type, or outside its admitted domain."""


class AgentConstitutionOrderingError(AgentConstitutionPolicyError):
    """A declared ordering is violated: a bound, the role list, or the effective interval."""


class AgentConstitutionDuplicateError(AgentConstitutionPolicyError):
    """A declared set names one member twice, so its membership is ambiguous."""


class AgentConstitutionFamilyCollisionError(AgentConstitutionPolicyError):
    """The assembled registry does not answer for this family exactly once.

    Raised by the `ACC-S1-Q3` registration-time guard: either no adapter answers
    for the Agent Constitution family, more than one does, or another registered
    adapter advertises this family's ratified value under a different identity.
    """
