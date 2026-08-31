#!/usr/bin/env python3
"""HIDDEN-EVALUATION LOCK for the Competing Operative Resolution Experiment v0.1."""

from __future__ import annotations

import hashlib
import json
import os

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
LOCK_VERSION = "v0.5"

_V5_FILES = [
    "agentic/hybrid_handover/resolution/experiment_v5/competing_operative.py",
    "agentic/hybrid_handover/resolution/experiment_v5/hybrid_resolver_v5.py",
    "agentic/hybrid_handover/resolution/experiment_v5/synthetic_fixtures.py",
    "agentic/hybrid_handover/resolution/experiment_v5/run_competing_operative_experiment.py",
    "agentic/hybrid_handover/resolution/experiment_v5/lock_v5.py",
    "Project_documentation/agentic_framework/agentic/hybrid_handover/resolution/experiment_v5/COMPETING_OPERATIVE_PREREGISTRATION.md",
    "Project_documentation/agentic_framework/agentic/hybrid_handover/resolution/experiment_v5/COMPETING_OPERATIVE_ARCHITECTURE.md",
    "Project_documentation/agentic_framework/agentic/hybrid_handover/resolution/experiment_v5/OPERATIVE_CANDIDATE_SCHEMA.md",
    "Project_documentation/agentic_framework/agentic/hybrid_handover/resolution/experiment_v5/OPERATIVE_SCOPE_SPEC.md",
    "Project_documentation/agentic_framework/agentic/hybrid_handover/resolution/experiment_v5/CONFLICT_PREDICATE_SPEC.md",
    "Project_documentation/agentic_framework/agentic/hybrid_handover/resolution/experiment_v5/CONFLICT_CLASSIFICATION_RULEBOOK.md",
    "Project_documentation/agentic_framework/agentic/hybrid_handover/resolution/experiment_v5/PRECISE_ABSTENTION_SPEC.md",
    "Project_documentation/agentic_framework/agentic/hybrid_handover/resolution/experiment_v5/PACKET_CARDINALITY_BOUNDARY.md",
]

_FROZEN_FILES = [
    "agentic/hybrid_handover/resolution/experiment_v4/governance_semantics.py",
    "agentic/hybrid_handover/resolution/experiment_v4/hybrid_resolver_v4.py",
    "agentic/hybrid_handover/resolution/experiment_v3/prioritizer.py",
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
    "study": "Competing Operative Resolution Experiment v0.1",
    "resolver_under_test": "HybridRelationshipResolver Experimental v0.5",
    "control": "C0 = Governance Semantics G3 (operative-source selection, no coarse abstention)",
    "ablation_order": ["C0_g3_control", "C1_extract", "C2_scope", "C3_classify", "C4_full"],
    "primary_endpoint": "selective_accuracy C4 vs C0 (+0.03), OR correct-abstention-recall "
                        "+0.10 with no false-abstention increase and no safety regression",
    "abstention_reasons": ["GENUINE_UNRESOLVED_CONFLICT", "INSUFFICIENT_SCOPE_EVIDENCE",
                           "OPERATIVE_TERM_NOT_LOCATED", "MULTIPLE_INCOMPATIBLE_OPERATIVE_TERMS",
                           "FROZEN_PACKET_CARDINALITY_LIMIT", "MISSING_DECISIVE_PROVENANCE"],
    "g3_fixes_that_must_be_retained": ["HX59d7a3eb1c", "HP059f01c294", "HP7d8d12efac",
                                       "HPb3463204c9", "HPebe6e8abf0"],
    "bootstrap_seed": 20240601, "bootstrap_iters": 10000,
    "repetitions": 2, "byte_identical_required": True,
    "note": "v0.1..v0.4 experiments and all frozen platform artifacts are unchanged; "
            "proposal, validation, governing set, and G3 operative selection are bit-identical.",
}


