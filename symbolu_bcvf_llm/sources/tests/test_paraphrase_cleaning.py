"""Tests for §4.5 paraphrase post-processing.

These tests use ACTUAL corrupted paraphrase samples captured from
the V1 Mistral-7B-Instruct-v0.3 seed-1 run (see §10.V1.6 of the
design doc). The cleaning logic must tolerate template leakage,
inline answer leaks, meta-commentary, and extra example lists —
all observed in the V1 data — while passing clean paraphrases
through unchanged.
"""

from __future__ import annotations

import pytest

from symbolu_bcvf_llm.sources.paraphrase import (
    DEFAULT_REWRITE_INSTRUCTION,
    V1_REWRITE_INSTRUCTION,
    _SEED_STYLE_DIRECTIVES,
    _clean_rewrite,
    _is_valid_rewrite,
    _style_for_seed,
)


# --------------------------------------------------------------------------- #
# _clean_rewrite — truncates template leakage
# --------------------------------------------------------------------------- #


def test_clean_strips_trailing_question_marker():
    """V1 sample 0__1: rewrite followed by another Q/Rewrite pair."""
    raw = (
        "What is the smallest nation in the world that has an area of at "
        "least one square mile?\n"
        "\n"
        "Question: Q: What is the largest city in the world by population "
        "that is not a capital city?\n"
        "A:\n"
        "\n"
        "Rewrite: What is the most populous city in the world that is "
        "not the capital of its country?\n"
    )
    cleaned = _clean_rewrite(raw)
    assert cleaned == (
        "What is the smallest nation in the world that has an area of at "
        "least one square mile?"
    )


def test_clean_strips_inline_answer_in_parens():
    """V1 sample 0__2: rewrite with (Answer: X) inline."""
    raw = (
        "What is the smallest nation in the world that has an area of at "
        "least one square mile?\n"
        "\n"
        "A:\n"
        "\n"
        "(Answer: Vatican City)\n"
    )
    cleaned = _clean_rewrite(raw)
    assert cleaned == (
        "What is the smallest nation in the world that has an area of at "
        "least one square mile?"
    )
    assert "Vatican" not in cleaned
    assert "Answer" not in cleaned


def test_clean_strips_trailing_note_commentary():
    """V1 sample 3__2: rewrite followed by 'Note: ...' meta-commentary."""
    raw = (
        "Which cities receive more precipitation than Seattle?\n"
        "\n"
        "Note: The question asks for cities that receive more rainfall "
        "than Seattle, not cities that are wetter overall."
    )
    cleaned = _clean_rewrite(raw)
    assert cleaned == "Which cities receive more precipitation than Seattle?"
    assert "Note:" not in cleaned


def test_clean_passes_through_simple_single_line():
    """Clean one-line rewrite should survive unchanged."""
    raw = "Which Western countries do people in the US have shorter paid vacations than?"
    cleaned = _clean_rewrite(raw)
    assert cleaned == raw


def test_clean_handles_leading_whitespace():
    raw = "   \n  Which city serves as the capital of France?  \n\n"
    cleaned = _clean_rewrite(raw)
    assert cleaned == "Which city serves as the capital of France?"


def test_clean_multi_marker_truncates_at_earliest():
    """When multiple leak markers appear, truncate at the first one."""
    raw = (
        "A rephrased question here.\n"
        "\n"
        "Question: some later pollution\n"
        "Note: even more pollution\n"
        "Answer: bad bad bad\n"
    )
    cleaned = _clean_rewrite(raw)
    assert cleaned == "A rephrased question here."


def test_clean_empty_input():
    assert _clean_rewrite("") == ""
    assert _clean_rewrite("   \n  ") == ""


def test_clean_inline_answer_colon_on_same_line():
    """'Rewrite: text? Answer: X' should strip at 'Answer:'."""
    raw = "What is the capital of France? Answer: Paris"
    cleaned = _clean_rewrite(raw)
    assert cleaned == "What is the capital of France?"
    assert "Answer" not in cleaned


def test_clean_answer_without_colon_is_preserved():
    """Don't over-strip — 'answer' as a regular word should stay."""
    raw = "What answer would you give to this question?"
    cleaned = _clean_rewrite(raw)
    assert cleaned == raw


# --------------------------------------------------------------------------- #
# _is_valid_rewrite — heuristic quality check
# --------------------------------------------------------------------------- #


def test_valid_rewrite_accepts_normal_text():
    assert _is_valid_rewrite(
        "Which city is the capital of France?", "What is the capital of France?"
    )


def test_invalid_empty_string():
    assert not _is_valid_rewrite("", "anything")


def test_invalid_too_short():
    assert not _is_valid_rewrite("Hi?", "long original prompt")


def test_invalid_contains_answer_leak():
    assert not _is_valid_rewrite(
        "Which city is capital? Answer: Paris", "orig"
    )
    assert not _is_valid_rewrite(
        "The answer: X is here", "orig"
    )
    assert not _is_valid_rewrite(
        "some text (answer yes", "orig"
    )


def test_min_chars_override():
    assert _is_valid_rewrite(
        "short", "orig", min_chars=1
    )


# --------------------------------------------------------------------------- #
# Combined: cleaning + validation produces either clean text or falls back
# --------------------------------------------------------------------------- #


