#!/usr/bin/env python3
"""
HIDDEN-EVALUATION LOCK for the Governance Semantics Experiment v0.1.

Content-hashes the v0.4 sources + specs AND the frozen dependencies it reuses —
including the v0.3/v0.2/v0.1 experiments, which must be unchanged — before the first
hidden evaluation of v0.4. Any post-lock edit to a locked file bumps the lock version
and forces a full rerun (disclosed).
"""

from __future__ import annotations

import hashlib
import json
import os

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
LOCK_VERSION = "v0.4"

_V4_FILES = [
    "agentic/hybrid_handover/resolution/experiment_v4/governance_semantics.py",
    "agentic/hybrid_handover/resolution/experiment_v4/hybrid_resolver_v4.py",
    "agentic/hybrid_handover/resolution/experiment_v4/run_governance_experiment.py",
    "agentic/hybrid_handover/resolution/experiment_v4/lock_v4.py",
    "Project_documentation/agentic_framework/agentic/hybrid_handover/resolution/experiment_v4/GOVERNANCE_SEMANTICS_PREREGISTRATION.md",
    "Project_documentation/agentic_framework/agentic/hybrid_handover/resolution/experiment_v4/GOVERNANCE_SEMANTICS_ARCHITECTURE.md",
    "Project_documentation/agentic_framework/agentic/hybrid_handover/resolution/experiment_v4/GOVERNANCE_STATUS_MODEL.md",
    "Project_documentation/agentic_framework/agentic/hybrid_handover/resolution/experiment_v4/GOVERNANCE_RULEBOOK.md",
    "Project_documentation/agentic_framework/agentic/hybrid_handover/resolution/experiment_v4/OPERATIVE_SOURCE_SPEC.md",
    "Project_documentation/agentic_framework/agentic/hybrid_handover/resolution/experiment_v4/GOVERNANCE_ABSTENTION_SPEC.md",
]

_FROZEN_FILES = [
    "agentic/hybrid_handover/resolution/experiment_v3/prioritizer.py",
    "agentic/hybrid_handover/resolution/experiment_v3/hybrid_resolver_v3.py",
    "agentic/hybrid_handover/resolution/experiment_v2/hybrid_resolver_v2.py",
    "agentic/hybrid_handover/resolution/experiment_v2/validator.py",
    "agentic/hybrid_handover/resolution/experiment/hybrid_resolver.py",
    "agentic/hybrid_handover/resolution/experiment/hidden_data.py",
    "agentic/hybrid_handover/resolution/experiment/hidden_metrics.py",
    "agentic/hybrid_handover/resolution/experiment/stats.py",
    "agentic/hybrid_handover/resolution/resolvers.py",
    "agentic/hybrid_handover/resolution/parse.py",
    "agentic/hybrid_handover/resolution/graph.py",
    "agentic/hybrid_handover/resolution/measurement/stage_metrics.py",
    "agentic/hybrid_handover/resolution/measurement/abstention.py",
    "agentic/hybrid_handover/resolution/hidden_corpus/corpus.py",
    "agentic/hybrid_handover/resolution/hidden_corpus/annotations.py",
    "agentic/hybrid_handover/resolution/hidden_corpus/curation/pilot_corpus.py",
    "agentic/hybrid_handover/resolution/hidden_corpus/curation/pilot_annotations.py",
]

# prior experiment locks that must still verify clean
_PRIOR_LOCKS = [
    "agentic/hybrid_handover/resolution/experiment/HIDDEN_EVALUATION_LOCK.json",
    "agentic/hybrid_handover/resolution/experiment_v2/HIDDEN_EVALUATION_LOCK_V2.json",
    "agentic/hybrid_handover/resolution/experiment_v3/HIDDEN_EVALUATION_LOCK_V3.json",
]

MANIFEST = {
    "study": "Governance Semantics Experiment v0.1",
    "resolver_under_test": "HybridRelationshipResolver Experimental v0.4",
    "control": "G0 = HybridRelationshipResolver v0.2 (frozen governance)",
    "ablation_order": ["G0_frozen", "G1_supersession_amendment", "G2_parallel",
                       "G3_operative", "G4_full"],
    "primary_endpoint": "full-pipeline selective_accuracy, G4 vs G0, threshold +0.03",
    "identical_metrics": ["discovery_precision", "discovery_recall", "discovery_f1",
                          "classification_accuracy", "packet_realization_accuracy_modeP"],
    "bounded_noninferiority": {"governance_modeG_decrease": 0.03, "coverage_decrease": 0.05,
                               "false_abstention_increase": 0.05, "missed_abstention_increase": 0.05,
                               "unsafe_increase": "any"},
    "governing_set": "pinned to the frozen governing set (Mode G preserved by construction)",
    "bootstrap_seed": 20240601, "bootstrap_iters": 10000,
    "repetitions": 2, "byte_identical_required": True,
    "note": "v0.1/v0.2/v0.3 experiments and all frozen platform artifacts are unchanged.",
}


