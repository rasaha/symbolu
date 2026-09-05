"""SD-2 — the studio never issues, activates, revokes, grants, authorizes, clears
or executes.

Owner ruling SD-2 (``NON_AUTHORITY_STUDIO``) says this is enforced by a test, not by
prose: "a prohibition that is only prose drifts; this one can be a test". So the whole
v2 contract is scanned, and a route whose operation id, path or summary names an
authority act fails the build.
"""
from __future__ import annotations

import json
import os

import pytest

from ugence_governance_studio_api.openapi_v2 import canonical_v2_openapi_bytes
from ugence_governance_studio_api.version import API_V2_CONTRACT_VERSION

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_APP = os.path.dirname(_BACKEND)

#: The seven verbs SD-2 names. Matched as substrings, case-insensitively, so
#: ``authorize_action`` and ``v2_grant`` are both caught.
PROHIBITED_VERBS = (
    "issue", "activate", "revoke", "grant", "authorize", "clear", "execute",
)


@pytest.fixture(scope="module")
def v2_schema():
    return json.loads(canonical_v2_openapi_bytes())


def _operations(schema):
    for path, methods in schema["paths"].items():
        for method, op in methods.items():
            if isinstance(op, dict) and "operationId" in op:
                yield path, method, op


def test_no_v2_operation_id_names_an_authority_act(v2_schema):
    violations = []
    for path, method, op in _operations(v2_schema):
        lowered = op["operationId"].lower()
        for verb in PROHIBITED_VERBS:
            if verb in lowered:
                violations.append(f"{method.upper()} {path} -> {op['operationId']} ({verb})")
    assert violations == [], (
        "SD-2 violation — the studio never performs an authority act:\n  "
        + "\n  ".join(violations)
    )


def test_no_v2_path_names_an_authority_act(v2_schema):
    """The path is as visible as the operation id, and just as bindable."""
    violations = []
    for path, method, _op in _operations(v2_schema):
        lowered = path.lower()
        for verb in PROHIBITED_VERBS:
            if verb in lowered:
                violations.append(f"{method.upper()} {path} ({verb})")
    assert violations == [], "SD-2 violation in a route path:\n  " + "\n  ".join(violations)


def test_the_prohibition_test_actually_catches_a_violation():
    """A guard that cannot fail is not a guard.

    Without this, a refactor that broke the matching would leave every assertion above
    passing vacuously and the ruling unenforced.
    """
    fake = {
        "paths": {
            "/api/v2/policy/issue": {
                "post": {"operationId": "v2_policy_issue_release"}
            }
        }
    }
    caught = [
        op["operationId"]
        for _p, _m, op in _operations(fake)
        if any(v in op["operationId"].lower() for v in PROHIBITED_VERBS)
    ]
    assert caught == ["v2_policy_issue_release"]


def test_every_v2_operation_has_a_stable_operation_id(v2_schema):
    for path, method, op in _operations(v2_schema):
        assert op["operationId"], f"{method.upper()} {path} has an empty operationId"
        assert op["operationId"].startswith("v2_"), (
            f"{op['operationId']} must be namespaced so it cannot collide with a v1 id"
        )


def test_v2_is_host_free_like_v1(v2_schema):
    assert v2_schema.get("servers", []) == []


def test_v2_contract_identity(v2_schema):
    assert v2_schema["info"]["version"] == API_V2_CONTRACT_VERSION


def test_v2_document_is_committed_and_free_of_drift():
    with open(os.path.join(_APP, "contracts", "openapi_v2.json"), "rb") as fh:
        committed = fh.read()
    assert committed == canonical_v2_openapi_bytes()


def test_v1_and_v2_are_separate_documents():
    """The whole reason v2 is its own application.

    Generating v2 must not change a byte of v1, because ``test_freeze.py`` asserts v1
    against a committed artifact and must keep passing unchanged.
    """
    from ugence_governance_studio_api.openapi import canonical_openapi_bytes

    v1 = json.loads(canonical_openapi_bytes())
    v2 = json.loads(canonical_v2_openapi_bytes())

    assert set(v1["paths"]) & set(v2["paths"]) == set(), "the documents must not overlap"
    assert all(p.startswith("/api/v2/") for p in v2["paths"]), (
        "every v2 route is namespaced under /api/v2/"
    )
    assert not any(p.startswith("/api/v2/") for p in v1["paths"]), (
        "no v2 route may have leaked into the frozen v1 document"
    )


def test_console_client_cannot_reach_an_authority_route():
    """SD-2 at the outbound edge, not only the inbound one.

    The console exposes ``/v1/actions/authorize`` and ``/v1/actions/clear``. The studio's
    client refuses them before opening a connection.
    """
    from ugence_governance_studio_api.clients.console import (
        CONSOLE_ALLOWED_ROUTES,
        ConsoleClient,
        ConsoleUnavailable,
    )

    assert len(CONSOLE_ALLOWED_ROUTES) == 4
    for _method, path in CONSOLE_ALLOWED_ROUTES:
        assert not any(v in path.lower() for v in PROHIBITED_VERBS), path

    client = ConsoleClient("http://console.invalid")
    for method, path in (
        ("POST", "/v1/actions/authorize"),
        ("POST", "/v1/actions/clear"),
        ("POST", "/v1/governed-loop/live"),
    ):
        with pytest.raises(ConsoleUnavailable) as excinfo:
            client._request(method, path)  # noqa: SLF001
        assert "not in the studio's permitted console route set" in str(excinfo.value)


def test_review_client_cannot_reach_a_resume_signal_or_authority_route():
    """HR-1 at the outbound edge: the review client is display and transmit only."""
    from ugence_governance_studio_api.clients.review import (
        REVIEW_ALLOWED_ROUTES,
        ReviewServiceClient,
        ReviewServiceUnavailable,
    )

    assert len(REVIEW_ALLOWED_ROUTES) == 5
    for _method, path in REVIEW_ALLOWED_ROUTES:
        assert not any(v in path.lower() for v in PROHIBITED_VERBS + ("resume", "signal")), path

    client = ReviewServiceClient("http://review.invalid")
    for method, path in (
        ("POST", "/review/resume"),
        ("POST", "/review/signals"),
        ("POST", "/review/approvals/{approval_id}/grant"),
    ):
        with pytest.raises(ReviewServiceUnavailable):
            client._request(method, path)  # noqa: SLF001
