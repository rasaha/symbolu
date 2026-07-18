#!/usr/bin/env python3
"""Phase 3 — freeze the raw evaluator evidence. NO model calls. Does NOT load the internal answer key.

Validates completeness (each evaluator has all 720 evaluator-facing trial IDs exactly once), serializes each
evaluator's records deterministically (sorted by trial_id), computes SHA-256 over that canonical form, and writes a
raw-evidence freeze declaration. Scoring refuses to run until this declaration exists and re-verifies. Refuses to
declare a complete freeze on incomplete evidence unless --allow-incomplete with an explicit reason.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import sys

import native_ws_runlib as R

HERE = pathlib.Path(__file__).resolve().parent


def _canonical(records):
    """Deterministic serialization independent of collection/resume order: sort records by trial_id."""
    recs = sorted(records, key=lambda r: r["trial_id"])
    return json.dumps(recs, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _load_records(resp_path):
    out = {}
    with open(resp_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            out[rec["trial_id"]] = rec                          # last write wins (resume-safe)
    return list(out.values())


def freeze(evidence_root, manifest_path, allow_incomplete, reason):
    root = pathlib.Path(evidence_root)
    expected_ids = {t["trial_id"] for t in R.load_trials()}
    man = R.load_manifest(manifest_path)
    per_eval = {}
    all_complete = True
    for e in man["evaluators"]:
        eid = e["evaluator_id"]
        resp = root / eid / "responses.jsonl"
        if not resp.exists():
            per_eval[eid] = {"present": False, "complete": False}
            all_complete = False
            continue
        recs = _load_records(resp)
        ids = {r["trial_id"] for r in recs}
        missing = sorted(expected_ids - ids)
        extra = sorted(ids - expected_ids)
        status_counts = {}
        for r in recs:
            status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
        n_bad = status_counts.get("invalid", 0) + status_counts.get("missing", 0)
        complete = not missing and not extra and len(recs) == len(expected_ids)
        all_complete = all_complete and complete
        rm = root / eid / "run_manifest.json"
        rmj = json.loads(rm.read_text(encoding="utf-8")) if rm.exists() else {}
        per_eval[eid] = {"present": True, "complete": complete, "n_records": len(recs),
                         "n_missing_ids": len(missing), "n_extra_ids": len(extra),
                         "status_counts": status_counts,
                         "missing_invalid_rate": round(n_bad / len(expected_ids), 4),
                         "exceeds_5pct_bad": (n_bad / len(expected_ids)) > 0.05,
                         "model_id": rmj.get("model_id"), "resolved_revision": rmj.get("resolved_revision"),
                         "family": rmj.get("family"),
                         "canonical_sha256": hashlib.sha256(_canonical(recs)).hexdigest()}

    families = sorted({v.get("family") for v in per_eval.values() if v.get("present") and v.get("family")})
    combined = hashlib.sha256("".join(
        per_eval[eid].get("canonical_sha256", "") for eid in sorted(per_eval)).encode()).hexdigest()
    frozen = all_complete or (allow_incomplete and bool(reason))
    decl = {"declaration": "NATIVE_WORD_SPECIFICITY_RAW_EVIDENCE_FREEZE",
            "packet_freeze_commit": "42f38d57", "prerun_audit_commit": "fc15a0d8",
            "n_evaluators": len(per_eval), "distinct_families": families,
            "all_complete": all_complete, "frozen": frozen,
            "allow_incomplete": bool(allow_incomplete), "incomplete_reason": reason or None,
            "per_evaluator": per_eval, "combined_sha256": combined,
            "family_policy_met_ge3_distinct": len(families) >= 3,
            "note": "raw evidence only; NO answer key loaded; NO accuracy computed; scoring must re-verify these hashes"}
    out = root / "raw_evidence_freeze.json"
    R.write_json_atomic(out, decl)
    print(json.dumps({"frozen": frozen, "all_complete": all_complete, "distinct_families": families,
                      "combined_sha256": combined, "declaration_path": str(out)}, indent=2))
    return 0 if frozen else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence-root", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--allow-incomplete", action="store_true")
    ap.add_argument("--reason", default=None)
    a = ap.parse_args()
    if a.allow_incomplete and not a.reason:
        print("--allow-incomplete requires --reason", file=sys.stderr)
        sys.exit(2)
    sys.exit(freeze(a.evidence_root, a.manifest, a.allow_incomplete, a.reason))


if __name__ == "__main__":
    main()