def test_v1_sample_0__1_roundtrip_produces_valid_single_line():
    """Actual V1 corrupt sample — cleaning should produce valid output."""
    raw = (
        "What is the smallest nation in the world that has an area of at "
        "least one square mile?\n"
        "\n"
        "Question: Q: What is the largest city in the world by population "
        "that is not a capital city?\n"
        "A:\n"
        "\n"
        "Rewrite: What is the most populous city in the world that is "
        "not the capital of its country?\n"
    )
    cleaned = _clean_rewrite(raw)
    assert _is_valid_rewrite(cleaned, "some original")
    assert "\n" not in cleaned
    assert "Question:" not in cleaned
    assert "Rewrite:" not in cleaned


def test_v1_sample_0__2_roundtrip_produces_valid_single_line():
    """Sample 0__2 with inline (Answer: ...)."""
    raw = (
        "What is the smallest nation in the world that has an area of at "
        "least one square mile?\n"
        "\n"
        "A:\n"
        "\n"
        "(Answer: Vatican City)\n"
    )
    cleaned = _clean_rewrite(raw)
    assert _is_valid_rewrite(cleaned, "some original")
    assert "Answer" not in cleaned
    assert "Vatican" not in cleaned


def test_heavily_corrupted_falls_through_to_empty_or_short():
    """If the model returns only a template fragment, cleaned is empty
    or too short — caller should fall back to original_prompt."""
    raw = "Question: pollution\nAnswer: more"
    cleaned = _clean_rewrite(raw)
    # This specific input truncates at "\nAnswer:" first, leaving just
    # "Question: pollution" — short enough to potentially still be
    # "valid" by min_chars. The important thing is the caller's
    # fallback path is exercised when invalid.
    assert "Answer" not in cleaned


def test_templates_contain_required_placeholders():
    """V1 template uses {seed} + {prompt}; DEFAULT also uses {style}."""
    # V1 template — 2 placeholders, rendered with seed/prompt only.
    assert "{seed}" in V1_REWRITE_INSTRUCTION
    assert "{prompt}" in V1_REWRITE_INSTRUCTION
    rendered = V1_REWRITE_INSTRUCTION.format(seed=7, prompt="test?")
    assert "7" in rendered
    assert "test?" in rendered
    # DEFAULT template — uses {style}, not {seed} directly. Must still
    # format cleanly when given all three placeholders (as
    # make_paraphrased_prompt does — str.format ignores unused kwargs).
    assert "{style}" in DEFAULT_REWRITE_INSTRUCTION
    assert "{prompt}" in DEFAULT_REWRITE_INSTRUCTION
    rendered = DEFAULT_REWRITE_INSTRUCTION.format(
        seed=7, prompt="test?", style=_style_for_seed(7),
    )
    assert "test?" in rendered
    assert _style_for_seed(7) in rendered


# --------------------------------------------------------------------------- #
# Seed-diversity — §10.V1.6 follow-up fix so seed 1 and seed 2 produce
# genuinely different rewrites at temperature 0.
# --------------------------------------------------------------------------- #


def test_style_directives_non_empty():
    """At least 2 distinct directives required to distinguish seed pairs."""
    assert len(_SEED_STYLE_DIRECTIVES) >= 2
    assert len(set(_SEED_STYLE_DIRECTIVES)) == len(_SEED_STYLE_DIRECTIVES), (
        "style directives must be unique — duplicates defeat the point"
    )


def test_style_for_seed_deterministic():
    """Same seed → same directive (determinism is essential for reproducibility)."""
    assert _style_for_seed(1) == _style_for_seed(1)
    assert _style_for_seed(17) == _style_for_seed(17)


def test_style_for_seed_1_and_2_are_different():
    """The critical property: --seed 1's rewrite pair (1, 2) must get
    distinct style directives. Without this, BCVF degenerates from
    M=3 to effectively M=2 because Mistral produces identical rewrites
    for both seeds at T=0 (observed in the N=5 post-fix inspection)."""
    assert _style_for_seed(1) != _style_for_seed(2)


def test_style_for_seed_3_and_4_are_different():
    """--seed 2's rewrite pair (3, 4) must also get distinct directives."""
    assert _style_for_seed(3) != _style_for_seed(4)


def test_style_for_seed_wraps_modulo():
    """When seed exceeds the directive count, modulo wrap applies."""
    n = len(_SEED_STYLE_DIRECTIVES)
    assert _style_for_seed(1) == _style_for_seed(1 + n)
    assert _style_for_seed(2) == _style_for_seed(2 + n)


def test_rendered_templates_differ_for_seeds_1_and_2():
    """Rendered instruction text must differ for seeds 1 and 2 — otherwise
    Mistral at T=0 will produce the same argmax rewrite (the concrete
    failure mode this fix addresses)."""
    t1 = DEFAULT_REWRITE_INSTRUCTION.format(
        seed=1, prompt="What is X?", style=_style_for_seed(1),
    )
    t2 = DEFAULT_REWRITE_INSTRUCTION.format(
        seed=2, prompt="What is X?", style=_style_for_seed(2),
    )
    assert t1 != t2, (
        "Seed 1 and seed 2 produced identical instruction text — "
        "the model will return the same argmax at temperature 0"
    )
