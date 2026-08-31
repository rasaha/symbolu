"""Bounded Typed Relational Reasoning (BTRR) experiment package.

Implementation only. Execution is NOT authorized: reserved seeds (8100, 8101-8103, 81600-81604) fail
closed until EXECUTION_AUTHORIZATION.md is signed. This package imports torch-free; torch is imported
lazily inside model.py / trainer.py only when an (unauthorized) training/eval path is taken.

Effective authority: Amendment 002 (a84cc8eef848e7081764deb894593f7b270f32ba).
"""
from __future__ import annotations

from . import (base_capability, config, execution, gates, generator, manifest, metrics, output,
               replay, schema_ext, serializer, shortcuts, tokenizer, verdict)

__all__ = [
    "config", "tokenizer", "schema_ext", "serializer", "output", "generator", "base_capability",
    "metrics", "shortcuts", "gates", "verdict", "execution", "manifest", "replay",
]
