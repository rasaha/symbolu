"""Test-only fixture helper: SYNTHETIC credential-shaped strings, assembled at runtime.

Every value is built from fragments that individually match no credential detector, so
no complete credential-shaped literal exists in any tracked file. The assembled strings
are nonsense (alphabets, counting digits, repeated characters): shapes for the negative
tests, never credentials.
"""

from __future__ import annotations

_LOWER = "abcdefghijklmnopqrstuvwxyz"
_UPPER = _LOWER.upper()
_DIGITS = "0123456789"


def _join(*fragments: str) -> str:
    return "".join(fragments)


_SHAPES = {
    "openai_project_key": lambda: _join("sk", "-", "proj", "-", _LOWER, _DIGITS[:4]),
    "openai_service_account_key": lambda: _join("sk", "-", "svcacct", "-", _UPPER),
    "google_api_key": lambda: _join("AI", "za", "SyA", _DIGITS, _LOWER[:21]),
    "google_oauth_token": lambda: _join("ya", "29", ".", "a0AfH6SMB", "x" * 20),
    "private_key_block": lambda: _join("-----", "BEGIN ", "PRIVATE", " KEY-----", "\n", "MIIE"),
}

KINDS = tuple(_SHAPES)


def synthetic_credential_shape(kind: str) -> str:
    return _SHAPES[kind]()


def service_account_key_document() -> str:
    """A SYNTHETIC downloaded service-account key document, assembled at runtime."""

    import json
    return json.dumps({
        "type": "service_account",
        "project_id": "ugence-meu-nonprod-4821",
        _join("private", "_key", "_id"): _join(_LOWER[:16], _DIGITS[:4]),
        _join("private", "_key"): _SHAPES["private_key_block"](),
        "client_email": "meu-runtime@ugence-meu-nonprod-4821.iam.gserviceaccount.com",
    })
