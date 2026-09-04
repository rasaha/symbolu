"""Frozen E1-S protocol configuration (ratified 2026-09-04; owner decisions [1]-[5] filled).

Recipe values are E1's frozen selection C1 (steps 1200, tau 0.07, train no-match 0.30, batch 48, lr 1e-3,
D 64) carried unchanged to every density. Gates are E1's absolute bars carried UNCHANGED (decision [4]:
strictly harder at higher density) plus G8. Everything in this module is bound by manifest.config_digest().
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Final

from . import keyspace as KS

ARM_NAME: Final[str] = "E1-S"
RATIFIED: Final[bool] = True
RATIFIED_ON: Final[str] = "2026-09-04"

# ---- frozen model / training recipe (E1 selection C1, unchanged) ----
D: Final[int] = 64
STEPS: Final[int] = 1200
TAU: Final[float] = 0.07
TRAIN_NO_MATCH_FRAC: Final[float] = 0.30
BATCH: Final[int] = 48
LR: Final[float] = 1e-3
TRAIN_EPISODES: Final[int] = 1500
TRAIN_SEED_FOR_EPISODES: Final[int] = 7
EVAL_N_PER_SPLIT: Final[int] = 200          # draft §4: >= 200 queries per split per seed

# ---- density ladder (decision [2]) ----
DENSITIES: Final[tuple] = KS.DENSITIES      # (32, 128, 512)
ANCHOR_DENSITY: Final[int] = 32             # replication anchor: must pass all primary gates
PRIMARY_DENSITY: Final[int] = 512

# ---- seeds (decision [3]); disjoint from every prior block (see draft §8) ----
DEVELOPMENT_SEEDS: Final[frozenset] = frozenset({6100, 6101, 6102})
FINAL_SEEDS: Final[frozenset] = frozenset({6140, 6141, 6142, 6143, 6144})
UNIT_FIXTURE_SEEDS: Final[frozenset] = frozenset({886000, 886001, 886002, 886003, 886004})
RESERVED_SEED_ROLES: Final = MappingProxyType({**{s: "development" for s in DEVELOPMENT_SEEDS},
                                               **{s: "final" for s in FINAL_SEEDS}})
FINAL_SEEDS_REQUIRED_TO_PASS: Final[int] = 4
PRIOR_SEED_BLOCKS: Final[tuple] = (            # must never be consumed by this line
    ("bindingslots_e1 reserved", (3140, 3141, 3142, 3143, 3144)),
    ("bindingslots_e1_confirmation final", (5140, 5141, 5142, 5143, 5144)),
    ("bindingslots_e1 dev", (500, 501, 502)), ("bindingslots_e1 burned", (2028, 2029, 2030, 2031, 2032)),
    ("bindingslots_address_generalization", tuple(range(0, 33)) + (99991,)),
    ("BTRR ABS", (8100, 8101, 8102, 8103, 81600, 81601, 81602, 81603, 81604)),
    ("BTRR RoPE", (8200, 8201, 8202, 8203, 81700, 81701, 81702, 81703, 81704)),
    ("BTRR fixtures", (883000, 883001, 883002, 883003, 883004)),
)
_prior = {s for _, block in PRIOR_SEED_BLOCKS for s in block}
assert not (_prior & (DEVELOPMENT_SEEDS | FINAL_SEEDS | UNIT_FIXTURE_SEEDS)), "E1-S seeds collide with a prior block"

# ---- frozen gates: E1 config.GATES carried unchanged + G8 (decision [4]) ----
GATES: Final = MappingProxyType({
    "G1_unseen_identity_min_addr": 0.80,
    "G2_paraphrase_min_addr": 0.80,
    "G3_hard_names_min_addr": 0.80,
    "G4_same_entity_diff_attr_min_addr": 0.75,
    "G5_recombined_min_addr": 0.80,
    "G8_unseen_composition_min_addr": 0.80,
    "nomatch_max_false_accept": 0.30,
    "nomatch_min_recall": 0.70,
    "nomatch_min_precision": 0.70,
    "nomatch_max_confident_false_accept": 0.20,
    "valid_max_false_reject": 0.15,
    "min_answer_availability": 0.80,
    "min_ordinary_retrieval_accuracy": 0.70,
    "min_improvement_over_b0": 0.50,
    "min_oracle_key_value_accuracy": 0.99,
    "max_oracle_to_predicted_gap": 0.30,
    "min_G7_stable_addr": 0.90,
    "worst_seed_min_G1_addr": 0.70,
    "structure_blind_margin": 0.10,          # draft §5 rule 4 (BTRR F13 margin rule)
    "lexical_overlap_max_accuracy": 0.30,    # id-verbatim design: overlap matcher must stay near 1/(n_same_subject+1)
})

# ---- verdict vocabulary (draft §7) ----
VERDICTS: Final[tuple] = ("EXPLICIT_KEY_SCALEUP_VALIDATED", "EXPLICIT_KEY_SCALEUP_DENSITY_LIMITED",
                          "EXPLICIT_KEY_SCALEUP_NOMATCH_FAILED", "EXPLICIT_KEY_SCALEUP_NOT_VALIDATED",
                          "SHORTCUT_OR_LEAKAGE_DETECTED", "EXPLICIT_KEY_DETERMINISM_NOT_ESTABLISHED",
                          "EXPLICIT_KEY_PROTOCOL_VIOLATED")
PRESERVED_VERDICTS: Final[tuple] = ("ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED",
                                    "E1_TEMPORAL_TRANSFER_PARTIAL", "KDA_VALIDATION_BLOCKED")
FORBIDDEN_VERDICTS: Final[frozenset] = frozenset({
    "E1_TEMPORAL_TRANSFER_VALIDATED", "E1_STRUCTURAL_TRANSFER_CONFIRMED", "E1_FOLLOW_ON_RESEARCH_ELIGIBLE",
    "KDA_VALIDATION_ELIGIBLE", "ENTERPRISE_READY", "PRODUCTION_READY", "BINDINGSLOTS_RESOLVED"})


def e1_param_count(vocab: int = KS.VOCAB, d: int = D) -> int:
    """embed V*d + key_head (d*d+d) + query_head (d*d+d) + null_key d."""
    return vocab * d + 2 * (d * d + d) + d


def b0_param_count(K: int, vocab: int = KS.VOCAB, d: int = D, n_values: int = KS.N_VALUES) -> int:
    """embed V*d + slot_keys K*d + value_write/fact_proj/query_proj 3*(d*d+d) + value_decoder d*nv+nv."""
    return vocab * d + K * d + 3 * (d * d + d) + (d * n_values + n_values)


EXPECTED_E1_PARAMS: Final[int] = e1_param_count()     # 22,848 at VOCAB 226
