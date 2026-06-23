#!/usr/bin/env python3
"""derive_weak_labels.py — WEAK heuristic Guna/Vritti labels from prompt+response (+ optional ground truth).
Pre-reg: docs/CG_GUNA_VRITTI_LABEL_SOURCE_PREREG.md §5. CPU-only, deterministic, torch-free.

WEAK by design: labels are derived from TRANSPARENT SURFACE CUES of the text (the same cues the surface
baseline measures), NEVER from hidden states. Therefore a probe trained on these labels is expected to be
SURFACE_CONFOUNDED and CANNOT support a `LEARNS_SIGNAL` claim — these labels are for PLUMBING and a weak
upper bound only (-> CG_GUNA_VRITTI_SYNTHETIC_ONLY / LABELS_USABLE_WEAK_ONLY). Guna dims 4-6 stay null
(underdefined in the source docs). Bhava is NOT labelled.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))
from conscious_generation_training.surface_baseline import surface_features   # noqa: E402

_RECALL = ("earlier", "you mentioned", "you said", "previously", "as i said", "before,", "last time",
           "you asked", "we discussed")
_HEDGE_TAMAS = 0.03           # hedge density above this -> tamas
_MIN_WORDS = 8                # below this -> nidra (non-answer) / tamas


def _contains_false_claim(response: str, false_claims) -> bool:
    r = response.lower()
    return any(fc and fc.lower() in r for fc in (false_claims or []))


def derive_vritti(prompt: str, response: str, *, false_claims: Optional[List[str]] = None,
                  ground_truth_available: bool = False) -> str:
    """nidra > viparyaya(GT) > vikalpa > smriti > pramana. viparyaya only when ground truth is available."""
    f = surface_features(prompt, response)
    wc = len((response or "").split())
    if wc < _MIN_WORDS or f["refusal_density"] > 0:
        return "nidra"                                       # empty / evasive / refusal
    if ground_truth_available and _contains_false_claim(response, false_claims):
        return "viparyaya"                                   # contradicts ground truth
    if f["speculation_density"] > 0:
        return "vikalpa"                                     # speculative / hypothetical
    if any(m in (" " + (response or "").lower() + " ") for m in _RECALL):
        return "smriti"                                      # recalls prior context
    return "pramana"                                         # default: grounded assertion


def derive_guna(prompt: str, response: str) -> List[Optional[int]]:
    """[sattva, rajas, tamas, null, null, null] — multi-label 0/1; dims 4-6 underdefined -> null."""
    f = surface_features(prompt, response)
    wc = len((response or "").split())
    tamas = int(f["hedge_density"] >= _HEDGE_TAMAS or f["refusal_density"] > 0 or wc < _MIN_WORDS)
    rajas = int(f["imperative_density"] > 0 or f["list_markers"] >= 2)
    sattva = int(tamas == 0 and wc >= _MIN_WORDS and f["sentence_count"] >= 1)
    return [sattva, rajas, tamas, None, None, None]


def derive_row(row: dict) -> dict:
    """Add weak labels + label_meta to a {prompt, response, [false_claims]} row. Never reads hidden states."""
    prompt, response = row.get("prompt", ""), row.get("response", "")
    gt_available = bool(row.get("ground_truth_available") or row.get("false_claims") is not None)
    vritti = derive_vritti(prompt, response, false_claims=row.get("false_claims"),
                           ground_truth_available=gt_available)
    guna = derive_guna(prompt, response)
    out = dict(row)
    out["labels"] = {"vritti": vritti, "guna": guna}
    out["label_meta"] = {"source": "weak_heuristic", "guna_labelled_dims": ["sattva", "rajas", "tamas"],
                         "ground_truth_available": gt_available,
                         "derived_from": "prompt+response+ground_truth (NEVER hidden states)",
                         "WARNING": "weak/surface-derivable labels — plumbing + weak upper bound ONLY; "
                                    "cannot validate a LEARNS_SIGNAL claim (see label-source pre-reg)"}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Derive WEAK Guna/Vritti labels (plumbing only, not validation).")
    ap.add_argument("--in", dest="inp", required=True, help="JSONL with prompt/response rows")
    ap.add_argument("--out", required=True, help="JSONL with weak labels added")
    args = ap.parse_args(argv)
    rows = [json.loads(l) for l in Path(args.inp).read_text().splitlines() if l.strip()]
    labelled = [derive_row(r) for r in rows]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for r in labelled:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    from collections import Counter
    vd = Counter(r["labels"]["vritti"] for r in labelled)
    print(f"derived WEAK labels for {len(labelled)} rows -> {args.out}")
    print(f"  vritti dist: {dict(vd)}   (source=weak_heuristic; NOT validation — see label-source pre-reg)")
    print("  reminder: weak labels are surface-derivable -> probe capped at SYNTHETIC_ONLY/WEAK_ONLY.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
