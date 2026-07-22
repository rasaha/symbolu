"""Deterministic exception (exemption) evaluation. Exceptions are never flattened."""
from __future__ import annotations
from typing import List, Mapping, Tuple


def evaluate(exemption_roles: List[str], situation: Mapping[str, str]
             ) -> Tuple[bool, str]:
    """Return (situation_is_exempt, basis). An EXEMPTS relationship whose exempted role
    matches the situation role exempts the situation from the otherwise-applicable
    obligation."""
    sr = (situation.get("user_role") or "").lower()
    for role in exemption_roles:
        r = (role or "").lower()
        if r and (r == sr or (r in sr) or (sr in r and sr)):
            return True, f"exempted: role '{role}' matches situation role '{sr}'"
    return False, ""
