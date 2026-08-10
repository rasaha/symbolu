#!/usr/bin/env python3
"""
HIDDEN-EVALUATION LOCK for the Exploratory Resolver Study v0.1.

Before the first hidden evaluation, every artifact that could influence the
result is content-hashed: the experimental resolver source, the preregistration,
the thresholds/margins, the statistics code, the metric harness, AND the frozen
dependencies (proving they are unchanged). The manifest (run order, seed, τ,
margins, primary-endpoint definition) is hashed too. Any post-lock edit to a
locked file changes its hash and, per the preregistration, invalidates prior
hidden runs and bumps the lock version.

`generate()` computes the lock; `write_lock_doc()` renders HIDDEN_EVALUATION_LOCK.md;
`verify()` re-checks the locked hashes against the current tree.
"""

from __future__ import annotations

import hashlib
import json
import os

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
LOCK_VERSION = "v0.1"

# experiment sources (mutable within the study, hashed at lock)
_EXPERIMENT_FILES = [
    "agentic/hybrid_handover/resolution/experiment/hybrid_resolver.py",
    "Project_documentation/agentic_framework/agentic/hybrid_handover/resolution/experiment/EXPERIMENT_PREREGISTRATION.md",
    "agentic/hybrid_handover/resolution/experiment/stats.py",
    "agentic/hybrid_handover/resolution/experiment/hidden_metrics.py",
    "agentic/hybrid_handover/resolution/experiment/hidden_data.py",
    "agentic/hybrid_handover/resolution/experiment/run_experiment.py",
    "agentic/hybrid_handover/resolution/experiment/lock.py",
]

# frozen dependencies (must be byte-identical to their frozen state)
_FROZEN_FILES = [
    "agentic/hybrid_handover/resolution/resolvers.py",
    "agentic/hybrid_handover/resolution/parse.py",
    "agentic/hybrid_handover/resolution/graph.py",
    "agentic/hybrid_handover/resolution/gold.py",
    "agentic/hybrid_handover/resolution/modes.py",
    "agentic/hybrid_handover/resolution/measurement/stage_metrics.py",
    "agentic/hybrid_handover/resolution/measurement/abstention.py",
    "agentic/hybrid_handover/resolution/measurement/gold_graph.py",
    "agentic/hybrid_handover/resolution/audit/adversarial.py",
    "agentic/hybrid_handover/resolution/hidden_corpus/corpus.py",
    "agentic/hybrid_handover/resolution/hidden_corpus/annotations.py",
    "agentic/hybrid_handover/resolution/hidden_corpus/curation/pilot_corpus.py",
    "agentic/hybrid_handover/resolution/hidden_corpus/curation/pilot_annotations.py",
]

# the frozen manifest (thresholds, run order, seed, endpoint) — hashed as data
MANIFEST = {
    "study": "Exploratory Resolver Study v0.1",
    "resolver_under_test": "HybridRelationshipResolver Experimental v0.1",
    "corpus": "Hidden Relationship Corpus Pilot v0.2 (22 seed + 38 pilot = 60)",
    "comparator_run_order": [
        "null", "always_abstain", "frozen", "rule", "graph_traversal", "hybrid_relationship"],
    "ablations": ["A0_full", "A1_no_semantic", "A2_no_traversal", "A3_no_governance_rules",
                  "A4_no_confidence_abstain", "A5_no_provenance", "A6_discovery_only",
                  "A7_modeG_gold_graph", "A8_modeP_gold_governance"],
    "abstention_threshold_tau": 0.5,
    "bootstrap_seed": 20240601,
    "bootstrap_iters": 10000,
    "ci_alpha": 0.05,
    "primary_endpoint": "hidden_owner_clean_macro = mean(discovery_f1, "
                        "classification_accuracy, governance_accuracy_modeG, "
                        "packet_realization_accuracy_modeP, selective_accuracy)",
    "practical_significance_threshold": 0.03,
    "non_inferiority_margins": {
        "discovery_precision_decrease": 0.05, "governance_modeG_decrease": 0.03,
        "packet_modeP_decrease": 0.03, "selective_decrease": 0.03,
        "false_abstention_increase": 0.05, "missed_abstention_increase": 0.05,
        "coverage_decrease": 0.10, "unsafe_answers_increase": "any", "determinism": "must hold"},
    "repetitions": 2, "byte_identical_required": True,
}


def _sha256(path: str) -> str:
    with open(os.path.join(ROOT, path), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def generate() -> dict:
    exp = {p: _sha256(p) for p in _EXPERIMENT_FILES}
    frz = {p: _sha256(p) for p in _FROZEN_FILES}
    manifest_hash = hashlib.sha256(
        json.dumps(MANIFEST, sort_keys=True).encode()).hexdigest()
    combined = hashlib.sha256(
        json.dumps({"experiment": exp, "frozen": frz, "manifest": manifest_hash},
                   sort_keys=True).encode()).hexdigest()
    return {"lock_version": LOCK_VERSION, "experiment_hashes": exp,
            "frozen_hashes": frz, "manifest": MANIFEST,
            "manifest_hash": manifest_hash, "combined_lock_hash": combined}


def write_lock_doc() -> dict:
    lock = generate()
    lines = [
        "# HIDDEN_EVALUATION_LOCK — Exploratory Resolver Study v0.1",
        "",
        f"**Lock version:** `{lock['lock_version']}`  ",
        f"**Combined lock hash:** `{lock['combined_lock_hash']}`  ",
        f"**Manifest hash:** `{lock['manifest_hash']}`",
        "",
        "This lock is computed BEFORE the first hidden evaluation. Every artifact that",
        "could influence the hidden result is content-hashed below. Per the",
        "preregistration, any post-lock edit to a locked file invalidates prior hidden",
        "runs, bumps the lock version, and forces a full rerun (disclosed).",
        "",
        "## Manifest (frozen parameters)",
        "```json",
        json.dumps(lock["manifest"], indent=2),
        "```",
        "",
        "## Experiment source hashes (SHA-256)",
        "| file | sha256 |", "|---|---|",
    ]
    for p, h in lock["experiment_hashes"].items():
        lines.append(f"| `{p.split('/')[-1]}` | `{h}` |")
    lines += ["", "## Frozen-dependency hashes (must be unchanged)",
              "| file | sha256 |", "|---|---|"]
    for p, h in lock["frozen_hashes"].items():
        lines.append(f"| `{'/'.join(p.split('/')[-2:])}` | `{h}` |")
    lines += ["", "## Discipline",
              "- No per-case hidden failure was inspected before this lock.",
              "- Thresholds (τ=0.5) and non-inferiority margins were selected on the",
              "  visible corpus and are frozen here.",
              "- Two byte-identical repetitions are required for the run to count.",
              ""]
    with open(os.path.join(HERE, "HIDDEN_EVALUATION_LOCK.md"), "w") as f:
        f.write("\n".join(lines))
    with open(os.path.join(HERE, "HIDDEN_EVALUATION_LOCK.json"), "w") as f:
        json.dump(lock, f, indent=2)
    return lock


def verify() -> list[str]:
    """Return a list of files whose current hash differs from the locked hash."""
    path = os.path.join(HERE, "HIDDEN_EVALUATION_LOCK.json")
    if not os.path.exists(path):
        return ["<no lock written>"]
    with open(path) as f:
        locked = json.load(f)
    drift = []
    for group in ("experiment_hashes", "frozen_hashes"):
        for p, h in locked[group].items():
            if _sha256(p) != h:
                drift.append(p)
    return drift


if __name__ == "__main__":
    lk = write_lock_doc()
    print("combined_lock_hash:", lk["combined_lock_hash"])
