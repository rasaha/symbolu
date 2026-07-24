"""Phase 5 - New dataset (4 partitions), none overlapping prior sets.

  DEVELOPMENT            (>=100)  rule development
  HELD_OUT_NATURAL       (>=250)  new natural artifacts absent from ALL prior sets
  ADVERSARIAL_INVARIANTS (>=75)   cases targeting each structural invariant (honestly synthetic)
  HUMAN_REVIEW_SET       (>=50)   items selected for real human review, balanced across risk/obligation

If insufficient NEW natural artifacts exist, the manifest records NOT_ENOUGH_EVIDENCE with the actual
count rather than fabricating. Gold from the independent rubrics (ground_truth.py). Deterministic.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from typing import Any, Dict, List

from customer_shadow_readiness import data_controls as dc
from minimal_evidence_policy import ground_truth as gt

_PKG = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_PKG)
_OUT = os.path.join(_PKG, "data", "v1")

TARGET_DEV, TARGET_HELDOUT, TARGET_ADVERSARIAL, TARGET_REVIEW = 100, 250, 75, 50
_ROOTS = ["symbolu", "cloud_controller", "simulator", "truth_assurance_pipeline", "ndol", "varna_lens",
          "robotics_reliability_bench", "restoration", "acp", "agent_runtime_v2", "token_compression",
          "sdk", "control_plane", "execution_gate", "execution_proposal_engine", "trading", "trading2",
          "symbolu_bcvf_llm", "symbolu_neural", "quad_generative_regularization", "resonant_model"]
_SKIP = {"__pycache__", ".git", "tests", "node_modules"}
_WORD = re.compile(r"\b\w+\b")


def _quality(t: str) -> bool:
    t = (t or "").strip()
    return len(t) >= 80 and len(_WORD.findall(t)) >= 12 and sum(c.isalpha() for c in t) >= 0.5 * len(t)


def _prior_paths() -> set:
    p = set(a["source_path"] for a in json.load(
        open(os.path.join(_ROOT, "bounded_shadow_pilot/data/natural_pilot_v1/corpus.json")))["artifacts"])
    for part in ("development", "held_out_natural"):
        p |= set(i["source_path"] for i in json.load(
            open(os.path.join(_ROOT, f"evidence_obligation/data/v1/{part}.json"))))
    return p


def _harvest() -> List[Dict[str, Any]]:
    prior = _prior_paths()
    seen: set = set()
    items: List[Dict[str, Any]] = []
    for root in _ROOTS:
        base = os.path.join(_ROOT, root)
        if not os.path.isdir(base):
            continue
        rc = 0
        for dp, dns, fns in os.walk(base):
            dns[:] = sorted(d for d in dns if d not in _SKIP)
            for fn in sorted(fns):
                if rc >= 60:
                    break
                if not fn.endswith((".py", ".md")):
                    continue
                p = os.path.join(dp, fn); rel = os.path.relpath(p, _ROOT)
                if rel in prior:
                    continue
                try:
                    if fn.endswith(".py"):
                        tree = ast.parse(open(p, encoding="utf-8", errors="ignore").read())
                        cands = [("docstring", ast.get_docstring(n)) for n in ast.walk(tree)
                                 if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
                    else:
                        cands = [("doc", open(p, encoding="utf-8", errors="ignore").read()[:2000])]
                except Exception:
                    continue
                for kind, c in cands:
                    if rc >= 60:
                        break
                    if not c or not _quality(c) or not dc.permitted_use(dc.classify(c), "internal"):
                        continue
                    aid = "mep-" + hashlib.sha256((rel + "|" + c).encode()).hexdigest()[:16]
                    if aid in seen:
                        continue
                    seen.add(aid)
                    text = dc.redact(c)
                    g = gt.adjudicate(text, rel, kind)
                    items.append({"artifact_id": aid, "source_path": rel, "source_kind": kind,
                                  "text": text, "synthetic": False, **g})
                    rc += 1
    items.sort(key=lambda x: x["artifact_id"])
    return items


# adversarial-invariant cases: each targets one invariant (honestly synthetic). Golds use the FULL
# minimal-vocabulary level names (from ground_truth) so they compare directly to policy output.
_E3, _ER, _E1 = gt.E3, gt.ER, gt.E1
_ADV = [
    ("INV-1", {"claim_family": "current_fact", "source_role": "model_generated_text", "self_verification": True, "risk_tier": "medium"}, _E3),
    ("INV-2", {"claim_family": "scientific", "evidence_derives_from_claim": True, "risk_tier": "high"}, _E3),
    ("INV-3", {"claim_family": "internal_policy", "claims_internal_authority": True, "explicit_authority_basis": False, "risk_tier": "high"}, _E3),
    ("INV-4", {"claim_family": "code_behavior", "doc_contradicts_impl": True, "risk_tier": "medium"}, _ER),
    ("INV-5", {"claim_family": "measured_performance", "evidence_kind": "test_fixture", "risk_tier": "high"}, _E3),
    ("INV-6", {"claim_family": "security_capability", "evidence_kind": "source_code", "risk_tier": "high"}, _E3),
    ("INV-7", {"claim_family": "current_fact", "authority_stale": True, "temporal_sensitivity": "current_status", "risk_tier": "medium"}, _E3),
    ("INV-8", {"claim_family": "attribution", "treats_attribution_as_truth": True, "risk_tier": "medium"}, _E3),
    ("INV-10", {"claim_family": "", "risk_tier": "unknown"}, _ER),
    ("INV-11", {"claim_family": "action_proposal", "claim_actionability": "action_directive", "risk_tier": "medium"}, _E3),
    ("INV-12", {"claim_family": "subjective_opinion", "risk_tier": "high", "factual_leak": True}, _E1),
]


def _adversarial(n: int) -> List[Dict[str, Any]]:
    out = []
    for i in range(n):
        inv, base, gold = _ADV[i % len(_ADV)]
        variant = i // len(_ADV)
        aid = "adv-" + hashlib.sha256(f"{inv}|{i}".encode()).hexdigest()[:16]
        item = {"artifact_id": aid, "source_path": f"synthetic/adversarial/{inv}/{i}",
                "source_kind": "adversarial", "text": f"Adversarial invariant case for {inv} (v{variant}).",
                "synthetic": True, "target_invariant": inv, "gold_obligation": gold,
                "acceptable_obligations": [gold], "unsafe_obligations": [], **base}
        item.setdefault("claim_family", base.get("claim_family", ""))
        out.append(item)
    out.sort(key=lambda x: x["artifact_id"])
    return out


def build() -> Dict[str, Any]:
    natural = _harvest()
    n = len(natural)
    enough = n >= (TARGET_DEV + TARGET_HELDOUT)
    dev = natural[:TARGET_DEV]
    held = natural[TARGET_DEV:TARGET_DEV + TARGET_HELDOUT]
    adv = _adversarial(TARGET_ADVERSARIAL)
    # human-review set: balanced sample from held-out across obligation classes
    by_gold: Dict[str, List] = {}
    for it in held:
        by_gold.setdefault(it["gold_obligation"], []).append(it)
    review: List = []
    idx = 0
    while len(review) < TARGET_REVIEW and any(by_gold.values()):
        for g in sorted(by_gold):
            if by_gold[g]:
                review.append(by_gold[g].pop())
                if len(review) >= TARGET_REVIEW:
                    break
        idx += 1
        if idx > TARGET_REVIEW:
            break
    review.sort(key=lambda x: x["artifact_id"])
    return {
        "dataset_version": "minimal_evidence_policy_v1",
        "evidence_status": "SUFFICIENT" if enough else "NOT_ENOUGH_EVIDENCE",
        "natural_available": n,
        "partitions": {"DEVELOPMENT": dev, "HELD_OUT_NATURAL": held,
                       "ADVERSARIAL_INVARIANTS": adv, "HUMAN_REVIEW_SET": review},
        "counts": {"DEVELOPMENT": len(dev), "HELD_OUT_NATURAL": len(held),
                   "ADVERSARIAL_INVARIANTS": len(adv), "HUMAN_REVIEW_SET": len(review)},
    }


def freeze() -> Dict[str, Any]:
    m = build()
    os.makedirs(_OUT, exist_ok=True)
    for name, items in m["partitions"].items():
        with open(os.path.join(_OUT, f"{name.lower()}.json"), "w") as fh:
            json.dump(items, fh, indent=2, sort_keys=True)
            fh.write("\n")
    manifest = {k: v for k, v in m.items() if k != "partitions"}
    manifest["partition_sha256"] = {name: hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()
                                    for name, items in m["partitions"].items()}
    with open(os.path.join(_OUT, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True); fh.write("\n")
    return m


def load_partition(name: str) -> List[Dict[str, Any]]:
    with open(os.path.join(_OUT, f"{name.lower()}.json")) as fh:
        return json.load(fh)


if __name__ == "__main__":
    m = freeze()
    print(f"dataset {m['dataset_version']}: status={m['evidence_status']} natural_available={m['natural_available']}")
    print("counts:", m["counts"])
    from collections import Counter
    for name, items in m["partitions"].items():
        print(f"  {name}: {len(items)} | golds {dict(Counter(i['gold_obligation'][:2] for i in items))}")
