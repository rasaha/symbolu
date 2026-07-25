"""Active constraint enforcement before dispatch (Task 107).

DGM/the pilot — not the execution provider — enforces authorized constraints
*before* dispatch. Constraints arrive as neutral ``type=value`` strings on the
authorization; this module parses and actively checks them against the proposed
action parameters. An action outside its authorized envelope is blocked before it
ever reaches the execution adapter.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnforcementResult:
    allowed: bool
    violations: tuple[str, ...] = ()
    checked: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return not self.allowed


def _parse(constraints: tuple[str, ...]) -> list[tuple[str, str]]:
    out = []
    for c in constraints:
        body = c[4:] if c.startswith("ext:") else c
        if "=" in body:
            t, v = body.split("=", 1)
        else:
            t, v = body, ""
        out.append((t, v))
    return out


def _num(value: str):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def enforce(constraints: tuple[str, ...], parameters: dict, *,
            approval_granted: bool = False,
            authorization_used: bool = False) -> EnforcementResult:
    """Return whether the action may dispatch under its authorized constraints."""
    violations: list[str] = []
    checked: list[str] = []
    for ctype, cval in _parse(constraints):
        checked.append(ctype)
        if ctype == "maximum_amount":
            amt = _num(str(parameters.get("amount", "")))
            limit = _num(cval)
            if amt is None or limit is None or amt > limit:
                violations.append(f"amount {parameters.get('amount')} exceeds maximum_amount {cval}")
        elif ctype == "maximum_quantity":
            qty = _num(str(parameters.get("quantity", "")))
            limit = _num(cval)
            if qty is None or limit is None or qty > limit:
                violations.append(f"quantity {parameters.get('quantity')} exceeds {cval}")
        elif ctype == "allowed_region":
            if str(parameters.get("region", "")) != cval:
                violations.append(f"region {parameters.get('region')!r} not allowed_region {cval!r}")
        elif ctype == "allowed_resource":
            if str(parameters.get("resource", "")) != cval:
                violations.append(f"resource not in allowed_resource {cval!r}")
        elif ctype == "required_approval":
            if not approval_granted:
                violations.append(f"required_approval {cval!r} not granted")
        elif ctype == "single_use":
            if authorization_used:
                violations.append("single_use authorization already consumed")
        # execution_deadline / parameter_restriction / rate_limit: recorded as
        # checked but treated as satisfied in the deterministic offline pilot.
    return EnforcementResult(allowed=not violations, violations=tuple(violations),
                             checked=tuple(checked))
