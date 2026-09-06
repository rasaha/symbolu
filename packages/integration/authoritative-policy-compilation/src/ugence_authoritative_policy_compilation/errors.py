"""Typed refusals. Every one is a refusal; none is advisory.

The vocabulary is deliberately about **this root's** checks — resolution status,
coordinate agreement, descriptor completeness, body-digest re-verification, temporal
posture, and the derivation prohibition. Policy Authority's own refusals are carried
through verbatim rather than restated, so a reader can always tell which component
refused.
"""

from __future__ import annotations

from enum import Enum


class RefusalCode(str, Enum):
    #: The resolution is anything but RESOLVED; Policy Authority's reason is carried.
    POLICY_NOT_RESOLVED = "POLICY_NOT_RESOLVED"
    #: The resolved coordinate is not the one that was requested.
    RESOLVED_COORDINATE_MISMATCH = "RESOLVED_COORDINATE_MISMATCH"
    #: The descriptor triple is absent or partial, so the body digest is uncheckable.
    INCOMPLETE_RESOLUTION_DESCRIPTOR = "INCOMPLETE_RESOLUTION_DESCRIPTOR"
    #: The recomputed framed body digest does not equal the issuance record's.
    BODY_DIGEST_MISMATCH = "BODY_DIGEST_MISMATCH"
    #: A historical answer where the caller asked for current governance.
    HISTORICAL_RESOLUTION_NOT_REQUESTED = "HISTORICAL_RESOLUTION_NOT_REQUESTED"
    #: The supplied pack already carries an authoritative source (ruling X1-B).
    AUTHORED_SOURCE_REFUSED = "AUTHORED_SOURCE_REFUSED"
    #: No family pack builder was supplied (ruling CR-2).
    NO_PACK_BUILDER = "NO_PACK_BUILDER"
    #: The builder returned something that is not a policy_pack.v2 pack.
    BUILDER_RETURNED_UNUSABLE_PACK = "BUILDER_RETURNED_UNUSABLE_PACK"


class AuthoritativeCompilationError(Exception):
    """A refusal by this composition root. Carries its typed code."""

    def __init__(self, code: RefusalCode, message: str) -> None:
        super().__init__(f"{code.value}: {message}")
        self.code = code
        self.message = message


__all__ = ["RefusalCode", "AuthoritativeCompilationError"]
