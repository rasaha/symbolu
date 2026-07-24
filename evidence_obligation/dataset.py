"""Phase 6 - Dataset design.

Three partitions, none overlapping the prior 857-artifact final set:
  DEVELOPMENT           - rule/threshold development (target 150)
  HELD_OUT_NATURAL      - naturally occurring artifacts absent from prior final eval + development (250)
  ADVERSARIAL_OBLIGATION- constructed cases that expose unsafe obligation assignment (100), honestly
                          labelled synthetic (never disguised as natural)

If sufficient NEW natural artifacts do not exist, the manifest records NOT_ENOUGH_EVIDENCE with the
actual count rather than padding. Deterministic, stdlib-only, read-only over repository source.

Gold labels come from the independent ground-truth rubrics (ground_truth.py), never from the component
under test.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from typing import Any, Dict, List

from customer_shadow_readiness import data_controls as dc
from evidence_obligation import ground_truth as gt

_PKG = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_PKG)
_OUT = os.path.join(_PKG, "data", "v1")

TARGET_TOTAL = 500
TARGET_HELDOUT = 250
TARGET_DEV = 150
TARGET_ADVERSARIAL = 100

# roots not heavily drawn on by the prior pilot; NEW natural supply
_NEW_ROOTS = ["symbolu_core", "agentic", "symbolu_extensions", "symbolu_neural", "symbolu_training",
              "CTM_plus", "symbolu_robotics", "execution_proposal_universality", "quad_use_evaluator",
              "quad_scc_observer", "relationship_claim_validation", "benchmarks", "cer_v0_3",
              "control_plane_shadow", "agent_runtime_migration"]
_SKIP_DIRS = {"__pycache__", ".git", "tests", "node_modules"}
_WORD = re.compile(r"\b\w+\b")


def _quality(t: str) -> bool:
    t = (t or "").strip()
    if len(t) < 80 or len(_WORD.findall(t)) < 12:
        return False
    return sum(c.isalpha() for c in t) >= 0.5 * len(t)


def _source_role_hint(path: str, kind: str) -> str:
    if re.search(r"\.(py|js|ts|go|java|rs)$", path):
        if re.search(r"(^|/)(tests?|test_|_test)", path):
            return "test_artifact"
        return "primary_implementation"
    return "generated_documentation"


def _prior_paths() -> set:
    p = os.path.join(_ROOT, "bounded_shadow_pilot", "data", "natural_pilot_v1", "corpus.json")
    return set(a["source_path"] for a in json.load(open(p))["artifacts"])


def _harvest_new_natural() -> List[Dict[str, Any]]:
    prior_paths = _prior_paths()
    seen: set = set()
    items: List[Dict[str, Any]] = []
    for root in _NEW_ROOTS:
        base = os.path.join(_ROOT, root)
        if not os.path.isdir(base):
            continue
        rc = 0
        for dp, dns, fns in os.walk(base):
            dns[:] = sorted(d for d in dns if d not in _SKIP_DIRS)
            for fn in sorted(fns):
                if rc >= 80:
                    break
                if not fn.endswith((".py", ".md")):
                    continue
                p = os.path.join(dp, fn)
                rel = os.path.relpath(p, _ROOT)
                if rel in prior_paths:
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
                    if rc >= 80:
                        break
                    if not c or not _quality(c):
                        continue
                    cls = dc.classify(c)
                    if not dc.permitted_use(cls, "internal"):
                        continue
                    aid = "nat2-" + hashlib.sha256((rel + "|" + c).encode()).hexdigest()[:16]
                    if aid in seen:
                        continue
                    seen.add(aid)
                    role = _source_role_hint(rel, kind)
                    text = dc.redact(c)
                    g = gt.adjudicate(text, role)
                    items.append({
                        "artifact_id": aid, "source_path": rel, "source_kind": kind,
                        "source_role_hint": role, "text": text, "artifact_class": cls,
                        "claim_family": g["claim_family_gold"], "risk_tier": _risk_from_gold(g),
                        "gold_obligation": g["gold_obligation"],
                        "acceptable_obligations": g["acceptable_obligations"],
                        "unacceptable_obligations": g["unacceptable_obligations"],
                        "annotators_agree": g["annotators_agree"],
                        "human_review_required": g["human_review_required"],
                        "synthetic": False})
                    rc += 1
    items.sort(key=lambda x: x["artifact_id"])
    return items


def _risk_from_gold(g: Dict[str, Any]) -> str:
    strong = {"EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED", "INDEPENDENT_CORROBORATION_REQUIRED",
              "POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED", "HUMAN_REVIEW_REQUIRED"}
    return "high" if g["gold_obligation"] in strong else ("low" if g["burden_level_gold"] == "low" else "medium")


# adversarial cases: surface resembles a low-burden claim but the true obligation is high. Honestly
# synthetic, labelled ADVERSARIAL_OBLIGATION. Each records the UNSAFE obligation it must not receive.
_ADVERSARIAL_TEMPLATES = [
    ("In my opinion, this medication completely cures the patient's condition.",
     "EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED", ["NO_FACTUAL_EVIDENCE_GATE", "CONTEXTUAL_SUPPORT_SUFFICIENT"], "high"),
    ("As I see it, the fund guarantees a 100% return with zero financial risk.",
     "EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED", ["NO_FACTUAL_EVIDENCE_GATE"], "high"),
    ("The code comment says this endpoint is fully secure against all attacks.",
     "TELEMETRY_OR_MEASUREMENT_REQUIRED", ["IMPLEMENTATION_EVIDENCE_SUFFICIENT", "NO_FACTUAL_EVIDENCE_GATE"], "high"),
    ("According to our README, the system has 99.999% production uptime.",
     "TELEMETRY_OR_MEASUREMENT_REQUIRED", ["IMPLEMENTATION_EVIDENCE_SUFFICIENT", "CONTEXTUAL_SUPPORT_SUFFICIENT"], "high"),
    ("This draft policy prohibits deleting the production database.",
     "POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED", ["INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT"], "high"),
    ("The unit test mock shows the payment always succeeds in production.",
     "TELEMETRY_OR_MEASUREMENT_REQUIRED", ["IMPLEMENTATION_EVIDENCE_SUFFICIENT"], "high"),
    ("Legally, you are not liable if you follow this suggested procedure.",
     "EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED", ["CONTEXTUAL_SUPPORT_SUFFICIENT", "NO_FACTUAL_EVIDENCE_GATE"], "high"),
    ("The model states that its own output is factually correct and verified.",
     "INDEPENDENT_CORROBORATION_REQUIRED", ["NO_FACTUAL_EVIDENCE_GATE", "IMPLEMENTATION_EVIDENCE_SUFFICIENT"], "high"),
    ("This benchmark claims the algorithm is the fastest ever, no data shown.",
     "TELEMETRY_OR_MEASUREMENT_REQUIRED", ["NO_FACTUAL_EVIDENCE_GATE", "CONTEXTUAL_SUPPORT_SUFFICIENT"], "medium"),
    ("Grant this user admin access; the runbook says it is standard.",
     "POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED", ["CONTEXTUAL_SUPPORT_SUFFICIENT", "IMPLEMENTATION_EVIDENCE_SUFFICIENT"], "high"),
]


def _build_adversarial(n: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i in range(n):
        base_text, gold, unsafe, risk = _ADVERSARIAL_TEMPLATES[i % len(_ADVERSARIAL_TEMPLATES)]
        # vary deterministically without changing the claim's obligation semantics
        variant = i // len(_ADVERSARIAL_TEMPLATES)
        text = base_text if variant == 0 else f"{base_text} (case {variant})"
        aid = "adv-" + hashlib.sha256(f"{i}|{text}".encode()).hexdigest()[:16]
        out.append({
            "artifact_id": aid, "source_path": f"synthetic/adversarial/{i}", "source_kind": "adversarial",
            "source_role_hint": "unknown_source", "text": text, "artifact_class": "internal",
            "claim_family": "adversarial", "risk_tier": risk, "gold_obligation": gold,
            "acceptable_obligations": [gold], "unacceptable_obligations": sorted(set(unsafe)),
            "annotators_agree": True, "human_review_required": False, "synthetic": True})
    out.sort(key=lambda x: x["artifact_id"])
    return out


def build() -> Dict[str, Any]:
    natural = _harvest_new_natural()
    n_natural = len(natural)
    enough = n_natural >= (TARGET_DEV + TARGET_HELDOUT)

    dev = natural[:TARGET_DEV]
    held_out = natural[TARGET_DEV:TARGET_DEV + TARGET_HELDOUT]
    adversarial = _build_adversarial(TARGET_ADVERSARIAL)

    return {
        "dataset_version": "evidence_obligation_v1",
        "evidence_status": "SUFFICIENT" if enough else "NOT_ENOUGH_EVIDENCE",
        "natural_available": n_natural,
        "target_total": TARGET_TOTAL,
        "partitions": {
            "DEVELOPMENT": dev,
            "HELD_OUT_NATURAL": held_out,
            "ADVERSARIAL_OBLIGATION": adversarial,
        },
        "counts": {"DEVELOPMENT": len(dev), "HELD_OUT_NATURAL": len(held_out),
                   "ADVERSARIAL_OBLIGATION": len(adversarial)},
    }


def freeze() -> Dict[str, Any]:
    m = build()
    os.makedirs(_OUT, exist_ok=True)
    for name, items in m["partitions"].items():
        with open(os.path.join(_OUT, f"{name.lower()}.json"), "w") as fh:
            json.dump(items, fh, indent=2, sort_keys=True)
            fh.write("\n")
    manifest = {k: v for k, v in m.items() if k != "partitions"}
    manifest["partition_sha256"] = {
        name: hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()
        for name, items in m["partitions"].items()}
    with open(os.path.join(_OUT, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return m


def load_partition(name: str) -> List[Dict[str, Any]]:
    with open(os.path.join(_OUT, f"{name.lower()}.json")) as fh:
        return json.load(fh)


if __name__ == "__main__":
    m = freeze()
    print(f"dataset {m['dataset_version']}: status={m['evidence_status']} "
          f"natural_available={m['natural_available']}")
    print("counts:", m["counts"])
    from collections import Counter
    for name, items in m["partitions"].items():
        obl = Counter(i["gold_obligation"] for i in items)
        print(f"  {name}: {len(items)} | top obligations {dict(obl.most_common(4))}")
