"""Test-only fixture helper: SYNTHETIC credential-shaped strings, assembled at runtime.

Every value here is built from fragments that individually match no credential
detector, so no complete credential-shaped literal exists in any tracked file. The
assembled strings are nonsense (alphabets, repeated characters, counting digits): they
are shapes for the negative tests, never credentials. ``expected_family`` names the
production detector's prefix family each shape must trigger, so a test can prove the
runtime-assembled value takes the same detection path a real one would.
"""

from __future__ import annotations

_LOWER = "abcdefghijklmnopqrstuvwxyz"
_UPPER = _LOWER.upper()
_DIGITS = "0123456789"


def _join(*fragments: str) -> str:
    return "".join(fragments)


#: kind -> (assembled synthetic value, the production prefix family it must trigger)
def synthetic_credential_shape(kind: str) -> str:
    return _SHAPES[kind]()


def expected_family(kind: str) -> str:
    return _FAMILIES[kind]


_SHAPES = {
    "openai_project_key": lambda: _join("sk", "-", "proj", "-", _LOWER, _DIGITS),
    "openai_service_account_key": lambda: _join("sk", "-", "svcacct", "-", _UPPER),
    "jwt": lambda: _join("ey", "JhbGciOiJIUzI1NiJ9", ".", "ey", "JzdWIiOiJtZXUifQ", ".", "c2lnbmF0dXJlLXNpZ25hdHVyZQ"),
    "google_api_key": lambda: _join("AI", "za", "SyA", _DIGITS, _LOWER[:21]),
    "google_oauth_token": lambda: _join("ya", "29", ".", "a0AfH6SMB", "x" * 20),
    "private_key_block": lambda: _join("-----", "BEGIN ", "PRIVATE", " KEY-----", "\n", "MIIE"),
    "embedded_openai_key": lambda: _join("evidence://x?token=", "sk", "-", _LOWER[:16]),
}

_FAMILIES = {
    "openai_project_key": _join("sk", "-", "proj", "-"),
    "openai_service_account_key": _join("sk", "-", "svcacct", "-"),
    "jwt": _join("ey", "J"),
    "google_api_key": _join("AI", "za"),
    "google_oauth_token": _join("ya", "29", "."),
    "private_key_block": _join("-----", "BEGIN"),
    "embedded_openai_key": _join("sk", "-"),
}

KINDS = tuple(_SHAPES)
