#!/usr/bin/env python3
"""Phase 2 — evaluator response collection for the native word-specificity run.

Loads ONLY the evaluator-facing trials (never the internal key), runs ONE evaluator model, applies the literal
frozen prompt at temperature 0 with the frozen one-retry / timeout / invalid rules, and records every request, raw
response, parsed choice, error, retry, latency, model id, model revision, and trial id — written incrementally and
atomically so a pod interruption is resumable. NEVER computes accuracy; NEVER prints or stores an answer key.

Official evidence is written under --output-dir and refuses overwrite unless --resume. --dry-run loads the model,
renders a few prompts, validates parsing, and writes to a SEPARATE non-evidence directory.
"""
from __future__ import annotations
import argparse
import json
import pathlib
import sys
import time

import native_ws_runlib as R
import native_ws_model as M

HERE = pathlib.Path(__file__).resolve().parent


def _manifest_entry(manifest_path, evaluator_id):
    man = R.load_manifest(manifest_path)
    for e in man.get("evaluators", []):
        if e["evaluator_id"] == evaluator_id:
            return e
    raise SystemExit(f"evaluator_id {evaluator_id!r} not found in manifest {manifest_path}")


def _load_order(presentation_order, trials_by_id):
    if presentation_order:
        order = json.loads(pathlib.Path(presentation_order).read_text(encoding="utf-8"))["order"]
        missing = [t for t in order if t not in trials_by_id]
        extra = [t for t in trials_by_id if t not in set(order)]
        if missing or extra or len(order) != len(trials_by_id):
            raise SystemExit(f"presentation order mismatch: {len(missing)} missing, {len(extra)} extra")
        return order
    return sorted(trials_by_id)                                # fallback: opaque-id order


def run(args):
    entry = _manifest_entry(args.manifest, args.evaluator_id)
    cfg = M.ModelConfig.from_manifest_entry(entry)
    trials = json.loads(pathlib.Path(args.trials).read_text(encoding="utf-8"))["trials"]
    trials_by_id = {t["trial_id"]: t for t in trials}
    protocol = R.load_protocol()
    order = _load_order(args.presentation_order, trials_by_id)

    if args.dry_run:
        out = pathlib.Path(str(args.output_dir).rstrip("/") + "__DRYRUN_NONEVIDENCE")
        out.mkdir(parents=True, exist_ok=True)
        (out / "NONEVIDENCE_DO_NOT_SCORE.txt").write_text(
            "Dry-run output. NOT official evidence. Never freeze or score this directory.\n", encoding="utf-8")
        ev = M.build_evaluator(cfg, fake_mode=args.fake_mode)
        n = min(args.dry_run_n, len(order))
        recs = []
        for tid in order[:n]:
            rec = R.collect_one(ev, trials_by_id[tid], protocol, args.evaluator_id, cfg.model_id,
                                getattr(ev, "resolved_revision", cfg.revision), settings=None,
                                timeout_s=cfg.timeout_s)
            recs.append(rec.to_json())
        R.write_json_atomic(out / f"{args.evaluator_id}_dryrun.json",
                            {"NONEVIDENCE": True, "evaluator_id": args.evaluator_id,
                             "model_id": cfg.model_id, "resolved_revision": getattr(ev, "resolved_revision", None),
                             "n": n, "parse_ok": sum(r["status"] == "answered" for r in recs),
                             "config": cfg.public_metadata(), "records": recs})
        print(json.dumps({"dry_run": True, "non_evidence_dir": str(out), "rendered": n,
                          "parsed_ok": sum(r["status"] == "answered" for r in recs),
                          "note": "NOT official evidence"}, indent=2))
        return 0

    # ---- official collection ----
    out = pathlib.Path(args.output_dir)
    resp_path = out / "responses.jsonl"
    if resp_path.exists() and not args.resume:
        raise SystemExit(f"REFUSING to overwrite existing evidence at {resp_path}; pass --resume to continue it")
    out.mkdir(parents=True, exist_ok=True)
    completed = R.read_completed_trial_ids(resp_path)
    todo = [t for t in order if t not in completed]

    ev = M.build_evaluator(cfg, fake_mode=args.fake_mode)     # loads the model (or fake)
    resolved_rev = getattr(ev, "resolved_revision", cfg.revision)
    t_start = time.time()
    status_counts = {"answered": 0, "invalid": 0, "missing": 0}
    for i, tid in enumerate(todo):
        rec = R.collect_one(ev, trials_by_id[tid], protocol, args.evaluator_id, cfg.model_id,
                            resolved_rev, settings=None, timeout_s=cfg.timeout_s)
        R.append_jsonl_atomic(resp_path, rec.to_json())        # atomic incremental write
        status_counts[rec.status] = status_counts.get(rec.status, 0) + 1
        if (i + 1) % 50 == 0:
            print(f"[{args.evaluator_id}] {i + 1}/{len(todo)} new (resumed {len(completed)})", flush=True)

    final_completed = R.read_completed_trial_ids(resp_path)
    run_manifest = {"evaluator_id": args.evaluator_id, "model_id": cfg.model_id, "resolved_revision": resolved_rev,
                    "family": cfg.family, "backend": cfg.backend, "runtime_config": cfg.public_metadata(),
                    "presentation_order_file": (pathlib.Path(args.presentation_order).name
                                                if args.presentation_order else None),
                    "n_expected": len(order), "n_completed": len(final_completed),
                    "n_new_this_session": len(todo), "status_counts_this_session": status_counts,
                    "complete": len(final_completed) == len(order),
                    "wall_seconds_this_session": round(time.time() - t_start, 2),
                    "note": "operational counts only; NO accuracy computed; answer key never loaded"}
    R.write_json_atomic(out / "run_manifest.json", run_manifest)
    print(json.dumps({"evaluator_id": args.evaluator_id, "completed": len(final_completed),
                      "expected": len(order), "complete": run_manifest["complete"],
                      "status_counts_this_session": status_counts}, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--evaluator-id", required=True)
    ap.add_argument("--trials", default=str(R.TRIALS_PATH))
    ap.add_argument("--presentation-order", default=None)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--dry-run-n", type=int, default=5)
    ap.add_argument("--fake-mode", default=None,
                    help="offline only: force the fake backend in a mode (valid|invalid|flaky|empty) for smoke/tests")
    sys.exit(run(ap.parse_args()))


if __name__ == "__main__":
    main()
