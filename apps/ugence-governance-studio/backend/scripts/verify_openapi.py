"""Generate / verify the frozen OpenAPI contract (§24).

    python scripts/verify_openapi.py            # verify committed artifact (drift check)
    python scripts/verify_openapi.py --write     # (re)generate the committed artifact

Exit code 1 on drift. The generated document is deterministic (host-free,
timestamp-free, stable operation and model names).
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
_APP = os.path.dirname(_BACKEND)
_REPO = os.path.dirname(os.path.dirname(_APP))
for _p in (
    os.path.join(_BACKEND, "src"),
    os.path.join(_REPO, "packages", "capabilities", "agent-workforce-composer", "src"),
    os.path.join(_REPO, "packages", "tooling", "policy-workflow-compiler", "src"),
):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from ugence_governance_studio_api.openapi import canonical_openapi_bytes  # noqa: E402

# Frozen contract lives beside the P3A contracts, next to the app.
CONTRACT_PATH = os.path.join(_APP, "contracts", "openapi.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="verify or write the frozen OpenAPI contract")
    parser.add_argument("--write", action="store_true", help="(re)write the committed artifact")
    args = parser.parse_args()

    generated = canonical_openapi_bytes()
    digest = hashlib.sha256(generated).hexdigest()

    if args.write:
        os.makedirs(os.path.dirname(CONTRACT_PATH), exist_ok=True)
        with open(CONTRACT_PATH, "wb") as fh:
            fh.write(generated)
        print(f"wrote {CONTRACT_PATH}\nsha256: {digest}")
        return 0

    if not os.path.isfile(CONTRACT_PATH):
        print(f"OPENAPI DRIFT: missing committed contract {CONTRACT_PATH}", file=sys.stderr)
        return 1
    with open(CONTRACT_PATH, "rb") as fh:
        committed = fh.read()
    if committed != generated:
        print("OPENAPI DRIFT: generated document differs from committed contract", file=sys.stderr)
        print(f"  committed sha256: {hashlib.sha256(committed).hexdigest()}", file=sys.stderr)
        print(f"  generated sha256: {digest}", file=sys.stderr)
        return 1
    print(f"OpenAPI contract in sync (sha256: {digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
