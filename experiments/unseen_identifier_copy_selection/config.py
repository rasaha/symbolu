"""Frozen configuration for the unseen-identifier copy/selection diagnostic.

Declarative only. Importing this module does not generate data, initialize a model, train,
write files, access the network, or authorize execution. The model/optimizer recipe is REUSED
by import from the merged typed-vs-prose benchmark (never redefined here).

Scope reminder (see the merged protocol lock and implementation authorization):
  * exact-identifier output only; NO candidate-index output, NO constrained decoding, NO ranking.
  * reserved diagnostic seeds are fail-closed; unit fixtures use a separate testing namespace.
"""
from __future__ import annotations

from typing import Final

# Reuse the exact frozen recipe from the merged benchmark (imported, not redefined).
from experiments.single_hop_typed_vs_prose.config import (  # noqa: F401  (re-exported)
    FROZEN_MODEL_RECIPE,
    FROZEN_TRAIN_RECIPE,
)

# ---- task splits ----
SPLIT_IDS: Final[tuple[str, ...]] = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8")
# Splits whose graded output is a positive exact identifier (vs. abstention for C8).
EXACT_ID_SPLITS: Final[frozenset[str]] = frozenset({"C1", "C2", "C3", "C4", "C5", "C6", "C7"})
ABSTENTION_SPLITS: Final[frozenset[str]] = frozenset({"C8"})

# ---- frozen identifier design (protocol-lock Decision 3) ----
IDENTIFIER_ALPHABET: Final[str] = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
IDENTIFIER_LENGTH: Final[int] = 4
CANDIDATE_COUNT: Final[int] = 3  # source->target pairs presented in selection splits
ABSTENTION_TOKEN: Final[str] = "INSUFFICIENT_EVIDENCE"

# ---- frozen split example counts (fixed here from the locked design) ----
EXAMPLES_PER_SPLIT: Final[int] = 60
POSITIONS: Final[tuple[str, ...]] = ("first", "middle", "last")

# ---- arm-neutral evaluation decode cap (never truncates a valid identifier) ----
# A valid output is a 4-character identifier (4 tokens) or the abstention token; 32 is a generous
# bound that cannot truncate either and is identical for all splits. Evaluation-efficiency only.
EVAL_OUTPUT_TOKENS: Final[int] = 32

# ---- seed roles (protocol-lock Decision 10). PROPOSED / reserved; fail-closed until a separate
# execution authorization exists (there is none: the token registry is intentionally empty). ----
SMOKE_SEEDS: Final[frozenset[int]] = frozenset({9070})
DEVELOPMENT_SEEDS: Final[frozenset[int]] = frozenset({9071, 9072, 9073})
FINAL_SEEDS: Final[frozenset[int]] = frozenset({90760, 90761, 90762, 90763, 90764})
RESERVED_SEEDS: Final[frozenset[int]] = SMOKE_SEEDS | DEVELOPMENT_SEEDS | FINAL_SEEDS

# Separate testing namespace for unit fixtures (mechanically verified unused; never a reserved seed).
FIXTURE_SEEDS: Final[tuple[int, ...]] = (993000, 993001, 993002, 993003, 993004)

# ---- frozen domain-separated sub-seed derivation (mirrors the typed-vs-prose discipline) ----
_DOMAIN_ID: Final[dict[str, int]] = {
    "identifier_pools": 0,
    "dataset": 1,
    "init": 2,
    "batch": 3,
    "perturb": 4,
    "position": 5,
}


def sub_seed(seed: int, domain: str) -> int:
    """Deterministic domain-separated sub-seed: seed*1_000_003 + DOMAIN_ID*97 + 13."""
    if domain not in _DOMAIN_ID:
        raise ValueError(f"unknown sub-seed domain: {domain}")
    return int(seed) * 1_000_003 + _DOMAIN_ID[domain] * 97 + 13
