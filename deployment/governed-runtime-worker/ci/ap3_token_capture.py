"""Redacted capture of one Cloudflare Access token, for the AP-3 record (ADR section 20.7).

    python deployment/governed-runtime-worker/ci/ap3_token_capture.py  < (the token on stdin)

Reads exactly one token from standard input, never from an argument or a file name it
would print, and writes to standard output ONLY: the header ``alg``, ``typ`` and
``kid``; the sorted payload key names; ``iss``; ``aud``; whether ``sub`` is non-empty;
``type``; and a SHA-256 fingerprint of the token. The token, its signature, ``sub``,
``email``, ``common_name``, ``identity_nonce`` and every other value are never printed.
Nothing is verified here: this is a capture for the owner to paste into the record,
not validation. Standard library only; no network.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys

#: The only fields the capture may contain. Anything else in the token stays there.
CAPTURE_FIELDS = ("alg", "typ", "kid", "payload_keys", "iss", "aud", "sub_non_empty", "type",
                  "token_sha256", "signature_verified")


def _segment(text: str) -> dict:
    padded = text + "=" * (-len(text) % 4)
    value = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("segment is not a JSON object")
    return value


def capture(token: str) -> dict:
    """The redacted capture of one compact JWS. Raises ValueError if it is not one."""
    token = token.strip()
    parts = token.split(".")
    if len(parts) != 3 or not all(parts):
        raise ValueError("not a compact JWS (three dot-separated segments)")
    header, payload = _segment(parts[0]), _segment(parts[1])
    aud = payload.get("aud")
    sub = payload.get("sub")
    out = {
        "alg": header.get("alg"), "typ": header.get("typ"), "kid": header.get("kid"),
        "payload_keys": sorted(str(k) for k in payload),
        "iss": payload.get("iss"),
        "aud": aud if isinstance(aud, (str, list)) else None,
        "sub_non_empty": isinstance(sub, str) and bool(sub.strip()),
        "type": payload.get("type"),
        "token_sha256": hashlib.sha256(token.encode("ascii", errors="replace")).hexdigest(),
        "signature_verified": False,
    }
    assert tuple(out) == CAPTURE_FIELDS
    return out


def main() -> int:
    if sys.stdin.isatty():
        print(json.dumps({"outcome": "REFUSED", "reason": "pipe the token on standard input; "
                          "never pass it as an argument"}), file=sys.stderr)
        return 2
    raw = sys.stdin.read()
    try:
        result = capture(raw)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        # the message names the failure and never the input
        print(json.dumps({"outcome": "NOT_A_TOKEN", "reason": type(exc).__name__}), file=sys.stderr)
        return 3
    print(json.dumps({"outcome": "REDACTED_CAPTURE", **result}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
