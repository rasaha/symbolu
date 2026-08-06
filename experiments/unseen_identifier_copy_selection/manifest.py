"""Deterministic fingerprint / manifest utilities for the unseen-identifier diagnostic.

Records ACTUAL digest values (not booleans). Reused frozen-recipe source hashes are computed from
the merged implementation so a future run can prove it used the exact recipe. No run is performed
here.
"""
from __future__ import annotations

import hashlib
import os
from typing import Iterable

from experiments.single_hop_typed_vs_prose import config as _tvp_config

_TVP_DIR = os.path.dirname(_tvp_config.__file__)
# Recipe-bearing frozen sources reused by this diagnostic.
FROZEN_RECIPE_SOURCES = ("config.py", "tokenizer.py", "model.py", "trainer.py")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def frozen_recipe_source_hashes() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in FROZEN_RECIPE_SOURCES:
        with open(os.path.join(_TVP_DIR, name), "rb") as fh:
            out[name] = sha256_bytes(fh.read())
    return out


def dataset_digest(serialized_examples: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for text in serialized_examples:
        digest.update(text.encode("ascii"))
        digest.update(b"\x00")
    return digest.hexdigest()


def example_hash_digest(example_hashes: Iterable[str]) -> str:
    return hashlib.sha256("".join(example_hashes).encode("ascii")).hexdigest()
