"""OpenAPI contract tests for the secure chat surface (Phase 3A).

Asserts the bounded chat route set, that the client message id is required, that the
cursor is an opaque string, that no message body appears in the conversation summary,
tombstone semantics, that no forbidden (Guna/compatibility/AI) route leaks in, and
that the existing Phase 1 routes are unchanged. Also checks the committed generated
OpenAPI artifact stays in sync (contract-drift guard).
"""

from __future__ import annotations

import json
import pathlib

from ugence_dilchat.app import create_app
from ugence_dilchat.config import Environment, Settings
from ugence_dilchat.scripts_openapi import build_openapi

_PRODUCT_ROOT = pathlib.Path(__file__).resolve().parents[2]
_GENERATED = _PRODUCT_ROOT / "docs" / "openapi" / "dilchat.generated.openapi.json"

_CHAT_PATHS = {
    "/v1/conversations/current": {"get"},
    "/v1/conversations/{conversation_id}/messages": {"get", "post"},
    "/v1/conversations/{conversation_id}/messages/{message_id}": {"delete"},
    "/v1/conversations/{conversation_id}/read-state": {"put"},
}
_PHASE1_PATHS = [
    "/v1/auth/register",
    "/v1/auth/login",
    "/v1/couples/invitations",
    "/v1/couples/current",
    "/v1/birth-profiles",
]
_BANNED = ("guna", "compatibility", "kundli", "milan", "ashtakoot", "koota", "kuta",
           "dosha", "matchmak", "moon-receptivity", "ai-assist", "friends-finder")


def _spec() -> dict:
    app = create_app(Settings(environment=Environment.TEST, database_url="sqlite+aiosqlite://"))
    return app.openapi()


def test_chat_routes_present_with_expected_methods():
    paths = _spec()["paths"]
    for path, methods in _CHAT_PATHS.items():
        assert path in paths, path
        assert methods <= set(paths[path]), (path, paths[path].keys())


def test_client_message_id_is_required():
    schema = _spec()["components"]["schemas"]["MessageCreateRequest"]
    assert "client_message_id" in schema["required"]
    assert "body" in schema["required"]


def test_cursor_is_opaque_string_query():
    op = _spec()["paths"]["/v1/conversations/{conversation_id}/messages"]["get"]
    params = {p["name"]: p for p in op["parameters"]}
    cursor_schema = params["cursor"]["schema"]
    cursor_type = cursor_schema.get("anyOf", [{}])[0].get("type", "string")
    assert cursor_type in ("string", None)
    # limit is bounded in the contract.
    limit_schema = params["limit"]["schema"]
    flat = json.dumps(limit_schema)
    assert "100" in flat and "1" in flat


def test_conversation_summary_has_no_message_body():
    schema = _spec()["components"]["schemas"]["ConversationResponse"]
    assert "body" not in schema["properties"]
    assert set(schema["required"]) >= {"conversation_id", "couple_id", "status"}


def test_message_response_body_is_nullable_for_tombstones():
    schema = _spec()["components"]["schemas"]["MessageResponse"]
    body = schema["properties"]["body"]
    assert "anyOf" in body and {"type": "null"} in body["anyOf"]
    assert "deleted" in schema["properties"]


def test_no_forbidden_routes_or_schemas():
    spec = _spec()
    blob = json.dumps(
        {"paths": list(spec["paths"]), "schemas": list(spec["components"]["schemas"])}
    ).lower()
    for term in _BANNED:
        assert term not in blob, term


def test_phase1_routes_unchanged():
    paths = _spec()["paths"]
    for p in _PHASE1_PATHS:
        assert p in paths, p


def test_generated_openapi_artifact_is_in_sync():
    # The committed generated artifact must match the live spec (regenerate with
    # `python -m ugence_dilchat.scripts_openapi docs/openapi/dilchat.generated.openapi.json`).
    live = json.dumps(build_openapi(), indent=2, sort_keys=True)
    committed = _GENERATED.read_text()
    assert live.strip() == committed.strip(), (
        "generated OpenAPI artifact is stale; regenerate it (see scripts_openapi)."
    )
