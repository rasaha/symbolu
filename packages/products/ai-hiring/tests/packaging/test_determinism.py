"""Determinism tests — the demo and verification are reproducible.

The package ships only deterministic, offline adapters; running the canonical
demo twice must produce byte-identical structured output, and version metadata
must be stable.
"""

from __future__ import annotations

import json


def test_demo_is_reproducible():
    from ugence_ai_hiring.product.demo import run_demo

    first = run_demo()
    second = run_demo()
    assert first.summary() == second.summary()
    assert first.product_version == second.product_version


def test_version_info_is_stable_and_not_production_certified():
    from ugence_ai_hiring import version_info

    a = version_info().to_dict()
    b = version_info().to_dict()
    assert a == b
    assert a["production_certified"] is False
    assert a["product_version"] == "0.6.0"
    assert a["distribution_version"] == "0.1.1"


def test_version_info_json_serializes_stably():
    from ugence_ai_hiring import version_info

    s1 = json.dumps(version_info().to_dict(), sort_keys=True)
    s2 = json.dumps(version_info().to_dict(), sort_keys=True)
    assert s1 == s2


def test_demo_stops_before_enterprise_execution_of_denied_action():
    """A denied authorization must not reconcile an executed enterprise action."""
    from ugence_ai_hiring.product.demo import run_demo

    result = run_demo()
    rows = {r["case_id"]: r for r in result.summary()}
    denied = rows.get("demo-denied")
    assert denied is not None
    assert denied["authorization_outcome"] == "DENIED"
    # No reconciliation of a real enterprise effect follows a denied authorization.
    assert denied["reconciliation_outcome"] in (None, "", "-")
