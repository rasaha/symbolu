"""Capability requirements.

A requirement states what an implementation must (or must never) be able to do,
and pins the registry entry that names that capability. This package does not
resolve the entry, does not know whether it exists, and does not decide whether
any implementation satisfies it — AC-0 ships no capability registry and no
conformance evaluation.
"""

from __future__ import annotations

from typing import Optional

from .common import CapabilityRegistryEntryRef, FrozenArtifact, RequirementObligation


class CapabilityRequirement(FrozenArtifact):
    """One capability obligation carried by a manifest or a constitution.

    ``entry_ref`` is optional because a requirement can legitimately be written
    before the capability it names exists in any registry. A requirement without a
    pinned entry is *narrative*: it is readable by a human and digestible by this
    package, but it names nothing a machine can resolve. Semantic validation
    reports that as INDETERMINATE for a MANDATORY obligation — a mandatory rule
    nobody can resolve cannot be declared satisfied or violated — while leaving a
    narrative CONDITIONAL or PROHIBITED requirement well-formed.
    """

    requirement_id: str
    summary: str
    obligation: RequirementObligation
    entry_ref: Optional[CapabilityRegistryEntryRef] = None
    condition: Optional[str] = None
    rationale: str = ""

    @property
    def is_resolvable(self) -> bool:
        """True when the requirement pins a registry entry a consumer could look up."""
        return self.entry_ref is not None

    @property
    def binds_unconditionally(self) -> bool:
        """True for obligations that apply with no stated precondition."""
        return self.obligation in (
            RequirementObligation.MANDATORY,
            RequirementObligation.PROHIBITED,
        )


__all__ = ["CapabilityRequirement"]
