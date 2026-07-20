#!/usr/bin/env python3
"""
HIDDEN-EVALUATION LOCK for the Proposal Validation Experiment v0.1.

Content-hashes the v0.2 sources (validator, resolver, orchestrator, preregistration,
rulebook, confidence spec, this lock) AND the frozen dependencies it reuses —
including the entire v0.1 experiment, which must be unchanged — before the first
hidden evaluation of v0.2. Any post-lock edit to a locked file bumps the lock version
and forces a full rerun (disclosed).
"""

from __future__ import annotations

import hashlib
import json
import os

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
LOCK_VERSION = "v0.2"

_V2_FILES = [
    "agentic/hybrid_handover/resolution/experiment_v2/validator.py",
    "agentic/hybrid_handover/resolution/experiment_v2/hybrid_resolver_v2.py",
    "agentic/hybrid_handover/resolution/experiment_v2/run_validation_experiment.py",
    "agentic/hybrid_handover/resolution/experiment_v2/lock_v2.py",
    "agentic/hybrid_handover/resolution/experiment_v2/PROPOSAL_VALIDATION_PREREGISTRATION.md",
    "agentic/hybrid_handover/resolution/experiment_v2/VALIDATION_RULEBOOK.md",
    "agentic/hybrid_handover/resolution/experiment_v2/CONFIDENCE_VECTOR_SPEC.md",
]

# frozen dependencies reused unchanged (v0.1 experiment + frozen platform)
_FROZEN_FILES = [
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
    "study": "Proposal Validation Experiment v0.1",
    "resolver_under_test": "HybridRelationshipResolver Experimental v0.2",
    "ablation_order": ["V0_none", "V1_dedupe_only", "V2_evidence_only",
                       "V3_authority_temporal", "V4_full"],
    "floor_lexical": 0.6, "floor_structural": 0.5,
    "primary_endpoint": "recover discovery precision with recall loss <= 0.03 vs V0",
    "recall_loss_margin": 0.03,
    "order_sensitive_types": ["supersedes", "amends", "effective_after"],
    "destination_required_types": ["supersedes", "amends", "overrides", "governs_over",
                                    "exception_to", "conflicts_with", "effective_after"],
    "bootstrap_seed": 20240601, "bootstrap_iters": 10000,
    "repetitions": 2, "byte_identical_required": True,
    "note": "v0.1 experiment and all frozen platform artifacts are unchanged.",
}


def _sha256(path):
    with open(os.path.join(ROOT, path), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def generate():
    v2 = {p: _sha256(p) for p in _V2_FILES}
    frz = {p: _sha256(p) for p in _FROZEN_FILES}
    manifest_hash = hashlib.sha256(json.dumps(MANIFEST, sort_keys=True).encode()).hexdigest()
    combined = hashlib.sha256(json.dumps(
        {"v2": v2, "frozen": frz, "manifest": manifest_hash}, sort_keys=True).encode()).hexdigest()
    return {"lock_version": LOCK_VERSION, "v2_hashes": v2, "frozen_hashes": frz,
            "manifest": MANIFEST, "manifest_hash": manifest_hash, "combined_lock_hash": combined}


def write_lock_doc():
    lock = generate()
    lines = [
        "# HIDDEN_EVALUATION_LOCK_V2 — Proposal Validation Experiment v0.1", "",
        f"**Lock version:** `{lock['lock_version']}`  ",
        f"**Combined lock hash:** `{lock['combined_lock_hash']}`  ",
        f"**Manifest hash:** `{lock['manifest_hash']}`", "",
        "Computed BEFORE the first hidden evaluation of v0.2. The v0.1 experiment and all",
        "frozen platform artifacts are hashed here to prove they are unchanged.", "",
        "## Manifest", "```json", json.dumps(lock["manifest"], indent=2), "```", "",
        "## v0.2 source hashes (SHA-256)", "| file | sha256 |", "|---|---|"]
    for p, h in lock["v2_hashes"].items():
        lines.append(f"| `{p.split('/')[-1]}` | `{h}` |")
    lines += ["", "## Frozen-dependency hashes (must be unchanged)", "| file | sha256 |", "|---|---|"]
    for p, h in lock["frozen_hashes"].items():
        lines.append(f"| `{'/'.join(p.split('/')[-2:])}` | `{h}` |")
    lines += ["", "## Discipline",
              "- Validator rules and floors (lexical 0.6, structural 0.5) were selected on the",
              "  visible corpus so that V4 rejects zero correct visible edges; frozen here.",
              "- No hidden per-case failure was inspected before this lock.",
              "- Two byte-identical repetitions are required.", ""]
    with open(os.path.join(HERE, "HIDDEN_EVALUATION_LOCK_V2.md"), "w") as f:
        f.write("\n".join(lines))
    with open(os.path.join(HERE, "HIDDEN_EVALUATION_LOCK_V2.json"), "w") as f:
        json.dump(lock, f, indent=2)
    return lock


def verify():
    path = os.path.join(HERE, "HIDDEN_EVALUATION_LOCK_V2.json")
    if not os.path.exists(path):
        return ["<no lock written>"]
    with open(path) as f:
        locked = json.load(f)
    drift = []
    for group in ("v2_hashes", "frozen_hashes"):
        for p, h in locked[group].items():
            if _sha256(p) != h:
                drift.append(p)
    return drift


if __name__ == "__main__":
    lk = write_lock_doc()
    print("combined_lock_hash:", lk["combined_lock_hash"])
