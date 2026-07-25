"""Constraint enforcement (benchmark-owned, provider-free).

Mirrors the frozen pilot's enforcement semantics so Strategy B (action-only) and
Strategy D (full, which reuses the pilot) enforce identically. A fairness test
asserts equivalence with the pilot on shared scenarios.
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
        t, v = (body.split("=", 1) if "=" in body else (body, ""))
        out.append((t, v))
    return out


def _num(value: str):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def enforce(constraints: tuple[str, ...], parameters: dict, *,
            approval_granted: bool = False, authorization_used: bool = False) -> EnforcementResult:
    violations: list[str] = []
    checked: list[str] = []
    for ctype, cval in _parse(constraints):
        checked.append(ctype)
        if ctype == "maximum_amount":
            amt, lim = _num(str(parameters.get("amount", ""))), _num(cval)
            if amt is None or lim is None or amt > lim:
                violations.append(f"amount {parameters.get('amount')} exceeds maximum_amount {cval}")
        elif ctype == "maximum_quantity":
            qty, lim = _num(str(parameters.get("quantity", ""))), _num(cval)
            if qty is None or lim is None or qty > lim:
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
    return EnforcementResult(allowed=not violations, violations=tuple(violations),
                             checked=tuple(checked))
