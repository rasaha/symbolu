"""OpenAPI + public-API freeze and fixture-bundle drift tests (§24, §25, §32)."""
from __future__ import annotations

import json
import os

import ugence_governance_studio_api as pkg
from ugence_governance_studio_api.openapi import canonical_openapi_bytes

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP = os.path.dirname(_BACKEND)
_REPO = os.path.dirname(os.path.dirname(_APP))


def test_openapi_no_drift():
    with open(os.path.join(_APP, "contracts", "openapi.json"), "rb") as fh:
        committed = fh.read()
    assert committed == canonical_openapi_bytes()


def test_openapi_is_host_free_and_stable():
    schema = json.loads(canonical_openapi_bytes())
    assert schema.get("servers", []) == []
    # every operation has a stable operationId
    for path in schema["paths"].values():
        for method in path.values():
            if isinstance(method, dict) and "operationId" in method:
                assert method["operationId"]


def test_public_api_snapshot_no_drift():
    with open(os.path.join(_BACKEND, "artifacts", "public_api.json"), "rb") as fh:
        committed = json.load(fh)
    assert committed["names"] == sorted(pkg.__all__)


def test_bundled_fixtures_match_p3a_source():
    """The wheel-bundled scenario fixtures are byte-identical to the P3A source,
    so the isolated distribution executes the SAME frozen inputs (P3B-A2)."""
    bundled = os.path.join(os.path.dirname(pkg.__file__), "data")
    for scenario in ("procurement", "customer_support", "cybersecurity_success",
                     "cybersecurity_no_feasible_team"):
        for kind, src_root in (("demo_data", os.path.join(_APP, "demo_data")),
                               ("expected_outputs", os.path.join(_APP, "expected_outputs"))):
            src_dir = os.path.join(src_root, scenario)
            bundled_dir = os.path.join(bundled, kind, scenario)
            for fname in os.listdir(src_dir):
                with open(os.path.join(src_dir, fname), "rb") as a, \
                        open(os.path.join(bundled_dir, fname), "rb") as b:
                    assert a.read() == b.read(), f"bundled {kind}/{scenario}/{fname} drifted"
