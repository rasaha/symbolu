"""Frozen configuration for the controlled typed-vs-prose implementation.

This module is declarative. Importing it does not initialize a model, generate data,
write files, access the network, or authorize a benchmark run.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

# Special-token IDs and the frozen vocabulary size live with the tokenizer; re-exported
# here as the single import surface used by the model and tests. (tokenizer imports nothing
# from this package, so this does not create an import cycle.)
from .tokenizer import PAD_ID, BOS_ID, EOS_ID  # noqa: F401  (re-exported)

VOCAB_SIZE: Final[int] = 200


@dataclass(frozen=True)
class ModelRecipe:
    vocab_size: int = 200
    d_model: int = 64
    n_layers: int = 2
    n_heads: int = 4
    d_ff: int = 256
    max_seq: int = 1024
    dropout: float = 0.0
    max_input_tokens: int = 512
    max_output_tokens: int = 384

    def validate(self) -> None:
        if self.vocab_size != 200:
            raise ValueError("the frozen lexical vocabulary contains exactly 200 IDs")
        if self.d_model <= 0 or self.d_model % self.n_heads:
            raise ValueError("d_model must be positive and divisible by n_heads")
        if self.n_layers <= 0 or self.d_ff <= 0 or self.max_seq <= 0:
            raise ValueError("model dimensions must be positive")
        if self.dropout != 0.0:
            raise ValueError("dropout is frozen at zero")


@dataclass(frozen=True)
class TrainRecipe:
    input_token_limit: int = 512
    output_token_limit: int = 384
    batch_size: int = 8
    maximum_updates: int = 2000
    learning_rate: float = 3e-4
    beta1: float = 0.9
    beta2: float = 0.95
    epsilon: float = 1e-8
    weight_decay: float = 0.01
    gradient_clip: float = 1.0
    ignore_index: int = -100
    output_marker: str = "\n<OUTPUT>\n"

    def validate(self) -> None:
        if self.input_token_limit != 512 or self.output_token_limit != 384:
            raise ValueError("the common input/output token limits are frozen")
        if self.batch_size != 8 or self.maximum_updates != 2000:
            raise ValueError("batch size and update ceiling are frozen")
        if self.output_marker != "\n<OUTPUT>\n":
            raise ValueError("the shared output marker is frozen")


FROZEN_MODEL_RECIPE: Final = ModelRecipe()
FROZEN_TRAIN_RECIPE: Final = TrainRecipe()
FROZEN_MODEL_RECIPE.validate()
FROZEN_TRAIN_RECIPE.validate()

SMOKE_SEEDS: Final[frozenset[int]] = frozenset({76})
DEVELOPMENT_SEEDS: Final[frozenset[int]] = frozenset({760, 761, 762})
FINAL_SEEDS: Final[frozenset[int]] = frozenset({7160, 7161, 7162, 7163, 7164})
RESERVED_SEED_ROLES: Final = MappingProxyType(
    {
        76: "smoke",
        760: "development",
        761: "development",
        762: "development",
        7160: "final",
        7161: "final",
        7162: "final",
        7163: "final",
        7164: "final",
    }
)

# Unit fixtures are mechanical implementation checks and are inadmissible as
# benchmark evidence. This seed is intentionally outside every reserved range.
UNIT_TEST_SEED: Final[int] = 99001

# Execution-authorization tokens. The reserved seed gate stays fail-closed until a
# caller supplies the matching token for the seed's role. These are populated because
# execution of this benchmark was explicitly authorized by the repository owner (see
# EXECUTION_AUTHORIZATION.md). They are NOT a default-open gate: a caller must pass the
# exact ExecutionAuthorization(role, token) to run a reserved seed.
SMOKE_AUTHORIZATION_TOKEN: Final[str] = "smoke-exec-auth-2026-08-typed-vs-prose"
DEVELOPMENT_AUTHORIZATION_TOKEN: Final[str] = "dev-exec-auth-2026-08-typed-vs-prose"
FINAL_AUTHORIZATION_TOKEN: Final[str] = "final-exec-auth-2026-08-typed-vs-prose"

SCENARIO_IDS: Final[tuple[str, ...]] = tuple(f"S{i}" for i in range(1, 9))
ABLATION_IDS: Final[tuple[str, ...]] = tuple(f"A{i}" for i in range(1, 7))

STATUS_VALUES: Final[tuple[str, ...]] = ("ANSWERED", "INSUFFICIENT_EVIDENCE")
OUTPUT_FIELDS: Final[tuple[str, ...]] = (
    "status",
    "selected_entity_id",
    "selected_relation_type",
    "relation_supported",
    "evidence_refs",
    "tenant_id",
    "reason_code",
)

FORBIDDEN_MODEL_VISIBLE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "answer",
        "correct",
        "expected",
        "gold",
        "label",
        "split",
        "seed",
        "target_rank",
        "validity_result",
        "arm",
    }
)
