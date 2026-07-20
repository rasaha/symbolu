#!/usr/bin/env python3
"""
HIDDEN-EVALUATION LOCK for the Edge Prioritization Experiment v0.1.

Content-hashes the v0.3 sources AND the frozen dependencies it reuses — including the
entire v0.2 experiment and the v0.1 experiment, which must be unchanged — before the
first hidden evaluation of v0.3. Any post-lock edit to a locked file bumps the lock
version and forces a full rerun (disclosed).
"""

from __future__ import annotations

import hashlib
import json
import os

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
LOCK_VERSION = "v0.3"

_V3_FILES = [
    "agentic/hybrid_handover/resolution/experiment_v3/prioritizer.py",
    "agentic/hybrid_handover/resolution/experiment_v3/hybrid_resolver_v3.py",
    "agentic/hybrid_handover/resolution/experiment_v3/run_prioritization_experiment.py",
    "agentic/hybrid_handover/resolution/experiment_v3/lock_v3.py",
    "agentic/hybrid_handover/resolution/experiment_v3/EDGE_PRIORITIZATION_PREREGISTRATION.md",
    "agentic/hybrid_handover/resolution/experiment_v3/PRIORITY_VECTOR_SPEC.md",
    "agentic/hybrid_handover/resolution/experiment_v3/EDGE_PRIORITY_RULEBOOK.md",
]

_FROZEN_FILES = [
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

MANIFEST = {
    "study": "Edge Prioritization Experiment v0.1",
    "resolver_under_test": "HybridRelationshipResolver Experimental v0.3",
    "ablation_order": ["P0_none", "P1_authority", "P2_authority_temporal",
                       "P3_auth_temporal_specificity", "P4_full"],
    "priority_component_order": ["authority", "temporal", "specificity", "reference",
                                 "structural", "confidence", "support"],
    "governance_source_types": ["supersedes", "overrides", "governs_over"],
    "primary_endpoint": "selective_accuracy, no degradation of discovery precision/"
                        "recall, classification, governance ModeG, packet ModeP, unsafe",
    "bootstrap_seed": 20240601, "bootstrap_iters": 10000,
    "repetitions": 2, "byte_identical_required": True,
    "note": "v0.2, the Proposal Validation Layer, v0.1, and all frozen platform "
            "artifacts are unchanged; proposal + validation are bit-identical to v0.2.",
}


def _sha256(path):
    with open(os.path.join(ROOT, path), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def generate():
    v3 = {p: _sha256(p) for p in _V3_FILES}
    frz = {p: _sha256(p) for p in _FROZEN_FILES}
    manifest_hash = hashlib.sha256(json.dumps(MANIFEST, sort_keys=True).encode()).hexdigest()
    combined = hashlib.sha256(json.dumps(
        {"v3": v3, "frozen": frz, "manifest": manifest_hash}, sort_keys=True).encode()).hexdigest()
    return {"lock_version": LOCK_VERSION, "v3_hashes": v3, "frozen_hashes": frz,
            "manifest": MANIFEST, "manifest_hash": manifest_hash, "combined_lock_hash": combined}


def write_lock_doc():
    lock = generate()
    lines = [
        "# HIDDEN_EVALUATION_LOCK_V3 — Edge Prioritization Experiment v0.1", "",
        f"**Lock version:** `{lock['lock_version']}`  ",
        f"**Combined lock hash:** `{lock['combined_lock_hash']}`  ",
        f"**Manifest hash:** `{lock['manifest_hash']}`", "",
        "Computed BEFORE the first hidden evaluation of v0.3. The v0.2 experiment (proposal",
        "generation + Proposal Validation Layer), the v0.1 experiment, and all frozen",
        "platform artifacts are hashed here to prove they are unchanged.", "",
        "## Manifest", "```json", json.dumps(lock["manifest"], indent=2), "```", "",
        "## v0.3 source hashes (SHA-256)", "| file | sha256 |", "|---|---|"]
    for p, h in lock["v3_hashes"].items():
        lines.append(f"| `{p.split('/')[-1]}` | `{h}` |")
    lines += ["", "## Frozen-dependency hashes (must be unchanged)", "| file | sha256 |", "|---|---|"]
    for p, h in lock["frozen_hashes"].items():
        lines.append(f"| `{'/'.join(p.split('/')[-2:])}` | `{h}` |")
    lines += ["", "## Discipline",
              "- Proposal generation and validation are bit-identical to v0.2 (reused by composition).",
              "- Prioritization runs only in the full pipeline; discovery, Mode G, and Mode P are",
              "  structurally unchanged. P0 reproduces v0.2; visible metrics are unchanged under P1–P4.",
              "- No hidden per-case failure was inspected before this lock.",
              "- Two byte-identical repetitions are required.", ""]
    with open(os.path.join(HERE, "HIDDEN_EVALUATION_LOCK_V3.md"), "w") as f:
        f.write("\n".join(lines))
    with open(os.path.join(HERE, "HIDDEN_EVALUATION_LOCK_V3.json"), "w") as f:
        json.dump(lock, f, indent=2)
    return lock


def verify():
    path = os.path.join(HERE, "HIDDEN_EVALUATION_LOCK_V3.json")
    if not os.path.exists(path):
        return ["<no lock written>"]
    with open(path) as f:
        locked = json.load(f)
    drift = []
    for group in ("v3_hashes", "frozen_hashes"):
        for p, h in locked[group].items():
            if _sha256(p) != h:
                drift.append(p)
    return drift


if __name__ == "__main__":
    lk = write_lock_doc()
    print("combined_lock_hash:", lk["combined_lock_hash"])
