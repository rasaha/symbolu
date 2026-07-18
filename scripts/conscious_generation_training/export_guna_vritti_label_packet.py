#!/usr/bin/env python3
"""Export a DE-BIASED human-labeling packet for Guna/Vritti. Pre-reg:
docs/CG_GUNA_VRITTI_HUMAN_LABELING_PREREG.md.

Raters see ONLY {item_id, prompt, response, reference?, human_labels}. Every Guna/Vritti construct word,
weak/auto label, source, model id, and answer key is stripped (hard-fail if any leaks). Opaque ids +
deterministic shuffle; a private analyst-only keymap maps opaque_id -> source_id (+ any weak label kept
for later concordance, never given to raters). No jargon; Bhava/Kosha not labelled.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

LABEL_FIELDS = ("response_kind", "clear_and_lucid", "energetic_actionable",
                "dull_confusing_lowsignal", "clarity_1to5", "short_reason")
PUBLIC_ROW_KEYS = ("item_id", "prompt", "response", "reference", "human_labels")
CSV_COLUMNS = ("item_id", *LABEL_FIELDS)
RESPONSE_KINDS = ("grounded_factual", "factually_wrong", "speculative_imaginative",
                  "evasive_nonanswer", "recall_of_context")

# any of these as a key anywhere in a rater row = hard fail (raters must not see the theory or sources)
FORBIDDEN_KEYS = frozenset({
    "guna", "vritti", "sattva", "rajas", "tamas", "velocity", "accel", "stable",
    "pramana", "viparyaya", "vikalpa", "nidra", "smriti", "kosha", "bhava",
    "labels", "label_meta", "weak", "weak_heuristic", "source", "ground_truth", "false_claims",
    "correct", "model", "hidden", "hidden_state", "sovereign", "metadata", "guna_scores", "vritti_probs",
})


def _new_labels():
    return {f: None for f in LABEL_FIELDS}


def build_packet(rows, *, seed=1234):
    """rows: [{id, prompt, response, [reference]}]. Returns (public_rows, keymap). Fails loud on missing
    prompt/response. Opaque ids; reference passed through only if present (for the factually_wrong call)."""
    rng = random.Random(seed)
    units = []
    for r in sorted(rows, key=lambda x: str(x.get("id", ""))):
        sid = r.get("id")
        if sid is None:
            raise KeyError("row missing 'id'")
        prompt, response = r.get("prompt"), r.get("response")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"{sid}: missing/empty prompt")
        if not isinstance(response, str) or not response.strip():
            raise ValueError(f"{sid}: missing/empty response")
        # weak label (if present) is kept ONLY in the private keymap, for later concordance
        weak = (r.get("labels") or {}) if isinstance(r.get("labels"), dict) else {}
        units.append((sid, prompt, response, r.get("reference"), weak))

    seen, oids = set(), []
    for _ in units:
        while True:
            o = format(rng.getrandbits(48), "012x")
            if o not in seen:
                seen.add(o); oids.append(o); break

    public, keymap = [], {}
    for idx, ((sid, prompt, response, ref, weak), oid) in enumerate(zip(units, oids)):
        row = {"item_id": oid, "prompt": prompt, "response": response, "human_labels": _new_labels()}
        if ref:
            row["reference"] = ref
        public.append(row)
        keymap[oid] = {"source_id": sid, "trace_index": idx, "weak_label_for_concordance": weak or None}
    random.Random(seed + 1).shuffle(public)
    return public, keymap


def _scan_forbidden(obj, path=""):
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


def assert_no_forbidden_fields(public_rows):
    for row in public_rows:
        if not set(row).issubset(set(PUBLIC_ROW_KEYS)):
            raise AssertionError(f"row keys {sorted(row)} exceed allowed {sorted(PUBLIC_ROW_KEYS)}")
        if set(row["human_labels"]) != set(LABEL_FIELDS):
            raise AssertionError("human_labels schema does not match the pre-registration")
        leaks = _scan_forbidden(row)
        if leaks:
            raise AssertionError(f"FORBIDDEN FIELD LEAK in rater packet: {leaks}")


def write_outputs(public_rows, keymap, out_dir: Path, prefix="guna_vritti"):
    out_dir.mkdir(parents=True, exist_ok=True)
    packet = out_dir / f"{prefix}_label_packet.jsonl"
    template = out_dir / f"{prefix}_labels_template.csv"
    private = out_dir / f"{prefix}_private_keymap.json"
    with open(packet, "w", encoding="utf-8") as fh:
        for r in public_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(template, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(CSV_COLUMNS))
        w.writeheader()
        for r in public_rows:
            w.writerow({"item_id": r["item_id"], **{f: "" for f in LABEL_FIELDS}})
    private.write_text(json.dumps(keymap, indent=2, ensure_ascii=False), encoding="utf-8")
    return packet, template, private


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export a de-biased Guna/Vritti human-labeling packet.")
    ap.add_argument("--in", dest="inp", required=True, help="JSONL of {id, prompt, response, [reference]}")
    ap.add_argument("--out-dir", default="runs/cg_training/guna_vritti_labeling")
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args(argv)

    rows = [json.loads(l) for l in Path(args.inp).read_text().splitlines() if l.strip()]
    public, keymap = build_packet(rows, seed=args.seed)
    assert_no_forbidden_fields(public)                       # hard gate before writing
    packet, template, private = write_outputs(public, keymap, Path(args.out_dir))
    print(f"rows={len(public)}  packet={packet}")
    print(f"  template={template}\n  keymap={private}  (ANALYST ONLY — do not give to raters)")
    print("  forbidden-field leakage check: PASS  (no Guna/Vritti jargon, no weak label, no source)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
