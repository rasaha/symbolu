#!/usr/bin/env python3
"""
Combined loader: immutable seed (22) + ACCEPTED pilot cases. Resolver-facing;
accepted-only. The seed subset is loaded unchanged from the frozen seed corpus.
"""

from __future__ import annotations

from agentic.hybrid_handover.resolution.hidden_corpus import corpus as seed_corpus

from . import pilot_corpus


def combined_executable() -> list[dict]:
    """Seed executable cases + accepted pilot executable cases."""
    return seed_corpus.executable_cases() + pilot_corpus.executable_cases()


def seed_count() -> int:
    return len(seed_corpus.executable_cases())


def pilot_count() -> int:
    return len(pilot_corpus.executable_cases())
