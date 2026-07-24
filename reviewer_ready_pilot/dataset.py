"""Phases 6 & 8 - Training set and final review set for the reviewer-ready pilot.

Harvests NEW natural artifacts (absent from ALL prior sets, including the earlier
reviewer_calibration_pilot final + training sets) and builds two frozen collections:

  training_v1     (20-30 items, WITH revealed gold labels + explanations - reviewers learn from these)
  final_review_v1 (target 90, >=75, NO revealed labels - reviewers judge blind)

Both include honestly-synthetic trap cases alongside natural artifacts. Gold labels for TRAINING come
from the frozen minimal policy (read-only) so a candidate reviewer can study the intended reasoning; the
FINAL set stores ONLY blind metadata - no gold_obligation, no explanation - because the final set is what
a real reviewer would judge and must never be tuned or coached on.

Training items never appear in the final review set (disjoint by artifact_id and source_path).

If insufficient NEW natural artifacts exist, the manifest records NOT_ENOUGH_ELIGIBLE_ARTIFACTS with the
actual count. Deterministic. Consumes minimal_evidence_policy READ-ONLY (never modifies it) and does not
tune any policy rule on any artifact.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from typing import Any, Dict, List

from customer_shadow_readiness import data_controls as dc
from minimal_evidence_policy import ground_truth as gt          # independent surface metadata (read-only)
from minimal_evidence_policy import classifier as policy         # frozen policy (read-only, training labels)

_PKG = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_PKG)
_TRAIN_DIR = os.path.join(_PKG, "data", "training_v1")
_FINAL_DIR = os.path.join(_PKG, "data", "final_review_v1")

TARGET_TRAINING = 24          # 16 natural + 8 traps (within the 20-30 band)
NATURAL_TRAINING = 16
NATURAL_FINAL = 78            # natural eligible artifacts in the final set (>= MIN_FINAL on their own)
TRAP_VARIANTS = 3            # 3 variants x 8 trap types = 24 honestly-synthetic traps
MIN_FINAL = 75
_ROOTS = ["symbolu_core", "agentic", "symbolu_extensions", "symbolu_training", "CTM_plus",
          "symbolu_robotics", "quad_generative_regularization", "quad_perturbation_consistency_sync",
          "model_selection_experiment", "cer_v0_1", "cer_public_draft", "control_plane",
          "robotics_reliability_bench", "varna_lens", "trading", "trading2", "sdk",
          "execution_proposal_engine", "symbolu_neural", "symbolu_bcvf_llm"]
_SKIP = {"__pycache__", ".git", "tests", "node_modules"}
_WORD = re.compile(r"\b\w+\b")
_PER_ROOT = 50


def _quality(t: str) -> bool:
    t = (t or "").strip()
    return len(t) >= 80 and len(_WORD.findall(t)) >= 12 and sum(c.isalpha() for c in t) >= 0.5 * len(t)


def _prior_paths() -> set:
    """Every source_path already consumed by a prior corpus / dev / held-out / review set."""
    p: set = set()
    # bounded_shadow_pilot natural corpus
    bsp = os.path.join(_ROOT, "bounded_shadow_pilot/data/natural_pilot_v1/corpus.json")
    if os.path.exists(bsp):
        p |= set(a["source_path"] for a in json.load(open(bsp))["artifacts"])
    # evidence_obligation + minimal_evidence_policy development + held-out natural sets
    for track, parts in (("evidence_obligation", ("development", "held_out_natural")),
                         ("minimal_evidence_policy", ("development", "held_out_natural"))):
        for part in parts:
            fp = os.path.join(_ROOT, f"{track}/data/v1/{part}.json")
            if os.path.exists(fp):
                p |= set(i["source_path"] for i in json.load(open(fp)))
    # minimal_evidence_policy human review set (natural entries carry source_path)
    hrs = os.path.join(_ROOT, "minimal_evidence_policy/data/v1/human_review_set.json")
    if os.path.exists(hrs):
        for i in json.load(open(hrs)):
            if i.get("source_path"):
                p.add(i["source_path"])
    # reviewer_calibration_pilot training + final natural source paths
    for rel in ("reviewer_calibration_pilot/data/training_v1/training.json",
                "reviewer_calibration_pilot/data/final_review_v1/final_review.json"):
        fp = os.path.join(_ROOT, rel)
        if os.path.exists(fp):
            for i in json.load(open(fp)):
                if not i.get("synthetic") and i.get("source_path"):
                    p.add(i["source_path"])
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
                if rc >= _PER_ROOT:
                    break
                if not fn.endswith((".py", ".md")):
                    continue
                p = os.path.join(dp, fn)
                rel = os.path.relpath(p, _ROOT)
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
                    if rc >= _PER_ROOT:
                        break
                    if not c or not _quality(c) or not dc.permitted_use(dc.classify(c), "internal"):
                        continue
                    aid = "rrp-" + hashlib.sha256((rel + "|" + c).encode()).hexdigest()[:16]
                    if aid in seen:
                        continue
                    seen.add(aid)
                    text = dc.redact(c)
                    md = gt.derive_metadata(text, rel, kind)
                    items.append({"artifact_id": aid, "source_path": rel, "source_kind": kind,
                                  "text": text, "synthetic": False, **md})
                    rc += 1
    items.sort(key=lambda x: x["artifact_id"])
    return items


# constructed trap cases (honestly synthetic, labelled `synthetic: True`) - present in training
# (with revealed labels) and final (blind). Traps are NEVER counted as natural eligible artifacts.
_TRAPS = [
    ("self_verification", {"claim_family": "current_fact", "source_role": "model_generated_text", "self_verification": True, "risk_tier": "medium", "text": "The model states its own output is verified and correct."}),
    ("circular_evidence", {"claim_family": "scientific", "evidence_derives_from_claim": True, "risk_tier": "high", "text": "The claim is corroborated by a summary generated from the same claim."}),
    ("stale_authority", {"claim_family": "current_fact", "authority_stale": True, "temporal_sensitivity": "current_status", "risk_tier": "medium", "text": "Per the 2019 policy, this is currently the active configuration."}),
    ("fixture_as_telemetry", {"claim_family": "measured_performance", "evidence_kind": "test_fixture", "risk_tier": "high", "text": "A unit-test fixture shows p99 latency is 5ms in production."}),
    ("impl_as_operational", {"claim_family": "security_capability", "evidence_kind": "source_code", "risk_tier": "high", "text": "The code contains an auth check, so the endpoint is secure in production."}),
    ("action_no_approval", {"claim_family": "action_proposal", "claim_actionability": "action_directive", "risk_tier": "high", "text": "Grant the service account admin access to unblock the deploy."}),
    ("attribution_as_truth", {"claim_family": "attribution", "treats_attribution_as_truth": True, "risk_tier": "medium", "text": "According to the vendor, the system is fully compliant, so it is compliant."}),
    ("high_risk_opinion", {"claim_family": "subjective_opinion", "risk_tier": "high", "factual_leak": True, "text": "In my opinion the medication is completely safe for all patients."}),
]


# honestly-synthetic RISK-TIER edge cases (not part of the 8 safety-trap families). They give the review
# set coverage of the critical and unknown risk tiers, which natural code docstrings rarely carry. Flagged
# synthetic; revealed in training, blind in final.
_EDGE = [
    ("critical_regulated_action", {"claim_family": "medical", "claim_actionability": "action_directive",
     "risk_tier": "critical", "text": "Administer the maximum dose to every patient without physician sign-off."}),
    ("critical_financial_claim", {"claim_family": "financial", "risk_tier": "critical",
     "text": "This unaudited model guarantees a 40% return with zero downside for all investors."}),
    ("unknown_metadata", {"claim_family": "unknown", "risk_tier": "unknown", "source_role": "unknown_source",
     "text": "An unattributed note asserts a state change with no discernible source, type, or authority."}),
    ("unknown_conflicting", {"claim_family": "unknown", "risk_tier": "unknown",
     "text": "Two undated sources give opposite current values; neither can be resolved."}),
]


def _trap_item(i: int, kind: str, base: Dict[str, Any], reveal: bool) -> Dict[str, Any]:
    aid = "trap-" + hashlib.sha256(f"rrp|{kind}|{i}".encode()).hexdigest()[:16]
    it = {"artifact_id": aid, "source_path": f"synthetic/{kind}/{i}", "source_kind": "trap",
          "synthetic": True, "trap_type": kind, **base}
    it.setdefault("source_role", base.get("source_role", "unknown_source"))
    it.setdefault("claim_actionability", base.get("claim_actionability", "none"))
    it.setdefault("temporal_sensitivity", base.get("temporal_sensitivity", "static"))
    if reveal:
        d = policy.classify(it)
        it["gold_obligation"] = d.final_obligation
        it["gold_explanation"] = d.rationale
        it["invariants_triggered"] = d.invariants_triggered
    return it


def _edge_item(i: int, kind: str, base: Dict[str, Any], reveal: bool) -> Dict[str, Any]:
    aid = "edge-" + hashlib.sha256(f"rrp|{kind}|{i}".encode()).hexdigest()[:16]
    it = {"artifact_id": aid, "source_path": f"synthetic/edge/{kind}/{i}", "source_kind": "edge_case",
          "synthetic": True, "edge_type": kind, **base}
    it.setdefault("source_role", base.get("source_role", "unknown_source"))
    it.setdefault("claim_actionability", base.get("claim_actionability", "none"))
    it.setdefault("temporal_sensitivity", base.get("temporal_sensitivity", "static"))
    if reveal:
        d = policy.classify(it)
        it["gold_obligation"] = d.final_obligation
        it["gold_explanation"] = d.rationale
        it["invariants_triggered"] = d.invariants_triggered
    return it


def build() -> Dict[str, Any]:
    natural = _harvest()
    n = len(natural)
    # need NATURAL_TRAINING for training + NATURAL_FINAL natural for the final set, disjoint.
    enough = n >= (NATURAL_TRAINING + NATURAL_FINAL)

    # training: revealed labels from the frozen policy so a candidate reviewer can study the reasoning.
    training: List[Dict[str, Any]] = []
    for it in natural[:NATURAL_TRAINING]:
        d = policy.classify(it)
        training.append({**it, "gold_obligation": d.final_obligation, "gold_explanation": d.rationale,
                         "invariants_triggered": d.invariants_triggered})
    for i, (kind, base) in enumerate(_TRAPS):
        training.append(_trap_item(i, kind, base, reveal=True))
    for i, (kind, base) in enumerate(_EDGE):
        training.append(_edge_item(i, kind, base, reveal=True))
    training.sort(key=lambda x: x["artifact_id"])
    train_paths = set(it["source_path"] for it in training)

    # final: disjoint natural artifacts (blind) + honestly-synthetic traps (blind, TRAP_VARIANTS each).
    remaining = [it for it in natural[NATURAL_TRAINING:] if it["source_path"] not in train_paths]
    final_natural = remaining[:NATURAL_FINAL]
    final: List[Dict[str, Any]] = [
        {k: v for k, v in it.items()
         if k not in ("gold_obligation", "gold_explanation", "invariants_triggered")}
        for it in final_natural
    ]
    for v in range(TRAP_VARIANTS):
        for i, (kind, base) in enumerate(_TRAPS):
            final.append(_trap_item(2000 + v * 100 + i, kind, base, reveal=False))
        for i, (kind, base) in enumerate(_EDGE):
            final.append(_edge_item(2000 + v * 100 + i, kind, base, reveal=False))
    final.sort(key=lambda x: x["artifact_id"])

    natural_in_final = sum(1 for it in final if not it.get("synthetic"))
    return {
        "dataset_version": "reviewer_ready_v1",
        "evidence_status": "SUFFICIENT" if (enough and natural_in_final >= MIN_FINAL) else "NOT_ENOUGH_ELIGIBLE_ARTIFACTS",
        "natural_available": n,
        "training": training, "final_review": final,
        "counts": {"training": len(training), "training_natural": NATURAL_TRAINING,
                   "final_review": len(final), "final_natural": natural_in_final,
                   "trap_variants": TRAP_VARIANTS, "final_min": MIN_FINAL},
    }


def freeze() -> Dict[str, Any]:
    m = build()
    os.makedirs(_TRAIN_DIR, exist_ok=True)
    os.makedirs(_FINAL_DIR, exist_ok=True)
    with open(os.path.join(_TRAIN_DIR, "training.json"), "w") as fh:
        json.dump(m["training"], fh, indent=2, sort_keys=True); fh.write("\n")
    with open(os.path.join(_FINAL_DIR, "final_review.json"), "w") as fh:
        json.dump(m["final_review"], fh, indent=2, sort_keys=True); fh.write("\n")
    manifest = {k: v for k, v in m.items() if k not in ("training", "final_review")}
    manifest["training_sha256"] = hashlib.sha256(json.dumps(m["training"], sort_keys=True).encode()).hexdigest()
    manifest["final_sha256"] = hashlib.sha256(json.dumps(m["final_review"], sort_keys=True).encode()).hexdigest()
    with open(os.path.join(_PKG, "data", "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True); fh.write("\n")
    return m


def load_training() -> List[Dict[str, Any]]:
    return json.load(open(os.path.join(_TRAIN_DIR, "training.json")))


def load_final() -> List[Dict[str, Any]]:
    return json.load(open(os.path.join(_FINAL_DIR, "final_review.json")))


if __name__ == "__main__":
    m = freeze()
    print(f"dataset {m['dataset_version']}: status={m['evidence_status']} natural_available={m['natural_available']}")
    print("counts:", m["counts"])
