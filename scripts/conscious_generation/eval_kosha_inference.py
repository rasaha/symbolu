#!/usr/bin/env python3
"""Deterministic evaluation of the Kosha depth/readiness SELECTOR (not generation). CPU-only.
Doc: docs/KOSHA_INFERENCE_LAYER.md. Scores select_kosha_depth() against a small labelled set; the layer
is experimental and NOT yet validated for quality improvement (selector accuracy ≠ answer-quality gain)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_CSR = Path(__file__).resolve().parent.parent / "cg_wrapper_ablation"
if str(_CSR) not in sys.path:
    sys.path.insert(0, str(_CSR))
from csr_match_filter import kosha as K   # noqa: E402

EVAL_SET = [
    {"query": "What is a doctor? Explain simply.", "expected_level": "annamaya"},
    {"query": "How do I prepare for a doctor appointment?", "expected_level": "pranamaya"},
    {"query": "I am confused and worried about what the doctor said. Can you explain?",
     "expected_level": "manomaya"},
    {"query": "Which is better, a general physician or specialist for this situation?",
     "expected_level": "vijnanamaya"},
    {"query": "Synthesize the deeper meaning of healing and the role of a doctor.",
     "expected_level": "anandamaya"},
    {"query": "Define photosynthesis briefly.", "expected_level": "annamaya"},
    {"query": "Give me step by step instructions to set up a database.", "expected_level": "pranamaya"},
    {"query": "Compare the tradeoffs of microservices vs a monolith.", "expected_level": "vijnanamaya"},
    {"query": "I feel overwhelmed and nervous about this diagnosis.", "expected_level": "manomaya"},
    {"query": "Tie together the big picture principle behind these results.", "expected_level": "anandamaya"},
    # K1.1 mixed-cue cases (primary level by intent; selector also emits a secondary):
    {"query": "How do I set up backups step by step, and should I bother?", "expected_level": "pranamaya"},
    {"query": "Synthesize the big picture and compare the options.", "expected_level": "anandamaya"},
]


def run(eval_set=EVAL_SET) -> dict:
    rows, correct = [], 0
    for ex in eval_set:
        sel = K.select_kosha_depth(ex["query"])
        ok = sel.level.value == ex["expected_level"]
        correct += int(ok)
        rows.append({"query": ex["query"], "expected": ex["expected_level"],
                     "predicted": sel.level.value,
                     "secondary": sel.secondary_level.value if sel.secondary_level else None,
                     "confidence": sel.confidence, "ok": ok,
                     "high_stakes": sel.features["high_stakes"]})
    return {"n": len(eval_set), "accuracy": round(correct / len(eval_set), 4), "rows": rows,
            "note": "selector accuracy only; Kosha is NOT yet validated for answer-quality improvement"}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Evaluate the Kosha depth selector (deterministic).")
    ap.add_argument("--out", default="runs/kosha/kosha_selector_eval.json")
    args = ap.parse_args(argv)
    rep = run()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(rep, indent=2))
    print(f"selector accuracy={rep['accuracy']} (n={rep['n']})  [NOT a quality-improvement claim]")
    for r in rep["rows"]:
        sec = f" +{r['secondary']}" if r["secondary"] else ""
        print(f"  {'OK ' if r['ok'] else 'MISS'} {r['predicted']:<12}{sec:<14} (exp {r['expected']:<12}) {r['query']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