def _sha256(path):
    with open(os.path.join(ROOT, path), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def generate():
    v4 = {p: _sha256(p) for p in _V4_FILES}
    frz = {p: _sha256(p) for p in _FROZEN_FILES}
    manifest_hash = hashlib.sha256(json.dumps(MANIFEST, sort_keys=True).encode()).hexdigest()
    combined = hashlib.sha256(json.dumps(
        {"v4": v4, "frozen": frz, "manifest": manifest_hash}, sort_keys=True).encode()).hexdigest()
    return {"lock_version": LOCK_VERSION, "v4_hashes": v4, "frozen_hashes": frz,
            "manifest": MANIFEST, "manifest_hash": manifest_hash, "combined_lock_hash": combined}


def verify_prior_locks():
    """Re-verify every prior experiment lock reports zero drift."""
    out = {}
    from agentic.hybrid_handover.resolution.experiment import lock as l1
    from agentic.hybrid_handover.resolution.experiment_v2 import lock_v2 as l2
    from agentic.hybrid_handover.resolution.experiment_v3 import lock_v3 as l3
    out["v0.1"] = l1.verify()
    out["v0.2"] = l2.verify()
    out["v0.3"] = l3.verify()
    return out


def write_lock_doc():
    lock = generate()
    prior = verify_prior_locks()
    lines = [
        "# GOVERNANCE_SEMANTICS_HIDDEN_LOCK — Governance Semantics Experiment v0.1", "",
        f"**Lock version:** `{lock['lock_version']}`  ",
        f"**Combined lock hash:** `{lock['combined_lock_hash']}`  ",
        f"**Manifest hash:** `{lock['manifest_hash']}`", "",
        "Computed BEFORE the first hidden evaluation of v0.4. The v0.3/v0.2/v0.1 experiments",
        "and all frozen platform artifacts are hashed here to prove they are unchanged.", "",
        "## Prior experiment locks (must verify zero drift)",
        "| experiment | drift |", "|---|---|"]
    for k, v in prior.items():
        lines.append(f"| {k} | {'none' if v == [] else v} |")
    lines += ["", "## Manifest", "```json", json.dumps(lock["manifest"], indent=2), "```", "",
              "## v0.4 source + spec hashes (SHA-256)", "| file | sha256 |", "|---|---|"]
    for p, h in lock["v4_hashes"].items():
        lines.append(f"| `{p.split('/')[-1]}` | `{h}` |")
    lines += ["", "## Frozen-dependency hashes (must be unchanged)", "| file | sha256 |", "|---|---|"]
    for p, h in lock["frozen_hashes"].items():
        lines.append(f"| `{'/'.join(p.split('/')[-2:])}` | `{h}` |")
    lines += ["", "## Calibration gates (must pass before hidden eval)",
              "- G0 control reproduces v0.2 bit-for-bit.",
              "- Discovery + classification identical across G0–G4.",
              "- Proposal-validation records identical across G0–G4.",
              "- Packet Mode P identical (delegated to the frozen packet).",
              "- No correct visible full-pipeline decision degraded (G0–G4 identical on visible).", ""]
    with open(os.path.join(HERE, "GOVERNANCE_SEMANTICS_HIDDEN_LOCK.md"), "w") as f:
        f.write("\n".join(lines))
    with open(os.path.join(HERE, "GOVERNANCE_SEMANTICS_HIDDEN_LOCK.json"), "w") as f:
        json.dump(lock, f, indent=2)
    return lock


def verify():
    path = os.path.join(HERE, "GOVERNANCE_SEMANTICS_HIDDEN_LOCK.json")
    if not os.path.exists(path):
        return ["<no lock written>"]
    with open(path) as f:
        locked = json.load(f)
    drift = []
    for group in ("v4_hashes", "frozen_hashes"):
        for p, h in locked[group].items():
            if _sha256(p) != h:
                drift.append(p)
    return drift


if __name__ == "__main__":
    lk = write_lock_doc()
    print("combined_lock_hash:", lk["combined_lock_hash"])
