#!/usr/bin/env python3
"""AP-3 JWKS probe: public-key evidence for the designated issuer, and nothing else.

    python deployment/governed-runtime-worker/ci/ap3_jwks_probe.py
    python deployment/governed-runtime-worker/ci/ap3_jwks_probe.py --url https://.../certs

Fetches the JWKS endpoint recorded in ``AP3_ENTERPRISE_ISSUER_VALIDATION.json``
(``designation.jwks_trust``, or ``--url``) with the standard library and default TLS
verification, and prints only what section 20.3 lets the record hold: the document's
sha256, and for each key its ``kid``, ``kty``, ``alg`` and ``use``. Key material is
never printed. A symmetric key in the document is reported and the run fails, since
IA-2 permits none. No token is requested, sent or accepted.

Exit 0 with evidence; 2 when the endpoint cannot be reached (egress refused, TLS
failure, HTTP error); 3 when the document is not a JWKS this adapter could use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
RECORD = HERE.parent / "AP3_ENTERPRISE_ISSUER_VALIDATION.json"
MAX_BYTES = 256 * 1024
_URL = re.compile(r"https://\S+/cdn-cgi/access/certs|https://\S+\.json")


def designated_url() -> str:
    record = json.loads(RECORD.read_text(encoding="utf-8"))
    match = _URL.search(record["designation"]["jwks_trust"] or "")
    if not match:
        raise SystemExit("the record names no JWKS URL in designation.jwks_trust")
    return match.group(0)


def probe(url: str, timeout_s: float = 10.0) -> dict:
    request = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_s) as response:  # default TLS verification
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("JWKS exceeds the size ceiling")
    document = json.loads(raw.decode("utf-8"))
    keys = document.get("keys")
    if not isinstance(keys, list) or not keys:
        raise ValueError("document has no 'keys' list")
    evidence = []
    for entry in keys:
        if not isinstance(entry, dict) or not entry.get("kid"):
            raise ValueError("a JWKS entry has no kid")
        if entry.get("kty") == "oct" or "k" in entry:
            raise ValueError(f"symmetric key published under kid {entry['kid']!r}; IA-2 permits none")
        evidence.append({"kid": entry["kid"], "kty": entry.get("kty"), "alg": entry.get("alg"),
                         "use": entry.get("use")})
    return {"jwks_url": url, "document_sha256": hashlib.sha256(raw).hexdigest(), "keys": evidence,
            "note": "public key identifiers only; no key material, token or secret is recorded"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=None, help="override the record's designated JWKS URL")
    args = parser.parse_args(argv)
    url = args.url or designated_url()
    if not url.startswith("https://"):
        print(json.dumps({"outcome": "REFUSED", "reason": "the JWKS URL must be https"}), file=sys.stderr)
        return 3
    try:
        evidence = probe(url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        print(json.dumps({"outcome": "UNREACHABLE", "jwks_url": url, "reason": type(exc).__name__}))
        return 2
    except (ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"outcome": "NOT_A_USABLE_JWKS", "jwks_url": url, "reason": str(exc)}))
        return 3
    print(json.dumps({"outcome": "EVIDENCE", **evidence}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
