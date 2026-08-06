"""Frozen mechanical configuration for the single-hop typed-vs-prose harness."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

ASCII_VOCAB_SIZE: Final[int] = 128
PAD_ID: Final[int] = 128
BOS_ID: Final[int] = 129
EOS_ID: Final[int] = 130
LEXEME_BASE_ID: Final[int] = 131

FROZEN_LEXEMES: Final[tuple[str, ...]] = (
    "ANSWERED",
    "INSUFFICIENT_EVIDENCE",
    "Within",
    "The",
    "Evidence",
    "No",
    "tenant",
    "the",
    "following",
    "records",
    "are",
    "authorized",
    "question",
    "concerns",
    "invoice",
    "contract",
    "vendor",
    "is",
    "a",
    "with",
    "no",
    "listed",
    "attributes",
    "belongs",
    "to",
    "different",
    "and",
    "not",
    "here",
    "associated",
    "through",
    "relation",
    "reference",
    "supports",
    "between",
    "of",
    "type",
    "recorded",
    "for",
    "amount",
    "status",
    "active",
    "pending",
    "name",
    "suffix",
    "tenant_id",
    "query",
    "entity_type",
    "entity_id",
    "relation_type",
    "entities",
    "relations",
    "evidence",
    "source_entity_type",
    "source_entity_id",
    "target_entity_type",
    "target_entity_id",
    "evidence_ref",
    "supports_relation",
    "selected_entity_id",
    "selected_relation_type",
    "relation_supported",
    "evidence_refs",
    "reason_code",
    "belongs_to_contract",
    "references_contract",
    "null",
    "true",
    "false",
)
if len(FROZEN_LEXEMES) != len(set(FROZEN_LEXEMES)):
    raise RuntimeError("FROZEN_LEXEMES must be unique")
VOCAB_SIZE: Final[int] = LEXEME_BASE_ID + len(FROZEN_LEXEMES)
OUTPUT_MARKER: Final[str] = "\n<OUTPUT>\n"

SMOKE_SEED: Final[int] = 76
DEVELOPMENT_SEEDS: Final[frozenset[int]] = frozenset({760, 761, 762})
FINAL_SEEDS: Final[frozenset[int]] = frozenset({7160, 7161, 7162, 7163, 7164})
RESERVED_SEEDS: Final[frozenset[int]] = frozenset({SMOKE_SEED, *DEVELOPMENT_SEEDS, *FINAL_SEEDS})

SMOKE_AUTHORIZATION_TOKEN: Final[str] = "SMOKE_EXECUTION_AUTHORIZED"
DEVELOPMENT_AUTHORIZATION_TOKEN: Final[str] = "DEVELOPMENT_EXECUTION_AUTHORIZED"
FINAL_AUTHORIZATION_TOKEN: Final[str] = "FINAL_EXECUTION_AUTHORIZED"


@dataclass(frozen=True)
class ModelRecipe:
    vocab_size: int = VOCAB_SIZE
    d_model: int = 64
    n_layers: int = 2
    n_heads: int = 4
    d_ff: int = 256
    max_seq: int = 1024
    dropout: float = 0.0
    max_input_tokens: int = 512
    max_output_tokens: int = 384

    def validate(self) -> None:
        if self.vocab_size != VOCAB_SIZE:
            raise ValueError(f"vocab_size must remain {VOCAB_SIZE}")
        if self.d_model % self.n_heads:
            raise ValueError("d_model must be divisible by n_heads")
        required = 1 + self.max_input_tokens + self.max_output_tokens + 1
        if self.max_seq < required:
            raise ValueError(f"max_seq={self.max_seq} is below required bound {required}")
        if self.dropout != 0.0:
            raise ValueError("dropout must remain zero for deterministic paired runs")


@dataclass(frozen=True)
class TrainRecipe:
    learning_rate: float = 3e-4
    beta1: float = 0.9
    beta2: float = 0.95
    epsilon: float = 1e-8
    weight_decay: float = 0.01
    gradient_clip: float = 1.0
    batch_size: int = 8
    max_updates: int = 2000

    def validate(self) -> None:
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")
        if not (0 < self.beta1 < 1 and 0 < self.beta2 < 1):
            raise ValueError("AdamW betas must lie in (0, 1)")
        if self.batch_size <= 0 or self.max_updates <= 0:
            raise ValueError("batch_size and max_updates must be positive")
        if self.gradient_clip <= 0:
            raise ValueError("gradient_clip must be positive")


FROZEN_MODEL_RECIPE: Final[ModelRecipe] = ModelRecipe()
FROZEN_TRAIN_RECIPE: Final[TrainRecipe] = TrainRecipe()
FROZEN_MODEL_RECIPE.validate()
FROZEN_TRAIN_RECIPE.validate()
