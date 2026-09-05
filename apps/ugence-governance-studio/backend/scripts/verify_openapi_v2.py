"""Generate / verify the frozen v2 OpenAPI contract (GAS-4).

    python scripts/verify_openapi_v2.py            # verify committed artifact
    python scripts/verify_openapi_v2.py --write    # (re)generate it

Deliberately a SEPARATE script and a separate artifact from ``verify_openapi.py``.
The v1 document is generated from ``create_app`` and the v2 document from
``create_v2_app``, so neither can perturb the other and each is frozen on its own.
Exit code 1 on drift.
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
    os.path.join(_REPO, "packages", "integration", "agent-constitution-activation", "src"),
    os.path.join(_REPO, "packages", "integration", "agent-constitution-policy", "src"),
    os.path.join(_REPO, "packages", "integration", "agent-constitution-conformance", "src"),
    os.path.join(_REPO, "packages", "capabilities", "agentic-proposer", "src"),
    os.path.join(_REPO, "packages", "policy-authority", "src"),
    os.path.join(_REPO, "packages", "capabilities", "decision-authority", "src"),
    os.path.join(_REPO, "packages", "runtime", "agent-runtime", "src"),
    os.path.join(_REPO, "packages", "uvi-policy-contracts", "src"),
    os.path.join(_REPO, "packages", "governance-contracts", "src"),
    os.path.join(_REPO, "packages", "jcs", "src"),
):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from ugence_governance_studio_api.openapi_v2 import canonical_v2_openapi_bytes  # noqa: E402

CONTRACT_PATH = os.path.join(_APP, "contracts", "openapi_v2.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="verify or write the frozen v2 OpenAPI contract")
    parser.add_argument("--write", action="store_true", help="(re)write the committed artifact")
    args = parser.parse_args()

    generated = canonical_v2_openapi_bytes()
    digest = hashlib.sha256(generated).hexdigest()

    if args.write:
        os.makedirs(os.path.dirname(CONTRACT_PATH), exist_ok=True)
        with open(CONTRACT_PATH, "wb") as fh:
            fh.write(generated)
        print(f"wrote {CONTRACT_PATH}\nsha256: {digest}")
        return 0

    if not os.path.isfile(CONTRACT_PATH):
        print(f"OPENAPI V2 DRIFT: missing committed contract {CONTRACT_PATH}", file=sys.stderr)
        return 1
    with open(CONTRACT_PATH, "rb") as fh:
        committed = fh.read()
    if committed != generated:
        print("OPENAPI V2 DRIFT: generated document differs from committed contract",
              file=sys.stderr)
        print(f"  committed sha256: {hashlib.sha256(committed).hexdigest()}", file=sys.stderr)
        print(f"  generated sha256: {digest}", file=sys.stderr)
        return 1
    print(f"v2 OpenAPI contract in sync (sha256: {digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
