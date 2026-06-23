#!/usr/bin/env python3
"""T1 dataset builder — C×R×S SFT examples for Mistral LoRA, by self-distilling the VALIDATED wrapper.
Pre-registration: docs/CG_TRAINING_CRS_MISTRAL_PREREG.md.

Joins C×R×S eval metadata (term/domains, framed_answer_eval_v2_rubricv2.jsonl) with the real-Mistral
robustness traces (robustness_eval_v2.json: framed-arm answers + rubric scores). Keeps only framed answers
that PASSED (primary_frame_correct ∧ rejected-domain-avoided ∧ factuality_preserved) as `target_answer`,
attaches the C/R/S/MATCH trace, and emits leakage-controlled train/val/test splits grouped by term with
disjoint UNSEEN-TERM and UNSEEN-DOMAIN holdouts.

CPU-SAFE: the real C/R/S/MATCH trace needs embeddings (pod); without them, MATCH fields are marked
unavailable (never faked) and the structural example is still built. `--dry-run` builds a tiny synthetic
set so the pipeline + tests run with no traces and no GPU.

NO Bhava/Guna/Vritti/Kosha fields are emitted (asserted by tests).
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

DECISIONS = (  # mirrors the eval harness; here only ENV/DATA states are reachable at build time
    "CG_TRAINING_INSUFFICIENT_DATA", "CG_TRAINING_ENV_UNAVAILABLE",
)
FORBIDDEN_FIELDS = ("bhava", "guna", "vritti", "kosha", "hidden_state", "sovereign_state")
SLICES = ("high_conf_primary", "ambiguous", "near_miss_secondary", "rejected_trap",
          "unseen_term", "domain_conflict", "negative_control")


def build_prompt(meta: dict) -> str:
    """Frame-constrained instruction prompt (natural, explicit constraints)."""
    pri = "/".join(meta["primary_domain"]) if isinstance(meta["primary_domain"], list) else meta["primary_domain"]
    sec = ", ".join(meta.get("secondary_domains") or []) or "(none)"
    rej = ", ".join(meta.get("rejected_domains") or []) or "(none)"
    return (
        "You are answering within a primary semantic frame.\n\n"
        f"Primary frame: {pri}\n"
        f"Secondary frames: {sec}\n"
        f"Rejected frames: {rej}\n\n"
        "Answer the user's question while staying in the primary frame. Do not promote rejected frames.\n\n"
        f"Question: {meta['query']}"
    )


def make_example(meta: dict, target_answer: str, match_trace: dict, failure_modes: dict,
                 slice_label: str) -> dict:
    ex = {
        "id": meta["id"], "term": meta["term"], "query": meta["query"],
        "primary_domain": meta["primary_domain"], "secondary_domains": meta.get("secondary_domains", []),
        "rejected_domains": meta.get("rejected_domains", []),
        "match_trace": match_trace,                       # {"C","R","S","MATCH","match_available"}
        "prompt": build_prompt(meta), "target_answer": target_answer,
        "failure_modes": failure_modes, "slice": slice_label,
    }
    leaked = [k for k in ex if any(b in k.lower() for b in FORBIDDEN_FIELDS)]
    if leaked:
        raise AssertionError(f"forbidden field(s) in SFT example: {leaked}")
    return ex


# ---- C/R/S/MATCH trace (real engine when embeddings present; marked unavailable otherwise) --------
def crs_trace(term: str, primary_domain, *, adapter=None) -> dict:
    """Real MATCH(term, primary) from the production engine. Without an adapter, S is unavailable -> we
    return match_available=False and do NOT fabricate a MATCH value."""
    import sys
    _CSR = Path(__file__).resolve().parent.parent / "cg_wrapper_ablation"
    if str(_CSR) not in sys.path:
        sys.path.insert(0, str(_CSR))
    from csr_match_filter.match import score_match            # noqa: E402
    from csr_match_filter import registry as R                # noqa: E402
    pri = primary_domain[0] if isinstance(primary_domain, list) else primary_domain
    if pri not in R.DOMAIN_REGISTRY:
        return {"C": None, "R": None, "S": None, "MATCH": None, "match_available": False,
                "note": f"primary domain {pri!r} not in C×R×S registry"}
    if adapter is None:
        return {"C": None, "R": None, "S": None, "MATCH": None, "match_available": False,
                "note": "no semantic backend (embeddings); MATCH not computed"}
    s = score_match(term, pri, adapter)
    return {"C": s.C, "R": s.R, "S": s.S, "MATCH": s.match, "match_available": True}


# ---- leakage-controlled split (grouped by term; disjoint unseen-term / unseen-domain holdouts) ----
def split_examples(examples, *, seed=0, unseen_term_frac=0.2, unseen_domains=None):
    """Return {train, val, test} with NO term across splits and a disjoint unseen-term holdout in test.
    `unseen_domains` (list) are forced into test only (their examples never train)."""
    unseen_domains = set(unseen_domains or [])
    rng = random.Random(seed)
    by_term = {}
    for ex in examples:
        by_term.setdefault(ex["term"], []).append(ex)
    terms = sorted(by_term)
    rng.shuffle(terms)

    def has_unseen_domain(t):
        return any(d in unseen_domains
                   for ex in by_term[t]
                   for d in ([ex["primary_domain"]] if isinstance(ex["primary_domain"], str)
                             else ex["primary_domain"]) + list(ex.get("secondary_domains", [])))

    forced_test = [t for t in terms if has_unseen_domain(t)]
    rest = [t for t in terms if t not in forced_test]
    n_unseen = max(1, int(len(rest) * unseen_term_frac)) if rest else 0
    unseen_terms = set(rest[:n_unseen])
    train_val = rest[n_unseen:]
    n_val = max(1, int(len(train_val) * 0.15)) if train_val else 0
    val_terms = set(train_val[:n_val])
    train_terms = set(train_val[n_val:])

    test_terms = unseen_terms | set(forced_test)
    return {
        "train": [ex for t in train_terms for ex in by_term[t]],
        "val": [ex for t in val_terms for ex in by_term[t]],
        "test": [dict(ex, slice=("unseen_term" if t in unseen_terms else ex["slice"]))
                 for t in test_terms for ex in by_term[t]],
        "_holdout": {"unseen_terms": sorted(unseen_terms), "unseen_domains": sorted(unseen_domains),
                     "forced_test_terms": sorted(forced_test)},
    }


def assert_no_leakage(splits) -> None:
    tr = {ex["term"] for ex in splits["train"]}
    for other in ("val", "test"):
        ov = tr & {ex["term"] for ex in splits[other]}
        if ov:
            raise AssertionError(f"term leakage train∩{other}: {sorted(ov)[:5]}")
    train_targets = {ex["target_answer"] for ex in splits["train"]}
    test_targets = {ex["target_answer"] for ex in splits["test"]}
    if train_targets & test_targets:
        raise AssertionError("target_answer leakage: a test answer appears in train")


# ---- loaders -------------------------------------------------------------------------------------
def _passed(scores: dict) -> bool:
    return bool(scores.get("primary_frame_correct")) and bool(scores.get("rejected_domain_avoidance")) \
        and bool(scores.get("factuality_preserved"))


def build_from_traces(eval_data_path, traces_path, *, adapter=None, arm="framed"):
    by_id = {r["id"]: r for r in
             (json.loads(l) for l in Path(eval_data_path).read_text().splitlines() if l.strip())}
    blob = json.loads(Path(traces_path).read_text())
    tr = blob.get("traces") or {}
    src = next(iter(tr.values())) if isinstance(tr, dict) else tr
    examples = []
    for item in src:
        meta_raw = by_id.get(item["id"])
        if meta_raw is None:
            continue
        ans = (item.get("answers") or {}).get(arm)
        sc = (item.get("scores") or {}).get(arm)
        if not ans or not sc or not _passed(sc):
            continue
        term = (meta_raw.get("dominant_terms") or [meta_raw["id"]])[0]
        meta = {"id": item["id"], "term": term, "query": meta_raw["query"],
                "primary_domain": meta_raw.get("expected_primary", []),
                "secondary_domains": meta_raw.get("expected_secondary", []),
                "rejected_domains": meta_raw.get("expected_rejected", [])}
        fm = {"rejected_domain_leak": not sc.get("rejected_domain_avoidance", True),
              "secondary_overpromoted": bool(sc.get("secondary_promoted", False)),
              "primary_frame_correct": bool(sc.get("primary_frame_correct", False))}
        slice_label = "ambiguous" if meta_raw.get("ambiguity_type", "none") != "none" else "high_conf_primary"
        examples.append(make_example(meta, ans, crs_trace(term, meta["primary_domain"], adapter=adapter),
                                     fm, slice_label))
    return examples


_SYNTH = [
    ("doctor", "Explain what a doctor does.", "medicine", ["care"], ["finance", "law"],
     "A doctor is a trained medical professional who diagnoses, treats, and helps prevent illness."),
    ("apple", "Tell me about apple.", "fruit", ["nature"], ["technology", "finance"],
     "An apple is an edible fruit that grows on apple trees, eaten fresh or used in cooking."),
    ("python", "Tell me about python.", "programming", ["technology"], ["biology", "finance"],
     "Python is a high-level programming language known for readable syntax and broad library support."),
    ("bank", "What is a bank?", "finance", ["commerce"], ["nature", "religion"],
     "A bank is a financial institution that accepts deposits, makes loans, and safeguards money."),
]


def build_dry_run():
    out = []
    for term, q, pri, sec, rej, ans in _SYNTH:
        meta = {"id": f"synth_{term}", "term": term, "query": q,
                "primary_domain": pri, "secondary_domains": sec, "rejected_domains": rej}
        fm = {"rejected_domain_leak": False, "secondary_overpromoted": False, "primary_frame_correct": True}
        out.append(make_example(meta, ans, {"C": None, "R": None, "S": None, "MATCH": None,
                                            "match_available": False, "note": "dry-run synthetic"},
                                fm, "high_conf_primary"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build C×R×S SFT dataset (T1).")
    ap.add_argument("--eval-data", default="scripts/cg_wrapper_ablation/csr_match_filter/eval_data/"
                    "framed_answer_eval_v2_rubricv2.jsonl")
    ap.add_argument("--traces", default=None, help="robustness_eval_v2.json (pod). Omit for --dry-run.")
    ap.add_argument("--out-dir", default="runs/cg_training/crs_sft")
    ap.add_argument("--dry-run", action="store_true", help="tiny synthetic set; no traces/GPU needed")
    ap.add_argument("--unseen-domains", default="", help="comma list forced into test only")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    if args.dry_run or not args.traces:
        examples = build_dry_run()
        note = "dry_run_synthetic"
    else:
        examples = build_from_traces(args.eval_data, args.traces)   # adapter=None on CPU -> MATCH unavailable
        note = "self_distilled_wrapper_passing_framed_answers"
    if len(examples) < 2:
        print("CG_TRAINING_INSUFFICIENT_DATA: <2 examples"); return 1

    splits = split_examples(examples, seed=args.seed,
                            unseen_domains=[d for d in args.unseen_domains.split(",") if d])
    assert_no_leakage(splits)
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    for name in ("train", "val", "test"):
        with open(out / f"{name}.jsonl", "w", encoding="utf-8") as fh:
            for ex in splits[name]:
                fh.write(json.dumps(ex, ensure_ascii=False) + "\n")
    (out / "meta.json").write_text(json.dumps(
        {"source": note, "n_total": len(examples),
         "counts": {k: len(splits[k]) for k in ("train", "val", "test")},
         "holdout": splits["_holdout"], "forbidden_fields_excluded": list(FORBIDDEN_FIELDS)}, indent=2))
    print(f"source={note} n={len(examples)} "
          f"train/val/test={len(splits['train'])}/{len(splits['val'])}/{len(splits['test'])}")
    print(f"wrote {out}/train.jsonl, val.jsonl, test.jsonl, meta.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
