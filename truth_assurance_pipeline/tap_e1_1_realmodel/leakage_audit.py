"""
TAP-E1.1 leakage audit (Section: Leakage audit).

Programmatic verification that:
  1. hidden gold labels cannot be reached through the public loader;
  2. the interpreter receives only the input projection (no gold) at inference;
  3. the experiment configuration (gates + prereg) is frozen before hidden execution;
  4. no hidden example appears in the development split;
  5. duplicate / near-duplicate detection passes;
  6. the hidden content-hash lock is unchanged from the frozen value.

Returns a structured report; ``run()`` also returns an overall pass/fail.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Tuple

from truth_assurance_pipeline.tap_e1_1_realmodel import loader
from truth_assurance_pipeline.tap_e1_1_realmodel.corpus_v11 import cases as corpus
from truth_assurance_pipeline.tap_e1_intent.schema import stable_hash

_HERE = os.path.dirname(os.path.abspath(__file__))
_LOCK = os.path.join(_HERE, "experiments", "eval_lock_v11.json")
_PREREG = os.path.join(_HERE, "experiments", "preregistration_v11.json")
_CACHE = os.path.join(_HERE, "cache", "agent_model_outputs.jsonl")


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.lower()).strip()


def _shingles(t: str, n: int = 4) -> set:
    toks = _norm(t).split()
    return {tuple(toks[i:i + n]) for i in range(max(0, len(toks) - n + 1))}


def run() -> Dict[str, object]:
    checks: List[Dict[str, object]] = []

    def add(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    # 1. public loader hides gold
    gold_hidden = True
    try:
        for split in corpus.SPLITS:
            for pub in loader.public_cases(split):
                if set(pub.keys()) != {"case_id", "split", "text", "conversation", "metadata"}:
                    gold_hidden = False
    except AssertionError:
        gold_hidden = False
    add("hidden_gold_not_in_public_projection", gold_hidden,
        "public_cases exposes only input keys")

    # 2. inference input carries no gold
    reqs = loader.public_requests("eval")
    no_gold_attr = all(not hasattr(r, "gold") for r in reqs)
    add("inference_input_has_no_gold", no_gold_attr,
        "RawUserRequest built from public projection has no gold attribute")

    # 3. config frozen before hidden execution
    frozen = os.path.exists(_LOCK) and os.path.exists(_PREREG)
    add("experiment_config_frozen", frozen,
        f"lock={os.path.exists(_LOCK)} prereg={os.path.exists(_PREREG)}")

    # 4. no hidden example in dev (by id and by text)
    dev_ids = {c.case_id for c in corpus.cases_for_split("dev")}
    eval_ids = {c.case_id for c in corpus.cases_for_split("eval")}
    dev_texts = {_norm(c.text) for c in corpus.cases_for_split("dev")}
    eval_texts = {_norm(c.text) for c in corpus.cases_for_split("eval")}
    id_overlap = dev_ids & eval_ids
    text_overlap = dev_texts & eval_texts
    add("no_hidden_case_in_dev", not id_overlap and not text_overlap,
        f"id_overlap={sorted(id_overlap)} text_overlap={len(text_overlap)}")

    # 5. duplicate / near-duplicate detection across the whole corpus
    exact = {}
    dup = []
    for c in corpus.ALL_CASES:
        k = _norm(c.text)
        if k in exact:
            dup.append((exact[k], c.case_id))
        exact[k] = c.case_id
    near = []
    cases = list(corpus.ALL_CASES)
    sh = {c.case_id: _shingles(c.text) for c in cases}
    for i in range(len(cases)):
        for j in range(i + 1, len(cases)):
            a, b = cases[i], cases[j]
            if a.split == "dev" and b.split == "eval" or a.split == "eval" and b.split == "dev":
                inter = sh[a.case_id] & sh[b.case_id]
                if inter and len(inter) >= 3:
                    near.append((a.case_id, b.case_id, len(inter)))
    add("no_duplicates", not dup, f"exact_dups={dup}")
    add("no_near_duplicates_dev_eval", not near, f"near={near}")

    # 6. hidden content-hash lock unchanged
    lock_ok = False
    detail = "lock file missing"
    if os.path.exists(_LOCK):
        with open(_LOCK) as fh:
            frozen_lock = json.load(fh)
        live = corpus.eval_lock()
        lock_ok = (live == frozen_lock["eval_lock"])
        # cache hash unchanged too
        cache_ok = True
        if os.path.exists(_CACHE):
            with open(_CACHE) as fh:
                cache_ok = stable_hash(fh.read()) == frozen_lock.get("agent_cache_hash")
        lock_ok = lock_ok and cache_ok
        detail = f"eval_lock_match={live == frozen_lock['eval_lock']} cache_match={cache_ok}"
    add("hidden_content_hash_unchanged", lock_ok, detail)

    all_pass = all(c["pass"] for c in checks)
    return {"all_pass": all_pass, "checks": checks}


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(run(), indent=2))
