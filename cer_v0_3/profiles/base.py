"""Profile contract + shared validators for CER V0.3 (original side).

Adds a **secret-material guard** on top of the V0.2 field-presence discipline: a
profile may declare keys/patterns that must never appear in the actuation (raw
credentials, DSNs, connection strings, statement text). This is a fail-closed
check — the CER must carry only non-secret identity (digests, logical names).
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Protocol


class CERValidationError(ValueError):
    """Structurally invalid CER (fail closed)."""


class SecretMaterialError(CERValidationError):
    """The actuation carries something that looks like a secret (fail closed)."""


class Profile(Protocol):
    PROFILE_ID: str
    ACTIONGATE_TOOL: str
    ACTIONGATE_SERVER: str
    ACTIONGATE_OPERATION: str
    REQUIRED_ACTUATION: tuple
    OPTIONAL_ACTUATION: tuple
    PROHIBITED_ACTUATION: tuple

    def validate_actuation(self, actuation: Dict[str, Any]) -> None: ...
    def to_envelope(self, cer: Dict[str, Any]) -> Dict[str, Any]: ...


def _require(d: Dict[str, Any], key: str, ctx: str) -> Any:
    if key not in d or d[key] is None:
        raise CERValidationError(f"missing required field {ctx}.{key}")
    return d[key]


def check_fields(actuation: Dict[str, Any], required, optional, prohibited,
                 profile_id: str) -> None:
    for f in required:
        _require(actuation, f, f"actuation[{profile_id}]")
    for f in prohibited:
        if f in actuation:
            raise CERValidationError(
                f"prohibited field {f!r} present for profile {profile_id} "
                "(possible profile downgrade/confusion)")
    allowed = set(required) | set(optional)
    unknown = set(actuation) - allowed
    if unknown:
        raise CERValidationError(
            f"unknown actuation field(s) for {profile_id}: {sorted(unknown)}")


# Keys that must never appear anywhere in a database actuation, and value patterns
# that look like embedded credentials. Fail closed if seen.
_SECRET_KEYS = {"password", "passwd", "secret", "dsn", "connection_string",
                "conn_string", "credentials", "credential", "token", "api_key",
                "private_key", "statement", "sql", "sql_text", "query_text"}
_SECRET_VALUE_RE = re.compile(
    r"(password\s*=)|(://[^/\s:]+:[^/\s@]+@)|(-----BEGIN [A-Z ]*PRIVATE KEY-----)",
    re.IGNORECASE)


def _walk(value: Any):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _walk(v)


def assert_no_secret_material(actuation: Dict[str, Any], profile_id: str) -> None:
    for k, v in _walk(actuation):
        if isinstance(k, str) and k.lower() in _SECRET_KEYS:
            raise SecretMaterialError(
                f"prohibited secret-bearing key {k!r} in {profile_id} actuation "
                "(CER carries only non-secret identity: digests/logical names)")
        if isinstance(v, str) and _SECRET_VALUE_RE.search(v):
            raise SecretMaterialError(
                f"value under {k!r} looks like embedded credential material "
                f"({profile_id}); fail closed")
