"""Protocol lock digest for E1-S: binds vocabulary geometry, density ladder, recipe, gates, seeds, profiles,
splits and the ratified E1 source digests. Changing any of them invalidates every signed authorization."""
from __future__ import annotations

import hashlib
import json

from . import config as C
from . import keyspace as KS
from .e1_import import E1_SOURCE_SHA256


def config_payload() -> dict:
    return {
        "arm": C.ARM_NAME, "ratified": C.RATIFIED, "ratified_on": C.RATIFIED_ON,
        "e1_source_sha256": dict(E1_SOURCE_SHA256),
        "vocab": {"VOCAB": KS.VOCAB, "N_ST": KS.N_ST, "N_REL": KS.N_REL, "N_OT": KS.N_OT, "SYN": KS.SYN,
                  "ID_PRIMS": KS.ID_PRIMS, "N_VALUES": KS.N_VALUES, "N_FILLER": KS.N_FILLER,
                  "KLEN": KS.KLEN, "QLEN": KS.QLEN, "PAD": KS.PAD, "SEP": KS.SEP},
        "densities": list(C.DENSITIES), "anchor_density": C.ANCHOR_DENSITY, "primary_density": C.PRIMARY_DENSITY,
        "recipe": {"D": C.D, "steps": C.STEPS, "tau": C.TAU, "train_no_match_frac": C.TRAIN_NO_MATCH_FRAC,
                   "batch": C.BATCH, "lr": C.LR, "train_episodes": C.TRAIN_EPISODES,
                   "train_seed_for_episodes": C.TRAIN_SEED_FOR_EPISODES, "eval_n_per_split": C.EVAL_N_PER_SPLIT},
        "profiles": {k: list(v) for k, v in KS.PROFILES.items()},
        "splits": {k: list(v[:4]) for k, v in KS.EVAL_SPLITS.items()},
        "gates": dict(C.GATES),
        "seeds": {"development": sorted(C.DEVELOPMENT_SEEDS), "final": sorted(C.FINAL_SEEDS),
                  "fixtures": sorted(C.UNIT_FIXTURE_SEEDS)},
        "final_seeds_required_to_pass": C.FINAL_SEEDS_REQUIRED_TO_PASS,
        "expected_e1_params": C.EXPECTED_E1_PARAMS,
        "pool_salt": "e1s_pool_v1",
    }


def config_digest() -> str:
    return hashlib.sha256(json.dumps(config_payload(), sort_keys=True).encode("utf-8")).hexdigest()
