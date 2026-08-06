"""Unseen-identifier copy/selection diagnostic — bounded package.

Importing this package has NO side effects: it does not generate data, initialize or train a model,
consume a seed, write files, or authorize execution. It reuses the exact frozen model/tokenizer/
trainer/config from the merged typed-vs-prose benchmark by import (never redefined or copied).

Exact-identifier output only. NO candidate-index output, NO constrained decoding, NO ranking
objective, NO pointer/copy head, NO capacity/tokenizer change. Reserved seeds are fail-closed;
unit fixtures use a separate testing seed namespace.
"""
from __future__ import annotations

from .config import (
    FIXTURE_SEEDS,
    FROZEN_MODEL_RECIPE,
    FROZEN_TRAIN_RECIPE,
    RESERVED_SEEDS,
    SPLIT_IDS,
    sub_seed,
)
from .execution import ExecutionNotAuthorized, require_execution_authorization
from .identifiers import generate_pool
from .metrics import split_metrics
from .parser import OutputCategory, parse
from .serializer import serialize
from .shortcuts import shortcut_precheck, shortcut_scores
from .tasks import Example, generate_split
from .verdict import VerdictInputs, evaluate

__all__ = [
    "FIXTURE_SEEDS", "FROZEN_MODEL_RECIPE", "FROZEN_TRAIN_RECIPE", "RESERVED_SEEDS", "SPLIT_IDS",
    "sub_seed", "ExecutionNotAuthorized", "require_execution_authorization", "generate_pool",
    "split_metrics", "OutputCategory", "parse", "serialize", "shortcut_precheck", "shortcut_scores",
    "Example", "generate_split", "VerdictInputs", "evaluate",
]
