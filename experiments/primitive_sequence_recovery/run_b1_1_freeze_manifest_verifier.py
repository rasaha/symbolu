#!/usr/bin/env python3
"""B1.1 freeze-manifest verifier (STUB) — verifies a freeze manifest IF one is supplied. Pure stdlib.

Does NOT create a manifest. NO model / embedding / generation / scoring / judging. Re-hashes every bound
artifact and fails on mismatch (INVALID_POSTHOC guard); checks authorization/status/anchor fields.

    python3 experiments/primitive_sequence_recovery/run_b1_1_freeze_manifest_verifier.py [path/to/b1_1_freeze_manifest.json]
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_MANIFEST = HERE / "b1_1_freeze_manifest.json"


def sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    mpath = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MANIFEST
    if not mpath.exists():
        print(f"[info] no manifest at {mpath} — nothing to verify. "
              "(The freeze manifest is created only at the freeze gate, not here.)")
        print("verifier_status = NO_MANIFEST")
        return

    man = json.loads(mpath.read_text(encoding="utf-8")).get("B1_1_FREEZE_MANIFEST", json.loads(mpath.read_text(encoding="utf-8")))
    bad, checks = [], {}

    # 1. artifact hashes match
    for art in man.get("bound_artifacts", []):
        p = HERE.parents[1] / art["path"] if not (HERE / art["path"]).exists() else HERE / art["path"]
        p = pathlib.Path(art["path"])
        if not p.is_absolute():
            p = (HERE.parents[1] / art["path"]) if (HERE.parents[1] / art["path"]).exists() else (HERE / pathlib.Path(art["path"]).name)
        if not p.exists():
            bad.append(f"missing bound artifact: {art['path']}")
        elif sha256(p) != art.get("sha256"):
            bad.append(f"HASH MISMATCH (INVALID_POSTHOC): {art['path']}")
    checks["hashes_match"] = not bad

    # 2-6. status/authorization/anchors
    checks["generation_not_authorized"] = man.get("generation_authorized", None) is False
    checks["fallback_qualification_present"] = "fallback_qualification" in man
    checks["embedding_gate_status_present"] = "embedding_gate_status" in man
    checks["b1_verdict_anchor"] = man.get("b1_verdict_anchor") == "RANDOM_OR_SCRAMBLED_MATCHES"
    checks["track_b_anchor"] = man.get("track_b_anchor") == "BLOCKED"
    for k, v in checks.items():
        if not v:
            bad.append(f"check failed: {k}")

    status = "MANIFEST_VERIFIED" if not bad else "MANIFEST_INVALID"
    print(f"verifier_status = {status}")
    for b in bad:
        print(f"  PROBLEM: {b}")
    print("(This verifier does not authorize generation and does not freeze anything.)")


if __name__ == "__main__":
    main()
