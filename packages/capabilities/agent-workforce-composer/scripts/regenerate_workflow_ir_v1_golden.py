"""Produce a CANDIDATE golden file for the Workflow IR v1 canonicalization ratchet.

This tool never updates ratified fixtures on its own. By default it writes
``*.candidate.json`` next to the committed golden and prints a diff summary for a
human to review. Overwriting the ratified file requires BOTH ``--write`` and
``--i-reviewed-every-changed-digest``, because a moved digest is a change to what
the compiler and AWC agree ``workflow_ir.v1`` canonicalizes to -- an explicit
compatibility decision (ADR §9), never a refresh.

Usage:
    python scripts/regenerate_workflow_ir_v1_golden.py            # candidate only
    python scripts/regenerate_workflow_ir_v1_golden.py --write \
        --i-reviewed-every-changed-digest                          # ratify
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

GOLDEN = _HERE.parent / "tests" / "fixtures" / "workflow_ir_v1_canonical_golden.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true",
                    help="overwrite the ratified golden file (requires the review flag)")
    ap.add_argument("--i-reviewed-every-changed-digest", action="store_true",
                    dest="reviewed", help="affirm that every moved digest was reviewed")
    args = ap.parse_args()

    from tests._ir_v1_compat_vectors import (  # noqa: E402
        CORPUS_VERSION, PINNED_DIGEST_COMPILER_VERSION, normative_vectors,
    )
    from tests._ir_v1_ratchet_harness import build_golden_payload  # noqa: E402
    from ugence_policy_workflow_compiler.serialization import canonical_json  # noqa: E402

    payload = build_golden_payload(normative_vectors(), canonical_json.dumps,
                                   CORPUS_VERSION, PINNED_DIGEST_COMPILER_VERSION)
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    old = json.loads(GOLDEN.read_text(encoding="utf-8")) if GOLDEN.exists() else {"vectors": {}}
    old_v, new_v = old.get("vectors", {}), payload["vectors"]
    added = sorted(set(new_v) - set(old_v))
    removed = sorted(set(old_v) - set(new_v))
    moved = sorted(k for k in set(new_v) & set(old_v) if new_v[k] != old_v[k])

    print(f"corpus       : {payload['corpus_version']}")
    print(f"vectors      : {len(new_v)}")
    print(f"added        : {added or '-'}")
    print(f"removed      : {removed or '-'}")
    print(f"MOVED DIGESTS: {moved or '-'}")
    for k in moved:
        print(f"  {k}\n    was: {old_v[k]['digest']}\n    now: {new_v[k]['digest']}")

    if args.write and args.reviewed:
        GOLDEN.write_text(rendered, encoding="utf-8")
        print(f"\nRATIFIED -> {GOLDEN}")
        if moved:
            print("A pinned digest moved. Record the compatibility decision in the ADR "
                  "and bump CORPUS_VERSION in the same commit.")
        return 0

    candidate = GOLDEN.with_suffix(".candidate.json")
    candidate.write_text(rendered, encoding="utf-8")
    print(f"\nCANDIDATE -> {candidate}")
    print("Ratified fixture NOT modified. Review, then re-run with --write "
          "--i-reviewed-every-changed-digest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
