#!/usr/bin/env python3
"""Export a DE-BIASED human-labeling packet from the Phase 2B-v2 traces (SUPERVISED OBSERVATION track).

Design/justification: docs/CSR_SUPERVISED_OBSERVATION_PREREG.md (Deliverables 1-3, 6).

Joins the real-Mistral robustness traces (`robustness_eval_v2.json`) with the eval-data prompts
(`framed_answer_eval_v2_rubricv2.jsonl`) by item id and emits ONE rater-facing row per (item, arm) =
110 x 2 = 220 rows. Every automated label, system score, answer key, and arm marker is stripped; the
public row carries only {item_id, prompt, answer, intended_task, human_labels}. Arm/source are kept ONLY
in a private analyst keymap. Rows are shuffled deterministically.

This is EXPORT ONLY. No evaluator, no policy, no runtime behavior. The evaluator
(`eval_supervised_observation.py`) is built only after human labels exist.

Outputs:
  supervised_observation_packet.jsonl          (rater-facing; no leakage)
  supervised_observation_labels_template.csv   (rater-facing; item_id + label columns)
  supervised_observation_private_keymap.json   (ANALYST ONLY; opaque_id -> source_id/arm/...)
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

# ---- pre-registered schema (must match docs/CSR_SUPERVISED_OBSERVATION_PREREG.md exactly) ---------
LABEL_FIELDS = (
    "rewrite_needed",
    "answer_acceptable",
    "primary_frame_correct",
    "rejected_domain_leak",
    "secondary_overpromoted",
    "generic_low_signal",
    "clear_and_useful_1to5",
    "factual_or_grounded_1to5",
    "overconfident_or_overstated",
    "frame_label_parroting",
    "needs_clarification",
    "short_reason",
)
PUBLIC_ROW_KEYS = ("item_id", "prompt", "answer", "intended_task", "human_labels")
CSV_COLUMNS = ("item_id", *LABEL_FIELDS)
DEFAULT_INTENDED_TASK = "Answer the user's question accurately and naturally."
DEFAULT_ARMS = ("base", "framed")

# Any of these appearing as a key anywhere in a public row is a hard failure (raters must not see them).
FORBIDDEN_KEYS = frozenset({
    "arm", "base", "framed",
    "expected_primary", "expected_secondary", "expected_rejected",
    "expected_secondary_true_senses", "candidate_domains",
    "must_include", "may_include", "must_not_include", "false_claims",
    "scores", "reasons", "rubric_target", "rubric_version",
    "primary_frame_correct_score", "rejected_domain_avoidance", "secondary_handling_correct",
    "phoneme_overreach", "factuality_preserved", "clarity_score", "must_include_recall",
    "must_not_violation_rate", "secondary_promoted",
    "finding_types", "needs_rewrite", "audit", "audit_findings",
    "match", "match_primary", "csr", "c_score", "r_score", "s_score",
    "csr_policy", "policy_risk",
    "derivedvrittitrajectory", "trajectory", "trajectory_mode", "traj_drift",
    "gunaqualitydiagnostic", "guna", "guna_quality",
    "backend", "llm_backend", "model", "production_valid", "polysemy_ok", "robust",
    "source_id", "trace_index", "category",
})


def _new_labels() -> dict:
    return {f: None for f in LABEL_FIELDS}


# ---- loading -------------------------------------------------------------------------------------
def select_backend(data: dict, backend: str | None = None) -> str:
    """Pick the trace backend. Prefer an explicit name, else a production_valid backend, else the sole key."""
    traces = data.get("traces") or {}
    if not traces:
        raise ValueError("traces file has no 'traces' section")
    if backend is not None:
        if backend not in traces:
            raise ValueError(f"backend {backend!r} not in traces (have {sorted(traces)})")
        return backend
    backends = data.get("backends") or {}
    valid = [k for k in traces if backends.get(k, {}).get("production_valid")]
    if len(valid) == 1:
        return valid[0]
    if len(traces) == 1:
        return next(iter(traces))
    raise ValueError(
        f"ambiguous backend (production_valid={valid}, all={sorted(traces)}); pass --backend")


def load_prompts(eval_data_path: str | Path) -> dict[str, str]:
    """id -> prompt (the user's `query`). Only the prompt is taken; the answer key is never read here."""
    prompts: dict[str, str] = {}
    with open(eval_data_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            prompts[rec["id"]] = rec["query"]
    if not prompts:
        raise ValueError(f"no prompts loaded from {eval_data_path}")
    return prompts


# ---- packet build --------------------------------------------------------------------------------
def build_packet(items, prompts, *, arms=DEFAULT_ARMS, seed=1234, intended_task=DEFAULT_INTENDED_TASK):
    """Return (public_rows, keymap). Raises loudly on a missing prompt join or missing/empty answer."""
    rng = random.Random(seed)

    # deterministic source order (sorted) so opaque-id assignment is reproducible regardless of file order
    units = []
    for it in sorted(items, key=lambda t: str(t["id"])):
        sid = it["id"]
        if sid not in prompts:
            raise KeyError(f"no prompt join for source id {sid!r} (eval-data missing this id)")
        answers = it.get("answers") or {}
        for arm in arms:
            if arm not in answers:
                raise KeyError(f"item {sid!r} missing answer for arm {arm!r}")
            ans = answers[arm]
            if not isinstance(ans, str) or not ans.strip():
                raise ValueError(f"item {sid!r} arm {arm!r} has empty/non-string answer")
            units.append((sid, arm, it.get("category"), prompts[sid], ans))

    # unique opaque ids (pure hex; cannot contain a source id or 'base'/'framed')
    seen: set[str] = set()
    oids: list[str] = []
    for _ in units:
        while True:
            oid = format(rng.getrandbits(48), "012x")
            if oid not in seen:
                seen.add(oid)
                oids.append(oid)
                break

    public_rows, keymap = [], {}
    for idx, ((sid, arm, cat, prompt, ans), oid) in enumerate(zip(units, oids)):
        public_rows.append({
            "item_id": oid,
            "prompt": prompt,
            "answer": ans,
            "intended_task": intended_task,
            "human_labels": _new_labels(),
        })
        keymap[oid] = {"source_id": sid, "arm": arm, "category": cat, "trace_index": idx}

    # deterministic shuffle so arm is not inferable from position (separate stream from id assignment)
    random.Random(seed + 1).shuffle(public_rows)
    return public_rows, keymap


def _scan_forbidden(obj, path="") -> list[str]:
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in FORBIDDEN_KEYS:
                hits.append(f"{path}.{k}")
            hits.extend(_scan_forbidden(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(_scan_forbidden(v, f"{path}[{i}]"))
    return hits


def assert_no_forbidden_fields(public_rows) -> None:
    """Hard-fail if any forbidden key (arm/answer-key/system-score/diagnostic/metadata) leaks into a row."""
    for row in public_rows:
        if set(row) != set(PUBLIC_ROW_KEYS):
            raise AssertionError(f"row keys {sorted(row)} != allowed {sorted(PUBLIC_ROW_KEYS)}")
        if set(row["human_labels"]) != set(LABEL_FIELDS):
            raise AssertionError("human_labels schema does not match pre-registration")
        leaks = _scan_forbidden(row)
        if leaks:
            raise AssertionError(f"FORBIDDEN FIELD LEAK in public packet: {leaks}")


def csv_rows(public_rows):
    return [{"item_id": r["item_id"], **{f: r["human_labels"][f] for f in LABEL_FIELDS}}
            for r in public_rows]


# ---- io ------------------------------------------------------------------------------------------
def write_outputs(public_rows, keymap, out_dir: Path, prefix="supervised_observation"):
    out_dir.mkdir(parents=True, exist_ok=True)
    packet = out_dir / f"{prefix}_packet.jsonl"
    template = out_dir / f"{prefix}_labels_template.csv"
    private = out_dir / f"{prefix}_private_keymap.json"

    with open(packet, "w", encoding="utf-8") as fh:
        for r in public_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(template, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(CSV_COLUMNS))
        w.writeheader()
        for r in csv_rows(public_rows):
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})
    with open(private, "w", encoding="utf-8") as fh:
        json.dump(keymap, fh, indent=2, ensure_ascii=False)
    return packet, template, private


def main(argv=None):
    p = argparse.ArgumentParser(description="Export a de-biased human-labeling packet (export only).")
    p.add_argument("--traces", required=True, help="robustness_eval_v2.json")
    p.add_argument("--eval-data", required=True, help="framed_answer_eval_v2_rubricv2.jsonl")
    p.add_argument("--backend", default=None, help="trace backend key (default: auto)")
    p.add_argument("--out-dir", default=".", help="output directory")
    p.add_argument("--seed", type=int, default=1234)
    args = p.parse_args(argv)

    data = json.load(open(args.traces, encoding="utf-8"))
    backend = select_backend(data, args.backend)
    items = data["traces"][backend]
    prompts = load_prompts(args.eval_data)

    public_rows, keymap = build_packet(items, prompts, seed=args.seed)
    assert_no_forbidden_fields(public_rows)   # hard gate before anything is written
    packet, template, private = write_outputs(public_rows, keymap, Path(args.out_dir))

    print(f"backend={backend}  rows={len(public_rows)} (items={len(items)} x arms={len(DEFAULT_ARMS)})")
    print(f"  packet:   {packet}")
    print(f"  template: {template}")
    print(f"  keymap:   {private}  (ANALYST ONLY — do not give to raters)")
    print("  forbidden-field leakage check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
