#!/usr/bin/env python3
"""Protocol lock for the readout diagnostic. Freezes — BEFORE any final/reserved seed — the exact R0-R3
definitions (hidden sizes + added-parameter counts), the readout training recipe, all seeds, the frozen
gate numbers, the conclusion logic, source hashes, the frozen base-parameter/checkpoint hash, the
dataset-generator hashes, and a proof that no final seed has run. Requires a byte-identical readout replay
on a non-reserved fixture and fails closed if the frozen-base hash changes."""
from __future__ import annotations

import hashlib
import json
import pathlib

import readout_config as C
import readout_run_lib as R
from readout_model import build_frozen_encoder
from readout_train import base_hash, param_hash
from readout_model import Readout

HERE = pathlib.Path(__file__).resolve().parent
RES = HERE / "results"
FROZEN_SOURCES = ["readout_model.py", "readout_config.py", "readout_train.py", "readout_run_lib.py",
                  "readout_gates.py", "readout_leakage.py"]
GEN_SOURCES = [pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1_temporal" / "temporal_task.py",
               pathlib.Path(__file__).resolve().parents[1] / "bindingslots_e1" / "models.py"]
FINAL_ARTIFACTS = ["final_per_seed.json", "readout_analysis.json", "final_report.json"]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    existing = [n for n in FINAL_ARTIFACTS if (RES / n).exists()]
    assert not existing, f"final artifacts already present before lock: {existing}"

    prior, prop = C.all_prior_seeds(), C.proposed_seeds()
    clash = sorted(prior & prop)
    assert not clash, f"seed collision with prior: {clash}"

    enc = build_frozen_encoder(verify=True)          # hash-verified vs committed temporal evidence
    frozen_base = base_hash(Readout(enc, "R0"))
    full_encoder_hash = param_hash(enc)

    # byte-identical readout replay on a NON-RESERVED (dev) fixture; frozen-base must be unchanged
    train_eps = C.build_train_episodes()
    det = R.determinism_replay(enc, train_eps, C.DEV_SEEDS[0], "R2")
    assert det["byte_identical"], "readout retrain not byte-identical; do not lock"
    assert base_hash(Readout(enc, "R0")) == frozen_base, "frozen-base hash changed; fail closed"

    dev = json.loads((RES / "dev_report.json").read_text())
    assert dev["frozen_base_unchanged_all"] and dev["determinism"]["byte_identical"] and \
        dev["oracle_equivariance"]["pass"] and dev["r1_r2_distinctness"]["distinct"] and \
        dev["readout_activity_ok"] and dev["leakage_all_pass"], "dev integrity failed; do not lock"

    lock = {
        "schema": "bindingslots_e1_readout/protocol_lock/v1",
        "locked_before": "first final/reserved seed",
        "arms": C.ARMS, "learned_arms": C.LEARNED_ARMS, "structural_arm": C.STRUCTURAL_ARM,
        "arm_definitions": {
            "R0": "frozen mean pooling; 0 params",
            "R1": f"single additive-attention head over frozen key-token embeddings, hidden={C.R1_HIDDEN}",
            "R2": f"two independent attention heads (hidden={C.R2_HIDDEN}) + linear proj(2d->d); heads discover separation",
            "R3": f"dual-head (hidden={C.R3_HIDDEN}) with FIXED schema slot masks (entity {{0,1}} / temporal {{2,3}}); structural prior; upper-bound only",
        },
        "hidden_sizes": {"R1": C.R1_HIDDEN, "R2": C.R2_HIDDEN, "R3": C.R3_HIDDEN},
        "added_params_per_arm": {a: R.added_params(enc, a) for a in C.ARMS},
        "training_recipe": {"steps": C.STEPS, "batch": C.BATCH, "lr": C.LR, "tau": C.TAU,
                            "optimizer": "Adam", "train_episodes": C.TRAIN_EPISODES,
                            "no_match_frac": C.TRAIN_NO_MATCH_FRAC, "readout_only": True,
                            "base_optimizer_step": False},
        "seeds": {"train": C.TRAIN_SEED, "dev": C.DEV_SEEDS, "final": C.FINAL_SEEDS,
                  "required_seeds_pass": C.REQUIRED_TO_PASS, "eval_n_per_split": C.EVAL_N_PER_SPLIT},
        "seed_disjoint_from_prior": True, "prior_seed_count": len(prior),
        "gates": C.GATES,
        "metric_conventions": {
            "T4_gated": "null-inclusive correct_latest",
            "inherited_splits_gated": "null-excluded addressing_top1",
            "improvement_baseline": "same-cohort R0 per seed",
            "T5": "reported diagnostic only; excluded from gates and conclusion",
        },
        "conclusion_logic": {
            "SIGNAL_PRESENT": "R1 or R2: >=4/5 seeds pass, mean T4>=0.75, mean impr over R0>=0.10, inherited+no-match+determinism+leakage pass; R3 can NEVER emit this",
            "SIGNAL_PARTIAL_learned": "R1 or R2: >=4/5 partial seeds, mean T4>=0.68, mean impr>=0.05, guards pass",
            "SIGNAL_PARTIAL_structural_only": "R3 reaches PRESENT bars while no learned arm reaches partial -> STRUCTURAL_PRIOR_ONLY_SIGNAL",
            "SIGNAL_NOT_FOUND": "neither learned arm partial and R3 not at present bars; integrity valid",
        },
        "selection_rule": ["fewer added parameters", "higher worst-seed T4", "higher mean T4",
                           "R3 never selectable as primary learned readout"],
        "conclusion_vocabulary": C.CONCLUSIONS,
        "structural_prior_only_flag": "STRUCTURAL_PRIOR_ONLY_SIGNAL",
        "always_preserve": C.PRESERVE, "never_emit": C.NEVER_EMIT,
        "frozen_source_sha256": {n: sha(HERE / n) for n in FROZEN_SOURCES},
        "dataset_generator_sha256": {p.name: sha(p) for p in GEN_SOURCES},
        "frozen_base_param_hash": frozen_base,
        "frozen_encoder_full_param_hash": full_encoder_hash,
        "frozen_encoder_seed": C.FROZEN_ENCODER_SEED,
        "byte_identical_readout_replay": det["byte_identical"],
        "no_final_seed_has_run": True,
    }
    p = R.write_json("protocol_lock.json", lock)
    print("PROTOCOL LOCKED ->", p)
    print("added params/arm:", lock["added_params_per_arm"], "| frozen_base:", frozen_base[:16],
          "| readout replay byte-identical:", det["byte_identical"])


if __name__ == "__main__":
    main()