def _sha256(path):
    with open(os.path.join(ROOT, path), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def generate():
    v5 = {p: _sha256(p) for p in _V5_FILES}
    frz = {p: _sha256(p) for p in _FROZEN_FILES}
    manifest_hash = hashlib.sha256(json.dumps(MANIFEST, sort_keys=True).encode()).hexdigest()
    combined = hashlib.sha256(json.dumps(
        {"v5": v5, "frozen": frz, "manifest": manifest_hash}, sort_keys=True).encode()).hexdigest()
    return {"lock_version": LOCK_VERSION, "v5_hashes": v5, "frozen_hashes": frz,
            "manifest": MANIFEST, "manifest_hash": manifest_hash, "combined_lock_hash": combined}


def verify_prior_locks():
    from agentic.hybrid_handover.resolution.experiment import lock as l1
    from agentic.hybrid_handover.resolution.experiment_v2 import lock_v2 as l2
    from agentic.hybrid_handover.resolution.experiment_v3 import lock_v3 as l3
    from agentic.hybrid_handover.resolution.experiment_v4 import lock_v4 as l4
    return {"v0.1": l1.verify(), "v0.2": l2.verify(), "v0.3": l3.verify(), "v0.4": l4.verify()}


def write_lock_doc():
    lock = generate()
    prior = verify_prior_locks()
    lines = [
        "# COMPETING_OPERATIVE_HIDDEN_LOCK — Competing Operative Resolution Experiment v0.1", "",
        f"**Lock version:** `{lock['lock_version']}`  ",
        f"**Combined lock hash:** `{lock['combined_lock_hash']}`  ",
        f"**Manifest hash:** `{lock['manifest_hash']}`", "",
        "Computed BEFORE the first hidden evaluation of v0.5. The v0.4/v0.3/v0.2/v0.1",
        "experiments and all frozen platform artifacts are hashed here to prove they are",
        "unchanged.", "",
        "## Prior experiment locks (must verify zero drift)", "| experiment | drift |", "|---|---|"]
    for k, v in prior.items():
        lines.append(f"| {k} | {'none' if v == [] else v} |")
    lines += ["", "## Manifest", "```json", json.dumps(lock["manifest"], indent=2), "```", "",
              "## v0.5 source + spec hashes (SHA-256)", "| file | sha256 |", "|---|---|"]
    for p, h in lock["v5_hashes"].items():
        lines.append(f"| `{p.split('/')[-1]}` | `{h}` |")
    lines += ["", "## Frozen-dependency hashes (must be unchanged)", "| file | sha256 |", "|---|---|"]
    for p, h in lock["frozen_hashes"].items():
        lines.append(f"| `{'/'.join(p.split('/')[-2:])}` | `{h}` |")
    lines += ["", "## Calibration gates (all must pass before hidden eval)",
              "C0 control identity · C1 discovery · C2 classification · C3 validation ·",
              "C4 governing set · C5 G3 operative · C6 Mode P · C7 visible non-degradation ·",
              "C8 co-occurrence safety · C9 genuine-conflict activation.", ""]
    with open(os.path.join(HERE, "COMPETING_OPERATIVE_HIDDEN_LOCK.md"), "w") as f:
        f.write("\n".join(lines))
    with open(os.path.join(HERE, "COMPETING_OPERATIVE_HIDDEN_LOCK.json"), "w") as f:
        json.dump(lock, f, indent=2)
    return lock


def verify():
    path = os.path.join(HERE, "COMPETING_OPERATIVE_HIDDEN_LOCK.json")
    if not os.path.exists(path):
        return ["<no lock written>"]
    with open(path) as f:
        locked = json.load(f)
    drift = []
    for group in ("v5_hashes", "frozen_hashes"):
        for p, h in locked[group].items():
            if _sha256(p) != h:
                drift.append(p)
    return drift


if __name__ == "__main__":
    lk = write_lock_doc()
    print("combined_lock_hash:", lk["combined_lock_hash"])
