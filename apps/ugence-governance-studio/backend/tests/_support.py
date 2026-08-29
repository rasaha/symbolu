"""Shared helpers for the Governance Studio API suite.

These live outside ``conftest.py`` deliberately. This directory is not a Python
package, so importing them as ``tests.conftest`` resolved ``tests`` against
whichever directory happened to be on ``sys.path`` first — and the P3A suite in
``apps/ugence-governance-studio/tests`` *is* a package of that name, so
collecting both suites in one pytest invocation bound the import to the wrong
one. Importing by the unique module name ``_support`` (the same idiom the P3A
suite uses for ``_loader``) keeps the two suites independent.
"""
from __future__ import annotations

SCENARIOS = (
    "procurement",
    "customer_support",
    "cybersecurity_success",
    "cybersecurity_no_feasible_team",
)


def result_of(response):
    body = response.json()
    return body["result"]
