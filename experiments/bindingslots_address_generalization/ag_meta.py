#!/usr/bin/env python3
"""Torch-free metadata for the A1 lever: query-template partitions. Kept separate so template
separation / leakage can be verified without importing torch. The TEST partition equals the frozen
needle-eval query framing and is NEVER used for A1 training or coefficient selection."""
from __future__ import annotations

QUERY_TEMPLATES = {
    "test": [
        ("the", "code", "for", "ENT", "is"),           # == make_eval_set('needle') query framing
    ],
    "train": [
        ("the", "value", "of", "ENT", "is"),
        ("the", "limit", "for", "ENT", "is"),
        ("the", "current", "value", "of", "ENT", "is"),
        ("vendor", "ENT", "limit"),
        ("the", "code", "of", "ENT", "is"),
        ("the", "value", "for", "ENT", "is"),
        ("per", "source", "the", "value", "of", "ENT", "is"),
        ("the", "limit", "of", "ENT", "is"),
    ],
    "dev": [
        ("the", "current", "limit", "for", "ENT", "is"),
        ("the", "value", "of", "ENT", "now", "is"),
    ],
}
