"""Phase 3A CPU tests for the prompt builders.

Validates the two ``PromptBuilder`` subclasses in
``ctm_bench.runner_vllm_streaming``:

* ``ParetoUniqueHeadPromptBuilder`` — the legacy PR-2 shape that
  defeats prefix caching by injecting a per-request unique head
  token. Default builder; preserves PR-2 behaviour byte-identical.
* ``SharedPrefixPromptBuilder`` — N cohorts each with a shared
  token-ID prefix; the workload shape Phase 3 uses to measure
  realized prefix-cache hits.

Acceptance gates exercised:
* A1: workload generator produces cohort-shared prompts (cohort
  prefixes match within-cohort, differ across cohorts).
* A5: defaults preserve PR-2 behaviour bit-exact (no
  shared-prefix → same prompts as today).

No torch, no vllm, no GPU.
"""

from __future__ import annotations

from typing import List

import pytest

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()

from ctm_bench.runner_vllm_streaming import (
    ParetoUniqueHeadPromptBuilder,
    PromptBuilder,
    SharedPrefixPromptBuilder,
)


# ---------------------------------------------------------------- #
# Pareto-unique-head builder (PR-2 default; byte-identical regression)
# ---------------------------------------------------------------- #


def test_pareto_builder_default_shape_matches_pr2() -> None:
    """The legacy builder must emit ``[200 + (i % 4096)] + [100]*(L-1)``
    for any (i, L). This is the bit-identical regression gate
    against PR-2's inline prompt generation."""
    b = ParetoUniqueHeadPromptBuilder()
    assert b.name == "pareto_unique_head"
    for i, L in [(0, 1), (0, 10), (1, 100), (4095, 256), (4096, 16), (10_000, 32)]:
        out = b.build(request_id_counter=i, suggested_length=L)
        expected_head = 200 + (i % 4096)
        assert out[0] == expected_head, (i, L, out[0])
        assert all(t == 100 for t in out[1:]), (i, L)
        assert len(out) == L


def test_pareto_builder_length_zero_returns_empty() -> None:
    """Edge case: suggested_length=0 → empty list. Tests the early
    guard in build()."""
    b = ParetoUniqueHeadPromptBuilder()
    assert b.build(request_id_counter=0, suggested_length=0) == []


def test_pareto_builder_cohort_of_is_minus_one() -> None:
    """Non-shared-prefix builder reports no-cohort."""
    b = ParetoUniqueHeadPromptBuilder()
    assert b.cohort_of(0) == -1
    assert b.cohort_of(999_999) == -1


# ---------------------------------------------------------------- #
# Shared-prefix builder — validation
# ---------------------------------------------------------------- #


def test_shared_prefix_builder_rejects_invalid_args() -> None:
    """Explicit guards on shared_prefix_length, n_cohorts,
    unique_tail_choices."""
    with pytest.raises(ValueError, match="shared_prefix_length"):
        SharedPrefixPromptBuilder(
            seed=1, shared_prefix_length=0,
            unique_tail_choices=[16], n_cohorts=1,
        )
    with pytest.raises(ValueError, match="n_cohorts"):
        SharedPrefixPromptBuilder(
            seed=1, shared_prefix_length=4,
            unique_tail_choices=[16], n_cohorts=0,
        )
    with pytest.raises(ValueError, match="unique_tail_choices"):
        SharedPrefixPromptBuilder(
            seed=1, shared_prefix_length=4,
            unique_tail_choices=[], n_cohorts=2,
        )


