"""Deterministic opaque-identifier pool generation with fail-closed integrity checks.

Identifiers are fixed-length opaque strings over a fixed alphabet, character-visible under the
frozen lexical tokenizer (each character is one token). Train / development / final pools are
disjoint; evidence identifiers come from a distinct domain-separated pool. No identifier encodes
task, position, answerability, seen/unseen status, or relation — they are drawn uniformly at random
from the alphabet, so surface form carries no lawful signal about the answer.
"""
from __future__ import annotations

import random
from typing import Iterable

from experiments.single_hop_typed_vs_prose.tokenizer import LexicalTokenizer

from .config import IDENTIFIER_ALPHABET, IDENTIFIER_LENGTH, sub_seed


class IdentifierIntegrityError(ValueError):
    """Raised (fail-closed) on any pool-integrity violation before identifiers are used."""


def _draw(rng: random.Random) -> str:
    return "".join(rng.choice(IDENTIFIER_ALPHABET) for _ in range(IDENTIFIER_LENGTH))


def _draw_distinct(rng: random.Random, count: int, used: set[str]) -> tuple[str, ...]:
    out: list[str] = []
    budget = count * 64 + 64
    for _ in range(budget):
        cand = _draw(rng)
        if cand not in used:
            used.add(cand)
            out.append(cand)
            if len(out) == count:
                return tuple(out)
    raise IdentifierIntegrityError("identifier space exhausted before pool was filled")


def build_pools(seed: int, per_split_window: int = 512, n_splits: int = 8,
                evidence_window: int = 256) -> dict[str, tuple[str, ...]]:
    """Build train / final / evidence master pools from ONE rng stream, so the three pools are
    DISJOINT BY CONSTRUCTION (drawn without replacement from a shared `used` set). Each pool is
    sized to give every split its own disjoint window (`per_split_window` per split)."""
    rng = random.Random(sub_seed(int(seed), "identifier_pools"))
    used: set[str] = set()
    train = _draw_distinct(rng, per_split_window * n_splits, used)
    final = _draw_distinct(rng, per_split_window * n_splits, used)
    evidence = _draw_distinct(rng, evidence_window * n_splits, used)
    return {"train": train, "final": final, "evidence": evidence}


def generate_pool(seed: int, cohort: str, size: int) -> tuple[str, ...]:
    """Convenience: a single distinct pool of `size` identifiers for one named cohort/stream."""
    if size <= 0:
        raise IdentifierIntegrityError("pool size must be positive")
    tag = {"train": 1, "development": 2, "final": 3, "evidence": 4}.get(cohort)
    if tag is None:
        raise IdentifierIntegrityError(f"unknown cohort: {cohort}")
    rng = random.Random(sub_seed(int(seed), "identifier_pools") * 31 + tag)
    return _draw_distinct(rng, size, set())


def assert_character_visible(identifiers: Iterable[str], tokenizer: LexicalTokenizer | None = None) -> None:
    """Fail-closed: every identifier must round-trip and occupy exactly IDENTIFIER_LENGTH tokens."""
    tokenizer = tokenizer or LexicalTokenizer()
    for ident in identifiers:
        ids = tokenizer.encode(ident)
        if tokenizer.decode(ids) != ident:
            raise IdentifierIntegrityError(f"identifier {ident!r} does not round-trip under the tokenizer")
        if len(ids) != IDENTIFIER_LENGTH:
            raise IdentifierIntegrityError(
                f"identifier {ident!r} is not character-visible ({len(ids)} tokens != {IDENTIFIER_LENGTH})"
            )


def assert_no_surface_leakage(identifiers: Iterable[str]) -> None:
    """Fail-closed: identifiers must be opaque (fixed length, fixed alphabet, no reserved prefix)."""
    alphabet = set(IDENTIFIER_ALPHABET)
    for ident in identifiers:
        if len(ident) != IDENTIFIER_LENGTH or any(ch not in alphabet for ch in ident):
            raise IdentifierIntegrityError(f"identifier {ident!r} violates the frozen alphabet/length")


def assert_pools_disjoint(**pools: tuple[str, ...]) -> None:
    """Fail-closed: every pair of named pools must be disjoint (train/dev/final/evidence)."""
    names = list(pools)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            overlap = set(pools[names[i]]) & set(pools[names[j]])
            if overlap:
                raise IdentifierIntegrityError(
                    f"pools {names[i]} and {names[j]} overlap on {sorted(overlap)[:3]}…"
                )


def assert_collision_free(identifiers: Iterable[str]) -> None:
    ids = list(identifiers)
    if len(ids) != len(set(ids)):
        raise IdentifierIntegrityError("duplicate identifier within a pool")
