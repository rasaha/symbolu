"""Verification report structures."""

from __future__ import annotations

from typing import Tuple

from ..models.common import CompilerModel


class VerificationCheck(CompilerModel):
    """One named verification check and its outcome."""

    name: str
    passed: bool
    detail: str = ""


class VerificationReport(CompilerModel):
    """The result of verifying a compiled package."""

    policy_pack_id: str
    structural_digest: str
    checks: Tuple[VerificationCheck, ...] = ()

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def failed_checks(self) -> Tuple[VerificationCheck, ...]:
        return tuple(c for c in self.checks if not c.passed)
