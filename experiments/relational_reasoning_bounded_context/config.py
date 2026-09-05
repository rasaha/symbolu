"""Frozen BTRR configuration (Amendment 002 effective authority).

Declarative and torch-free: importing this module initializes no model, generates no data, reads no
seed, and touches no filesystem. Numeric constants are the effective Amendment-002 limits.

Provenance chain (do not break):
  original preregistration   626a897a513eb7e415cde6fbaff10e9e922b8abb
  implementation blocker     f8dd65c5e734bc1f31eaf100e4069c050d014e8c
  amendment 001              9e6168f93c850acbf2bc134d5226aad1572c1add
  amendment 002 (effective)  a84cc8eef848e7081764deb894593f7b270f32ba
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Final

# ---- frozen representation capacity (Amendment 002) ----
VOCAB_SIZE: Final[int] = 211
INPUT_TOKEN_LIMIT: Final[int] = 3520
OUTPUT_TOKEN_LIMIT: Final[int] = 384
MAX_SEQ_LEN: Final[int] = 3904

# ---- frozen reasoning architecture (UNCHANGED across all amendments) ----
D_MODEL: Final[int] = 64
N_LAYERS: Final[int] = 2
N_HEADS: Final[int] = 4
D_FF: Final[int] = 256
DROPOUT: Final[float] = 0.0

# ---- frozen training recipe (UNCHANGED) ----
BATCH_SIZE: Final[int] = 8
MAX_UPDATES: Final[int] = 2000
LEARNING_RATE: Final[float] = 3e-4
BETA1: Final[float] = 0.9
BETA2: Final[float] = 0.95
EPSILON: Final[float] = 1e-8
WEIGHT_DECAY: Final[float] = 0.01
GRADIENT_CLIP: Final[float] = 1.0
IGNORE_INDEX: Final[int] = -100
OUTPUT_MARKER: Final[str] = "\n<OUTPUT>\n"

# ---- frozen legal-size caps (Amendment 002) ----
CAPS: Final = MappingProxyType({
    "max_entities": 12,
    "min_entities": 6,
    "max_events_per_entity": 4,
    "min_events_per_entity": 2,
    "max_events_total": 48,
    "max_relations": 20,
    "max_hops": 3,
    "max_policies": 4,
    "max_conditions_per_policy": 4,
    "max_evidence": 16,
    "max_attributes_per_entity": 3,
    "max_id_len": 6,
    "max_value_len_tokens": 9,
    "max_numeric_digits": 9,
    "max_sequence_digits": 2,
    "max_reasoning_path_nodes": 8,
    "max_evidence_ids_in_output": 16,
})

# ---- output contract ----
STATUS_VALUES: Final[tuple[str, ...]] = (
    "SUPPORTED", "INSUFFICIENT_EVIDENCE", "POLICY_NOT_APPLICABLE", "INVALID_RELATION_PATH",
)
OUTPUT_FIELDS: Final[tuple[str, ...]] = ("answer", "reasoning_path", "evidence_ids", "status")

# 8 symmetric outcome tokens + NULL (no single outcome privileged by tokenization).
OUTCOME_VOCAB: Final[tuple[str, ...]] = (
    "VP_APPROVAL_REQUIRED", "DIRECTOR_APPROVAL_REQUIRED", "AUTO_APPROVED", "MANUAL_REVIEW",
    "REJECTED", "ESCALATE_RISK", "HOLD_PENDING_EVIDENCE", "NO_ACTION",
)

# Keys that would leak the gold answer if model-visible. NOTE: a policy's `outcome` and a PATH_GIVEN
# `relation_chain` are legitimate visible facts (the policy definition; the supplied plan) and are NOT
# listed here; PATH_DISCOVERY strips relation_chain in visible_canonical() separately.
FORBIDDEN_MODEL_VISIBLE_KEYS: Final[frozenset[str]] = frozenset({
    "answer", "correct", "expected", "gold", "label", "split", "seed",
    "authoritative_output", "expect_status", "target_index", "arm",
})

# ---- reserved seeds (fail-closed; UNCONSUMED) ----
SMOKE_SEEDS: Final[frozenset[int]] = frozenset({8100})
DEVELOPMENT_SEEDS: Final[frozenset[int]] = frozenset({8101, 8102, 8103})
FINAL_SEEDS: Final[frozenset[int]] = frozenset({81600, 81601, 81602, 81603, 81604})
UNIT_FIXTURE_SEEDS: Final[frozenset[int]] = frozenset({883000, 883001, 883002, 883003, 883004})
RESERVED_SEED_ROLES: Final = MappingProxyType({
    **{s: "smoke" for s in SMOKE_SEEDS},
    **{s: "development" for s in DEVELOPMENT_SEEDS},
    **{s: "final" for s in FINAL_SEEDS},
})
FINAL_SEEDS_REQUIRED_TO_PASS: Final[int] = 4
FINAL_SEEDS_TOTAL: Final[int] = 5

# ---- frozen numeric scientific gates (unchanged; see preregistration §8) ----
NUMERIC_GATES: Final = MappingProxyType({
    "structured_output_validity": 0.98,
    "R1_direct_attribute": 0.95,
    "R2_path_given_1hop": 0.90,
    "R3_path_given_multihop": 0.85,
    "R4_path_discovery_multihop": 0.75,
    "entity_selection": 0.90,
    "relation_path_exact_ordered": 0.80,
    "latest_event": 0.85,
    "latest_event_effect_over_global_most_recent": 0.20,
    "policy_condition": 0.85,
    "evidence_precision": 0.90,
    "evidence_recall": 0.85,
    "abstention_R10_R11": 0.85,
    "false_abstention_on_answerable_max": 0.10,
    "hallucinated_entity_max": 0.02,
    "hallucinated_relation_max": 0.02,
    "hallucinated_evidence_max": 0.02,
    "R7_path_discovery_temporal": 0.72,
    "R9_composite_final_answer": 0.70,
    "R9_full_chain_correct": 0.60,
    "R12_confusable_min_relative_to_R9": -0.10,
    "structure_blind_margin": 0.10,
})

# ---- base-capability P0 gates ----
P0_SUBTASK_GATE: Final[float] = 0.98
P0_BLOCK_THRESHOLD: Final[float] = 0.95

# capacity_increase override (Amendment 002 §9A): permitted ONLY for lexical + sequence capacity.
CAPACITY_INCREASE_PERMITTED: Final[frozenset[str]] = frozenset({
    "tokenizer_vocabulary", "token_embedding_rows", "positional_embedding_rows",
})
CAPACITY_INCREASE_FORBIDDEN: Final[frozenset[str]] = frozenset({
    "reasoning_depth", "hidden_width", "attention_heads", "ffn_width",
    "attention_architecture", "specialized_reasoning_modules",
})


def backbone_param_count(vocab: int, max_seq: int,
                         d: int = D_MODEL, layers: int = N_LAYERS, d_ff: int = D_FF) -> tuple[int, int]:
    """Analytic parameter count for the weight-tied SoftmaxTransformerLM backbone (torch-free).

    Returns (total, reasoning_block_params). Reasoning blocks = layers*per_block + final RMSNorm;
    they exclude the token/positional embeddings (representation/sequence capacity).
    per_block = 2*d (two RMSNorm) + 4*d^2 (qkv 3d^2 + proj d^2) + 3*d*d_ff (SwiGLU w1,w2,wo).
    The output head is weight-tied to the token embedding, so it adds no parameters.
    """
    tok = vocab * d
    pos = max_seq * d
    per_block = 2 * d + 4 * d * d + 3 * d * d_ff
    reasoning_blocks = layers * per_block + d  # + final RMSNorm
    total = tok + pos + reasoning_blocks
    return total, reasoning_blocks


# expected effective (Amendment 002) and original reference numbers
EXPECTED_TOTAL_PARAMS: Final[int] = 394_752
EXPECTED_REASONING_BLOCK_PARAMS: Final[int] = 131_392
ORIGINAL_TOTAL_PARAMS: Final[int] = 209_728  # single-hop recipe (vocab 200, max_seq 1024)

# Mechanical assertions at import (fail fast if any frozen number drifts).
_t, _b = backbone_param_count(VOCAB_SIZE, MAX_SEQ_LEN)
assert _t == EXPECTED_TOTAL_PARAMS, (_t, EXPECTED_TOTAL_PARAMS)
assert _b == EXPECTED_REASONING_BLOCK_PARAMS, (_b, EXPECTED_REASONING_BLOCK_PARAMS)
# reasoning-block delta vs original single-hop recipe is exactly zero
assert backbone_param_count(200, 1024)[1] == EXPECTED_REASONING_BLOCK_PARAMS
assert _b - backbone_param_count(200, 1024)[1] == 0

PRESERVED_VERDICTS: Final[tuple[str, ...]] = (
    "ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED",
    "E1_TEMPORAL_TRANSFER_PARTIAL",
    "KDA_VALIDATION_BLOCKED",
)
FORBIDDEN_VERDICTS: Final[frozenset[str]] = frozenset({
    "ENTERPRISE_READY", "PRODUCTION_READY", "DATABASE_REPLACEMENT_VALIDATED",
    "BINDINGSLOTS_RESOLVED", "KDA_VALIDATION_ELIGIBLE", "AGI_VALIDATED",
})

# ---- sibling arms (BTRR_ROPE_SIBLING_ARM_PREREGISTRATION_DRAFT.md). ----
# BTRR-ABS is the frozen parent arm; every module-level constant above describes it and is unchanged.
# BTRR-RoPE differs in the positional mechanism ONLY (learned absolute table -> parameter-free rotary on
# Q/K) and carries its own frozen budget, dataset size, reserved seeds and authorization record.
# `ratified: False` marks values that are DRAFT until the owner ratifies the sibling preregistration.
ARM_ABS: Final[str] = "ABS"
ARM_ROPE: Final[str] = "ROPE"
ROPE_SMOKE_SEEDS: Final[frozenset[int]] = frozenset({8200})
ROPE_DEVELOPMENT_SEEDS: Final[frozenset[int]] = frozenset({8201, 8202, 8203})
ROPE_FINAL_SEEDS: Final[frozenset[int]] = frozenset({81700, 81701, 81702, 81703, 81704})
ARMS: Final = MappingProxyType({
    ARM_ABS: MappingProxyType({
        "name": "BTRR-ABS", "positional_mechanism": "learned_absolute", "rope_theta": None,
        "expected_total_params": 394_752, "expected_reasoning_block_params": 131_392,
        "max_updates": MAX_UPDATES, "n_train_per_split": None,   # dataset size unfrozen in the ABS protocol
        "seeds": MappingProxyType({"smoke": SMOKE_SEEDS, "development": DEVELOPMENT_SEEDS,
                                   "final": FINAL_SEEDS}),
        "record_file": "BTRR_EXECUTION_AUTHORIZATION_RECORD.json",
        "preregistration": "BOUNDED_TYPED_RELATIONAL_REASONING_PREREGISTRATION.md", "ratified": True,
    }),
    ARM_ROPE: MappingProxyType({
        "name": "BTRR-RoPE", "positional_mechanism": "rope", "rope_theta": 10000.0,
        "expected_total_params": 144_896, "expected_reasoning_block_params": 131_392,
        "max_updates": 15000, "n_train_per_split": 400,          # budget option (a), DRAFT
        "seeds": MappingProxyType({"smoke": ROPE_SMOKE_SEEDS, "development": ROPE_DEVELOPMENT_SEEDS,
                                   "final": ROPE_FINAL_SEEDS}),
        "record_file": "BTRR_ROPE_EXECUTION_AUTHORIZATION_RECORD.json",
        "preregistration": "BTRR_ROPE_SIBLING_ARM_PREREGISTRATION.json", "ratified": False,
    }),
})
RESERVED_SEED_ARM_ROLES: Final = MappingProxyType({
    s: (arm, role) for arm, spec in ARMS.items() for role, seeds in spec["seeds"].items() for s in seeds
})
_all_reserved = [s for spec in ARMS.values() for seeds in spec["seeds"].values() for s in seeds]
assert len(_all_reserved) == len(set(_all_reserved)), "reserved seeds overlap across arms/roles"
assert not (set(_all_reserved) & UNIT_FIXTURE_SEEDS), "reserved seeds collide with unit fixtures"


def arm_of_seed(seed: int) -> tuple[str, str] | None:
    """(arm, role) for a reserved seed; None for fixtures and any non-reserved seed."""
    return RESERVED_SEED_ARM_ROLES.get(int(seed))


def frozen_run_params(arm: str, seed: int, n_train: int | None, max_updates: int | None,
                      default_n_train: int = 6) -> tuple[int, int]:
    """Resolve (n_train_per_split, max_updates) for a run and enforce admissibility.

    A reserved seed may only be run under its own arm. On development/final seeds the arm's frozen values
    are mandatory: any differing override raises (inadmissible). On smoke and non-reserved seeds the
    frozen values are defaults that calibration may override."""
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    spec = ARMS[arm]
    owner = arm_of_seed(seed)
    if owner is not None and owner[0] != arm:
        raise ValueError(f"seed {seed} is reserved for arm {owner[0]}, not {arm}")
    frozen_n, frozen_u = spec["n_train_per_split"], spec["max_updates"]
    if owner is not None and owner[1] in ("development", "final"):
        if max_updates is not None and max_updates != frozen_u:
            raise ValueError(f"{spec['name']} {owner[1]} seed {seed}: max_updates={max_updates} is an "
                             f"inadmissible override of the frozen budget {frozen_u}")
        if frozen_n is not None and n_train is not None and n_train != frozen_n:
            raise ValueError(f"{spec['name']} {owner[1]} seed {seed}: n_train={n_train} is an inadmissible "
                             f"override of the frozen dataset size {frozen_n}")
    n = n_train if n_train is not None else (frozen_n if frozen_n is not None else default_n_train)
    u = max_updates if max_updates is not None else frozen_u
    return int(n), int(u)


def arm_param_count(arm: str) -> tuple[int, int]:
    """(total, reasoning_block) analytic parameter count for an arm (torch-free)."""
    total, blocks = backbone_param_count(VOCAB_SIZE, MAX_SEQ_LEN)
    if ARMS[arm]["positional_mechanism"] == "rope":
        total -= MAX_SEQ_LEN * D_MODEL            # no learned position table
    return total, blocks


for _arm, _spec in ARMS.items():
    assert arm_param_count(_arm) == (_spec["expected_total_params"], _spec["expected_reasoning_block_params"]), _arm
