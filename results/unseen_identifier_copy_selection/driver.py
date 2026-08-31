"""Execution driver for the unseen-identifier copy/selection diagnostic.

This driver ONLY orchestrates the frozen, merged building blocks (build_cohort, shortcut_scores,
train_cohort, evaluate_cohort, metrics, manifest, evidence). It changes NO protocol or implementation
code. It mirrors the phase-scoped CLI control flow: validate_phase_seed() first, then the primitive
guards are threaded the declared phase as `token`, exactly like cli.py._handle.

For a (phase, seed):
  * build seen + unseen cohorts (all C1-C8),
  * compute per-split structure-blind shortcut baselines for both cohorts,
  * train the frozen 209,728-param model on the SEEN cohort (2000 updates),
  * greedy-decode + classify every example for both cohorts,
  * compute per-split metrics,
  * assemble a canonical run manifest with ACTUAL digests per evaluated cohort,
  * write per-example traces + manifest atomically under the run dir.

Returns a compact summary dict for gate reconstruction. NO capability verdict is computed here.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time

import torch

from experiments.unseen_identifier_copy_selection.config import SPLIT_IDS, sub_seed
from experiments.unseen_identifier_copy_selection.evaluation import evaluate_cohort
from experiments.unseen_identifier_copy_selection.evidence import write_run_evidence
from experiments.unseen_identifier_copy_selection.execution import validate_phase_seed
from experiments.unseen_identifier_copy_selection.identifiers import build_pools
from experiments.unseen_identifier_copy_selection.manifest import (
    build_run_manifest,
    dataset_digest,
    digest_json,
    frozen_recipe_source_hashes,
    sha256_text,
)
from experiments.unseen_identifier_copy_selection import metrics as M
from experiments.unseen_identifier_copy_selection.parser import parse
from experiments.unseen_identifier_copy_selection.runner import build_cohort
from experiments.unseen_identifier_copy_selection.serializer import serialize
from experiments.unseen_identifier_copy_selection.shortcuts import shortcut_scores
from experiments.unseen_identifier_copy_selection.training import train_cohort

SOURCE_COMMIT = "b73a9f1e3cabe5f26bcc9a3a15f20d5519347baa"
IMPL_COMMIT = "69f8b492405072d58adaf103094c189bb72938f5"
PROTOCOL_LOCK_COMMIT = "872c034cd44179c59858c1f87ff08832cb4aa32c"  # preregistration merge (Decision 6 source)
AUTH_DOC = "docs/research/hybrid_llm/benchmarks/UNSEEN_IDENTIFIER_COPY_SELECTION_SMOKE_DEV_EXECUTION_AUTHORIZATION.md"


def _env_digest() -> str:
    return sha256_text(
        json.dumps(
            {
                "python": sys.version.split()[0],
                "torch": torch.__version__,
                "platform": platform.platform(),
                "machine": platform.machine(),
            },
            sort_keys=True,
        )
    )


def _pairs(cohort_by_split, traces_by_hash):
    """Rebuild (Example, ParseResult) pairs per split from stored traces (raw outputs)."""
    out = {}
    for split, examples in cohort_by_split.items():
        pl = []
        for e in examples:
            raw = traces_by_hash[e.example_hash]["raw_output"]
            pl.append((e, parse(raw, e)))
        out[split] = pl
    return out


def run_phase_seed(phase: str, seed: int, out_root: str, *, write: bool = True) -> dict:
    validate_phase_seed(phase, seed)  # protocol boundary, exactly as the CLI does
    t0 = time.time()

    # ---- cohorts (both seen and unseen); training uses the seen (train-pool) cohort ----
    seen = build_cohort(seed, "seen", token=phase)
    unseen = build_cohort(seed, "unseen", token=phase)
    seen_examples = [e for s in SPLIT_IDS for e in seen[s]]
    unseen_examples = [e for s in SPLIT_IDS for e in unseen[s]]

    # ---- shortcut baselines (pre-reserved gate machinery) ----
    sc_seen = shortcut_scores(seen_examples)
    sc_unseen = shortcut_scores(unseen_examples)

    # ---- identifier pool digest (disjointness provenance) ----
    pools = build_pools(seed, token=phase)
    pool_digest = digest_json({k: list(v) for k, v in pools.items()})

    recipe_hashes = frozen_recipe_source_hashes()

    # ---- train on the seen cohort ----
    ckpt_dir = os.path.join(out_root, f"seed{seed}_ckpt")
    os.makedirs(ckpt_dir, exist_ok=True)
    art = train_cohort(seed, "seen", seen_examples, ckpt_dir, recorded_hashes=recipe_hashes, device="cpu")
    ckpt_path = art.checkpoint_path

    # ---- evaluate on both cohorts ----
    ev_seen = evaluate_cohort(ckpt_path, seen, device="cpu")
    ev_unseen = evaluate_cohort(ckpt_path, unseen, device="cpu")

    traces_seen = {t["example_hash"]: t for t in ev_seen.traces}
    traces_unseen = {t["example_hash"]: t for t in ev_unseen.traces}
    pairs_seen = _pairs(seen, traces_seen)
    pairs_unseen = _pairs(unseen, traces_unseen)

    def per_split(pairs_by_split):
        return {s: M.split_metrics(s, pairs_by_split[s]).__dict__ for s in SPLIT_IDS}

    metrics_seen = per_split(pairs_seen)
    metrics_unseen = per_split(pairs_unseen)

    wall = time.time() - t0

    def manifest_for(eval_cohort, serialized, ev, pred_digest, cat_counts, per_task):
        digests = {
            "source_digest": digest_json(recipe_hashes),
            "config_digest": sha256_text(open("experiments/unseen_identifier_copy_selection/config.py").read()),
            "tokenizer_digest": recipe_hashes["tokenizer.py"],
            "authorization_record_digest": sha256_text(open(AUTH_DOC).read()),
            "identifier_pool_digest": pool_digest,
            "dataset_digest": dataset_digest(serialized),
            "serializer_digest": art.serializer_digest,
            "initialization_digest": art.initialization_digest,
            "batch_order_digest": art.batch_order_digest,
            "checkpoint_parameter_digest": art.checkpoint_parameter_digest,
            "prediction_digest": pred_digest,
            "evaluator_digest": sha256_text(open("experiments/unseen_identifier_copy_selection/evaluation.py").read()),
            "environment_digest": _env_digest(),
        }
        return build_run_manifest(
            seed=seed, cohort=eval_cohort, source_commit=SOURCE_COMMIT,
            protocol_lock_commit=PROTOCOL_LOCK_COMMIT,
            implementation_authorization_commit=SOURCE_COMMIT,
            implementation_commit=IMPL_COMMIT,
            digests=digests, parser_category_counts=cat_counts, per_task_metrics=per_task,
            shortcut_results=(sc_seen if eval_cohort == "seen" else sc_unseen),
            resource_measurements={"wall_clock_s": round(wall, 3), "updates": art.updates,
                                   "train_examples": len(seen_examples), "training_cohort_seen": 1.0},
            protocol_compliance={"phase_seed_validated": True, "trained_on_seen": True,
                                 "no_final_seed": True, "one_seed_per_invocation": True},
        )

    ser_seen = [serialize(e) for e in seen_examples]
    ser_unseen = [serialize(e) for e in unseen_examples]
    man_seen = manifest_for("seen", ser_seen, ev_seen, ev_seen.prediction_digest,
                            ev_seen.parser_category_counts, metrics_seen)
    man_unseen = manifest_for("unseen", ser_unseen, ev_unseen, ev_unseen.prediction_digest,
                              ev_unseen.parser_category_counts, metrics_unseen)

    if write:
        write_run_evidence(out_root, seed=seed, cohort="seen",
                           traces=list(ev_seen.traces), manifest=man_seen)
        write_run_evidence(out_root, seed=seed, cohort="unseen",
                           traces=list(ev_unseen.traces), manifest=man_unseen)

    return {
        "phase": phase, "seed": seed, "wall_clock_s": round(wall, 3),
        "updates": art.updates, "first_loss": art.first_loss, "final_loss": art.final_loss,
        "train_examples": len(seen_examples),
        "digests": {
            "dataset_seen": dataset_digest(ser_seen), "dataset_unseen": dataset_digest(ser_unseen),
            "identifier_pool": pool_digest,
            "initialization": art.initialization_digest, "batch_order": art.batch_order_digest,
            "checkpoint_parameter": art.checkpoint_parameter_digest,
            "prediction_seen": ev_seen.prediction_digest, "prediction_unseen": ev_unseen.prediction_digest,
            "manifest_seen": man_seen["manifest_digest"], "manifest_unseen": man_unseen["manifest_digest"],
        },
        "shortcut": {"seen_all_pass": sc_seen["all_pass"], "unseen_all_pass": sc_unseen["all_pass"],
                     "chance": sc_seen["chance"], "bound": sc_seen["bound"]},
        "metrics_seen": metrics_seen, "metrics_unseen": metrics_unseen,
        "category_counts_seen": ev_seen.parser_category_counts,
        "category_counts_unseen": ev_unseen.parser_category_counts,
    }


if __name__ == "__main__":
    phase, seed, out_root = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    summary = run_phase_seed(phase, seed, out_root, write=(os.environ.get("NOWRITE") != "1"))
    os.makedirs(out_root, exist_ok=True)
    with open(os.path.join(out_root, f"summary_seed{seed}.json"), "w") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
    print(json.dumps({k: summary[k] for k in ("phase", "seed", "wall_clock_s", "updates",
                                              "first_loss", "final_loss", "shortcut")}, indent=2))
