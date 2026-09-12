"""Test-only fixture helper: SYNTHETIC credential-shaped strings, assembled at runtime.

Every value is built from fragments that individually match no credential detector, so
no complete credential-shaped literal exists in any tracked file. The assembled strings
are nonsense (alphabets, counting digits): shapes for the negative tests, never
credentials. ``expected_family`` names the production prefix family each must trigger.
"""

from __future__ import annotations

_LOWER = "abcdefghijklmnopqrstuvwxyz"
_DIGITS = "0123456789"


def _join(*fragments: str) -> str:
    return "".join(fragments)


_SHAPES = {
    "openai_project_key": lambda: _join("sk", "-", "proj", "-", _LOWER, _DIGITS[:4]),
    "openai_project_key_short": lambda: _join("sk", "-", "proj", "-", _LOWER),
    "google_api_key": lambda: _join("AI", "za", "SyA", _DIGITS, _LOWER[:21]),
}

_FAMILIES = {
    "openai_project_key": _join("sk", "-", "proj", "-"),
    "openai_project_key_short": _join("sk", "-", "proj", "-"),
    "google_api_key": _join("AI", "za"),
}

#: The bare production prefix families the boundary test forbids in source, assembled
#: so that not even a family literal appears in this file.
BOUNDARY_FAMILIES = (_join("sk", "-", "proj", "-"), _join("sk", "-", "svcacct", "-"), _join("AI", "za"),
                     _join("BEGIN", " PRIVATE", " KEY"), _join("ya", "29", "."))

KINDS = tuple(_SHAPES)


def synthetic_credential_shape(kind: str) -> str:
    return _SHAPES[kind]()


def expected_family(kind: str) -> str:
    return _FAMILIES[kind]