def test_shared_prefix_builder_intra_cohort_prefixes_match() -> None:
    """All requests in the same cohort share an identical prompt
    token-ID prefix of length ``shared_prefix_length``.

    This is the load-bearing assertion: if it fails, vLLM's
    content-hash chain across requests in a cohort won't produce
    prefix-cache hits, and the Phase 3 measurement collapses.
    """
    b = SharedPrefixPromptBuilder(
        seed=42, shared_prefix_length=32, unique_tail_choices=[16, 32],
        n_cohorts=4,
    )
    L = b.shared_prefix_length
    # Cohort assignment is round-robin by request_id_counter modulo
    # n_cohorts. Requests 0, 4, 8, ... → cohort 0; 1, 5, 9, ... → cohort 1; etc.
    cohort_0_prefixes: List[List[int]] = []
    cohort_1_prefixes: List[List[int]] = []
    for i in [0, 4, 8, 12, 16]:
        p = b.build(request_id_counter=i, suggested_length=999)
        cohort_0_prefixes.append(p[:L])
    for i in [1, 5, 9, 13, 17]:
        p = b.build(request_id_counter=i, suggested_length=999)
        cohort_1_prefixes.append(p[:L])
    # Every cohort-0 request shares the same prefix.
    assert all(
        p == cohort_0_prefixes[0] for p in cohort_0_prefixes
    ), "cohort 0 prefixes drifted"
    # Same for cohort 1.
    assert all(
        p == cohort_1_prefixes[0] for p in cohort_1_prefixes
    ), "cohort 1 prefixes drifted"


def test_shared_prefix_builder_cross_cohort_prefixes_differ() -> None:
    """Different cohorts must produce different prefixes — otherwise
    they'd all hash-collapse into one super-cohort."""
    b = SharedPrefixPromptBuilder(
        seed=42, shared_prefix_length=32, unique_tail_choices=[16],
        n_cohorts=4,
    )
    L = b.shared_prefix_length
    prefixes = [
        b.build(request_id_counter=i, suggested_length=999)[:L]
        for i in range(4)
    ]
    # Pairwise distinct.
    for i in range(4):
        for j in range(i + 1, 4):
            assert prefixes[i] != prefixes[j], (
                f"cohorts {i} and {j} collided"
            )


def test_shared_prefix_builder_tail_lengths_in_choices() -> None:
    """Tail length must be one of ``unique_tail_choices``."""
    choices = [8, 16, 32]
    b = SharedPrefixPromptBuilder(
        seed=42, shared_prefix_length=8,
        unique_tail_choices=choices, n_cohorts=2,
    )
    L = b.shared_prefix_length
    for i in range(20):
        out = b.build(request_id_counter=i, suggested_length=99)
        tail_len = len(out) - L
        assert tail_len in choices, (i, tail_len, out)


def test_shared_prefix_builder_token_id_ranges_are_disjoint() -> None:
    """Prefix tokens drawn from [1000, 4999]; tail tokens from
    [6000, 9999]. The disjoint ranges prevent accidental tail-to-
    prefix content_hash collisions across cohorts."""
    b = SharedPrefixPromptBuilder(
        seed=42, shared_prefix_length=8,
        unique_tail_choices=[8, 16], n_cohorts=3,
    )
    L = b.shared_prefix_length
    for i in range(10):
        out = b.build(request_id_counter=i, suggested_length=99)
        prefix = out[:L]
        tail = out[L:]
        assert all(1000 <= t <= 4999 for t in prefix), (i, prefix)
        assert all(6000 <= t <= 9999 for t in tail), (i, tail)


def test_shared_prefix_builder_is_deterministic_per_seed() -> None:
    """Two builders with the same seed produce identical token IDs
    for the same request_id_counter. Phase 3 needs this so cells
    A/B/C see the same prompts on the same seed."""
    b1 = SharedPrefixPromptBuilder(
        seed=7, shared_prefix_length=16,
        unique_tail_choices=[8, 16], n_cohorts=2,
    )
    b2 = SharedPrefixPromptBuilder(
        seed=7, shared_prefix_length=16,
        unique_tail_choices=[8, 16], n_cohorts=2,
    )
    for i in range(5):
        assert b1.build(request_id_counter=i, suggested_length=99) == \
            b2.build(request_id_counter=i, suggested_length=99)


def test_shared_prefix_builder_cohort_of_round_robin() -> None:
    """cohort_of(i) = i % n_cohorts."""
    b = SharedPrefixPromptBuilder(
        seed=1, shared_prefix_length=4,
        unique_tail_choices=[2], n_cohorts=4,
    )
    for i in range(20):
        assert b.cohort_of(i) == i % 4


def test_shared_prefix_builder_name_is_shared_prefix() -> None:
    """Name surfaces in the result dataclass for downstream
    analysis to distinguish the workload shape per run."""
    b = SharedPrefixPromptBuilder(
        seed=1, shared_prefix_length=4,
        unique_tail_choices=[2], n_cohorts=1,
    )
    assert b.name == "shared_prefix"
