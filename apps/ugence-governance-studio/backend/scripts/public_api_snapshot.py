"""Generate / verify the frozen public Python API snapshot (§25).

    python scripts/public_api_snapshot.py           # verify committed snapshot
    python scripts/public_api_snapshot.py --write     # (re)generate

The snapshot is the sorted ``__all__`` of the package plus a sha256 over that
list, so an accidental addition/removal of a public name is caught in CI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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

import ugence_governance_studio_api as pkg  # noqa: E402

SNAPSHOT_PATH = os.path.join(_BACKEND, "artifacts", "public_api.json")


def snapshot() -> dict:
    names = sorted(pkg.__all__)
    digest = hashlib.sha256(json.dumps(names, sort_keys=True).encode()).hexdigest()
    return {"public_api_version": pkg.API_CONTRACT_VERSION, "count": len(names),
            "names": names, "sha256": digest}


def _canonical(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=2) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    snap = snapshot()

    if args.write:
        os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
        with open(SNAPSHOT_PATH, "wb") as fh:
            fh.write(_canonical(snap))
        print(f"wrote {SNAPSHOT_PATH} ({snap['count']} names, sha256 {snap['sha256']})")
        return 0

    if not os.path.isfile(SNAPSHOT_PATH):
        print(f"PUBLIC API DRIFT: missing {SNAPSHOT_PATH}", file=sys.stderr)
        return 1
    with open(SNAPSHOT_PATH, "rb") as fh:
        committed = fh.read()
    if committed != _canonical(snap):
        print("PUBLIC API DRIFT: public surface differs from committed snapshot", file=sys.stderr)
        return 1
    print(f"public API in sync ({snap['count']} names, sha256 {snap['sha256']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
