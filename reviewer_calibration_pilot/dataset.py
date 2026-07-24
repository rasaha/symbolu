"""Phases 4-5 - Training and final review sets.

Harvests NEW natural artifacts (absent from ALL prior sets) and builds:
  training_v1     (20 items, WITH revealed gold labels + explanations - reviewers learn from these)
  final_review_v1 (target 100, >=60, balanced, NO revealed reviewer gold - reviewers judge blind)

Both include constructed trap cases (self-verification, circular, stale-authority, fixture-as-telemetry)
alongside natural artifacts. Gold labels for TRAINING come from the frozen minimal policy (read-only) +
the independent rubric; the FINAL set stores only metadata (the reviewer gold is produced by humans).

If insufficient NEW natural artifacts exist, the manifest records NOT ENOUGH EVIDENCE with the actual
count. Deterministic. Consumes minimal_evidence_policy READ-ONLY (never modifies it).
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from typing import Any, Dict, List

from customer_shadow_readiness import data_controls as dc
from minimal_evidence_policy import ground_truth as gt          # independent metadata + rubric (read-only)
from minimal_evidence_policy import classifier as policy         # frozen policy (read-only, training labels)

_PKG = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_PKG)
_TRAIN_DIR = os.path.join(_PKG, "data", "training_v1")
_FINAL_DIR = os.path.join(_PKG, "data", "final_review_v1")

TARGET_TRAINING = 20
TARGET_FINAL = 100
MIN_FINAL = 60
_ROOTS = ["symbolu_core", "agentic", "symbolu_extensions", "symbolu_training", "CTM_plus",
          "symbolu_robotics", "quad_perturbation_consistency", "quad_scc_observer", "quad_use_evaluator",
          "relationship_claim_validation", "cer_v0_3", "cer_v0_2", "control_plane_shadow",
          "agent_runtime_migration", "execution_gate_shadow", "model_selection_pilot", "benchmarks",
          "simulator", "cloud_controller", "ndol"]
_SKIP = {"__pycache__", ".git", "tests", "node_modules"}
_WORD = re.compile(r"\b\w+\b")


def _quality(t: str) -> bool:
    t = (t or "").strip()
    return len(t) >= 80 and len(_WORD.findall(t)) >= 12 and sum(c.isalpha() for c in t) >= 0.5 * len(t)


def _prior_paths() -> set:
    p = set(a["source_path"] for a in json.load(
        open(os.path.join(_ROOT, "bounded_shadow_pilot/data/natural_pilot_v1/corpus.json")))["artifacts"])
    for track, parts in (("evidence_obligation", ("development", "held_out_natural")),
                         ("minimal_evidence_policy", ("development", "held_out_natural"))):
        for part in parts:
            p |= set(i["source_path"] for i in json.load(
                open(os.path.join(_ROOT, f"{track}/data/v1/{part}.json"))))
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
                if rc >= 50:
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
                    if rc >= 50:
                        break
                    if not c or not _quality(c) or not dc.permitted_use(dc.classify(c), "internal"):
                        continue
                    aid = "rcp-" + hashlib.sha256((rel + "|" + c).encode()).hexdigest()[:16]
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


# constructed trap cases (honestly synthetic) - present in both training (labelled) and final (blind)
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


def _trap_item(i: int, kind: str, base: Dict[str, Any], reveal: bool) -> Dict[str, Any]:
    aid = "trap-" + hashlib.sha256(f"{kind}|{i}".encode()).hexdigest()[:16]
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


def build() -> Dict[str, Any]:
    natural = _harvest()
    n = len(natural)
    enough = n >= (TARGET_TRAINING + MIN_FINAL)

    # training: 12 natural + 8 traps, with revealed labels
    training = []
    for it in natural[:12]:
        d = policy.classify(it)
        training.append({**it, "gold_obligation": d.final_obligation, "gold_explanation": d.rationale,
                         "invariants_triggered": d.invariants_triggered})
    for i, (kind, base) in enumerate(_TRAPS):
        training.append(_trap_item(i, kind, base, reveal=True))
    training.sort(key=lambda x: x["artifact_id"])

    # final: 60 natural + 40 traps (5 variants per type) so the safety categories meet their minimums
    # without fabricating NATURAL artifacts (traps are honestly synthetic). self-verif+circular=10,
    # source-authority (stale/impl/attribution)=15, action-bearing (action/opinion)=10.
    TRAP_VARIANTS = 5
    final_natural = natural[12:12 + (TARGET_FINAL - len(_TRAPS) * TRAP_VARIANTS)]
    final = list(final_natural)
    for v in range(TRAP_VARIANTS):
        for i, (kind, base) in enumerate(_TRAPS):
            final.append(_trap_item(1000 + v * 100 + i, kind, base, reveal=False))
    final.sort(key=lambda x: x["artifact_id"])

    return {
        "dataset_version": "reviewer_calibration_v1",
        "evidence_status": "SUFFICIENT" if enough else "NOT_ENOUGH_EVIDENCE",
        "natural_available": n,
        "training": training, "final_review": final,
        "counts": {"training": len(training), "final_review": len(final),
                   "final_min": MIN_FINAL, "final_target": TARGET_FINAL},
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
