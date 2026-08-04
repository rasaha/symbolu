"""Centralized secret redaction for the shadow-validation harness.

No token, credential, certificate, private key, secret-bearing header, or sensitive
URL query parameter may appear in any log, audit event, request ledger, exception,
shadow decision, evidence file, CLI output, or verification report. All harness output
paths funnel through the helpers here.

These build on the operations package's :func:`ugence_cloud_scaling_operations.audit.redact`
(keys + inline ``Bearer`` tokens) and add URL, header, and exception redaction.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from ugence_cloud_scaling_operations.audit import redact as _redact_keys

REDACTED = "<redacted>"

# Keys whose values must never be persisted verbatim.
_SECRET_KEY_RE = re.compile(
    r"(token|secret|password|passwd|authorization|api[-_]?key|private[-_]?key|"
    r"bearer|credential|cookie|session|kubeconfig|client[-_]?cert|signature|"
    r"access[-_]?key|sig)", re.IGNORECASE)

# Inline bearer tokens embedded in free text.
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+")

# Sensitive URL query-parameter names.
_SECRET_QUERY_RE = re.compile(
    r"(token|secret|password|api[-_]?key|access[-_]?token|sig|signature|"
    r"credential|key)", re.IGNORECASE)


def redact_mapping(value: Any) -> Any:
    """Deep-redact a mapping/list/string using the operations key+bearer policy."""
    return _redact_keys(value)


def redact_headers(headers: Mapping[str, Any]) -> Dict[str, str]:
    """Fully redact any secret-bearing header value (Authorization, Cookie, ...)."""
    out: Dict[str, str] = {}
    for k, v in dict(headers or {}).items():
        if _SECRET_KEY_RE.search(str(k)):
            out[str(k)] = REDACTED
        else:
            out[str(k)] = _BEARER_RE.sub(f"Bearer {REDACTED}", str(v))
    return out


def redact_url(url: str) -> str:
    """Strip userinfo and redact secret query-parameter values; keep host/path."""
    if not isinstance(url, str) or not url:
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return REDACTED
    netloc = parts.netloc
    if "@" in netloc:  # strip user:pass@
        netloc = netloc.rsplit("@", 1)[1]
    query = urlencode([
        (k, REDACTED if _SECRET_QUERY_RE.search(k) else v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
    ])
    return urlunsplit((parts.scheme, netloc, parts.path, query, parts.fragment))


def redact_exception(exc: BaseException) -> str:
    """A redacted, single-line string form of an exception message."""
    text = _BEARER_RE.sub(f"Bearer {REDACTED}", str(exc))
    # Redact any URL-looking token in the message.
    text = re.sub(r"https?://[^\s'\"]+", lambda m: redact_url(m.group(0)), text)
    return text


def redact_record(record: Any) -> Any:
    """Deep redaction for arbitrary evidence records (mappings, lists, strings)."""
    if isinstance(record, Mapping):
        return {
            str(k): (REDACTED if _SECRET_KEY_RE.search(str(k)) else redact_record(v))
            for k, v in record.items()
        }
    if isinstance(record, (list, tuple)):
        return [redact_record(v) for v in record]
    if isinstance(record, str):
        s = _BEARER_RE.sub(f"Bearer {REDACTED}", record)
        s = re.sub(r"https?://[^\s'\"]+", lambda m: redact_url(m.group(0)), s)
        return s
    return record


def contains_secret_material(blob: str) -> bool:
    """Best-effort scan used by tests/verifier: True if obvious secrets survive."""
    if not isinstance(blob, str):
        blob = str(blob)
    if _BEARER_RE.search(blob):
        # A surviving 'Bearer <token>' (not the redacted placeholder) is a leak.
        for m in _BEARER_RE.finditer(blob):
            if REDACTED not in m.group(0):
                return True
    return False


__all__ = [
    "REDACTED",
    "redact_mapping",
    "redact_headers",
    "redact_url",
    "redact_exception",
    "redact_record",
    "contains_secret_material",
]
