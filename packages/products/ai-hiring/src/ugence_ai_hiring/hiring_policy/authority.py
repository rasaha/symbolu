"""Approver authority — what an approval-chain role may grant.

Used by compile-check (e): a policy whose declared action constraints exceed the
authority of every approver in its chain is rejected, so a contract can never be
published that no one is empowered to approve.

The default table is a conservative, offline stand-in; production deployments
inject a real authority source. Levels are compared as ``L<n>`` (higher ``n`` =
more senior); unknown formats are treated as not-authorized unless listed
explicitly.
"""

from __future__ import annotations

import re
from typing import Optional

_LEVEL_RE = re.compile(r"^[Ll](\d+)$")


def parse_level(level: str) -> Optional[int]:
    """Parse an ``L<n>`` seniority level to its integer, or None if unrecognized."""
    m = _LEVEL_RE.match(level.strip())
    return int(m.group(1)) if m else None


class ApproverAuthority:
    """Maps an approver role to the maximum salary and level it may grant."""

    def __init__(self, limits: Optional[dict[str, tuple[float, str]]] = None) -> None:
        # role -> (max_salary, max_level)
        self._limits: dict[str, tuple[float, str]] = dict(limits or _DEFAULT_LIMITS)

    def max_for(self, role: str) -> Optional[tuple[float, str]]:
        return self._limits.get(role.strip())

    def authorizes(self, role: str, *, salary: float, level: str) -> bool:
        limit = self.max_for(role)
        if limit is None:
            return False
        max_salary, max_level = limit
        if salary > max_salary:
            return False
        want = parse_level(level)
        cap = parse_level(max_level)
        if want is None or cap is None:
            # unrecognized level format: authorize only on exact string match
            return level.strip() == max_level.strip()
        return want <= cap

    def chain_authorizes(self, chain: tuple[str, ...], *, salary: float, level: str) -> bool:
        """True if ANY approver in the chain may grant the constraints."""
        return any(self.authorizes(r, salary=salary, level=level) for r in chain)


# Conservative default limits for common roles (offline stand-in).
_DEFAULT_LIMITS: dict[str, tuple[float, str]] = {
    "Hiring Manager": (180000.0, "L4"),
    "Director": (260000.0, "L6"),
    "VP Eng": (400000.0, "L8"),
    "VP Engineering": (400000.0, "L8"),
    "CTO": (600000.0, "L10"),
    "CEO": (1000000.0, "L11"),
}
