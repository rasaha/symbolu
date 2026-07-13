"""Verify a durable run: completeness + integrity. Fails loudly on problems.

Checks: expected (method,budget,example,task) keys all present; no duplicate keys
with differing prompts; single model revision; single run_kind (no smoke/primary
mixing); stable prompt hashes; and — for a PRIMARY run — that a real model produced
every record (never the mock).
"""

from __future__ import annotations

import json
import sys

import runpod_common as RC

from actiongate_context_ablation import llm_tasks
from actiongate_context_ablation import real_llm_bench as R
from actiongate_context_ablation.corpus import registry
from actiongate_context_ablation import adapter, ablation, milestone_bench as MB, protected_detector as PD


def _expected_keys(config, revision):
    items = registry.load_all()
    if config["contexts_limit"]:
        items = items[: config["contexts_limit"]]
    sp = adapter.default_signed_policy()
    keys = set()
    for method in config["methods"]:
        budgets = [0.0] if method in ("original", "structural_only") else config["budgets"]
        for b in budgets:
            for it in items:
                for task in llm_tasks.build_tasks(it, sp):
                    keys.add(RC.example_key(config["run_id"], revision, method, b,
                                            it.item_id, task["type"]))
    return keys


def verify(config=None) -> dict:
    config = config or RC.load_config()
    problems = []
    recs = RC.read_records(RC.records_path(config))
    cfg_path = RC.config_path(config)
    run_cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
    revision = run_cfg.get("model_revision", "local-unpinned")

    if not recs:
        problems.append("no records found")
        return {"ok": False, "problems": problems, "n_records": 0}

    # single revision / run_kind
    revs = {r["model_revision"] for r in recs}
    kinds = {r["run_kind"] for r in recs}
    if len(revs) > 1:
        problems.append(f"multiple model revisions in one run: {revs}")
    if len(kinds) > 1:
        problems.append(f"smoke/primary records mixed: {kinds}")

    # duplicate keys with differing prompt
    seen = {}
    for r in recs:
        k = r["key"]
        if k in seen and seen[k] != r["prompt_hash"]:
            problems.append(f"duplicate key with differing prompt: {k}")
        seen[k] = r["prompt_hash"]

    # completeness vs expected
    expected = _expected_keys(config, revision)
    got = set(seen)
    missing = expected - got
    extra = got - expected
    if missing:
        problems.append(f"{len(missing)} expected records missing (e.g. {sorted(missing)[:1]})")
    if extra:
        problems.append(f"{len(extra)} unexpected records present")

    # primary run must be a real model
    if config["run_kind"] == RC.RUN_KIND_PRIMARY:
        if not all(r.get("is_real") for r in recs):
            problems.append("PRIMARY run contains non-real (mock) records — invalid")

    # error/status count (informational, not fatal unless all errored)
    errors = [r for r in recs if r.get("status", "OK") != "OK"]
    if errors and len(errors) == len(recs):
        problems.append("every record errored")

    return {"ok": not problems, "problems": problems, "n_records": len(recs),
            "n_missing": len(missing), "n_extra": len(extra), "n_errors": len(errors),
            "run_kind": config["run_kind"], "model_revision": revision,
            "is_real": all(r.get("is_real") for r in recs)}


def main():
    res = verify()
    print(json.dumps(res, indent=2))
    RC.write_json_atomic(RC.run_dir(RC.load_config()) / "verify_report.json", res)
    sys.exit(0 if res["ok"] else 2)


if __name__ == "__main__":
    main()
