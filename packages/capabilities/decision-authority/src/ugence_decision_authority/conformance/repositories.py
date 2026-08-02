"""Repositories dimension — platform repositories are kernel repository types."""
from __future__ import annotations

from .results import fail, ok


def check(fixture, platform, outcome):
    results = []
    for attr, expected in fixture.expected_repository_types().items():
        obj = getattr(platform, attr, None)
        good = isinstance(obj, expected) and type(obj).__module__.startswith(
            ("ugence_decision_authority.", "decision_governance."))
        results.append(
            ok("repositories", f"{attr}") if good
            else fail("repositories", f"{attr}",
                      f"{attr} is {type(obj)!r}, expected kernel {expected.__name__}"))
    return results
