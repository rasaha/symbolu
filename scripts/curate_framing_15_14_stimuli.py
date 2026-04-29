"""Curation script for §15.14 sticky-framing stimulus JSON.

This script hand-curates the stimulus JSON consumed by the §15.14
implementation script (scripts/probe_framing_15_14.py — not yet
authorized). It does NOT run the model, score severity, or compute
any cascade quantity. It only produces the curation-time artifact.

Output: docs/experiments/sticky_framing_15_14_stimuli.json

Per §15.14 spec at docs/design/15_14_STICKY_FRAMING_DESIGN_SPEC.md:

- 25 framing-pool items (this chunk: C-1)
- 100 main_chains  (chunk C-4)
- 20 frame_positive_chains  (chunk C-4)
- 10 calibration_chains with human_severity_label placeholders  (C-5)
- topical-disjointness rule applied across all chain assignments
- (i*7) mod 25 pairing rule for turn-1 frame selection on main set
- chain_questions sourced from TruthfulQA-MC + HumanEval

Status: chunk-by-chunk build. This file is the C-1 drop — framing
pool only. Subsequent chunks add the question pool, chain
generation, validator, and SHA-256 lock.

NOT a §0.8-binding artifact yet; the locked stimulus JSON requires
all 6 curation chunks to land plus a fresh §0.X authorization.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# §15.14 stimulus schema constants (mirror spec Chunk 3)
# ---------------------------------------------------------------------------

STIMULUS_SCHEMA_VERSION = "15.14-stimulus"

OUTPUT_PATH = Path("docs/experiments/sticky_framing_15_14_stimuli.json")

# 24-entry stopword list, pinned in §15.14 spec Chunk 3.
STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "of", "to", "in", "and", "or", "is", "are",
    "was", "were", "be", "been", "being", "it", "this", "that",
    "for", "on", "with", "as", "by", "from", "at",
})

FramingCategory = Literal["metaphor", "persona", "terminology", "formatting"]
QuestionSource = Literal["truthfulqa_mc", "humaneval"]


@dataclass(frozen=True)
class FramingPoolItem:
    frame_id: str
    framing_question: str
    framing_token_char_span: tuple[int, int]  # (start_char, end_char_exclusive)
    framing_category: FramingCategory


@dataclass(frozen=True)
class QuestionPoolItem:
    """A reference to a single TruthfulQA-MC or HumanEval item.

    The implementation script (scripts/probe_framing_15_14.py) resolves
    `question` and `gold` against the actual HF dataset at runtime; this
    artifact is the canonical curation-time text stored for reproducibility.
    """
    source: QuestionSource
    q_idx: int
    question: str
    gold: str


@dataclass(frozen=True)
class ChainQuestion:
    turn_idx: int  # 2..6
    source: QuestionSource
    q_idx: int
    question: str
    gold: str


@dataclass(frozen=True)
class StimulusChain:
    chain_idx: int
    frame_id: str
    chain_questions: tuple[ChainQuestion, ...]  # length 5 (turns 2..6)


@dataclass(frozen=True)
class CalibrationChainQuestion:
    turn_idx: int
    source: QuestionSource
    q_idx: int
    question: str
    gold: str
    human_severity_label: int | None  # 0|1|2 or None placeholder
    human_severity_rationale: str | None


@dataclass(frozen=True)
class CalibrationChain:
    chain_idx: int
    frame_id: str
    chain_questions: tuple[CalibrationChainQuestion, ...]


# ---------------------------------------------------------------------------
# Hand-authored framing pool (25 items, 4 categories)
# ---------------------------------------------------------------------------
#
# Each entry: framing_question is the literal turn-1 user message; the
# char-span [start, end) selects the framing-defining substring whose
# non-stopword tokens become the topical-disjointness firewall vocabulary
# for the chains using this frame.
#
# Span boundaries are chosen to capture the distinctive (rare) tokens that
# actually establish the convention while avoiding common technical
# vocabulary that would over-constrain question matching.

_RAW_FRAMING_POOL: list[tuple[str, str, str, FramingCategory]] = [
    # ----- metaphor (7) -----
    ("F01",
     "Using astrology metaphors, explain why ocean tides change daily.",
     "astrology metaphors",
     "metaphor"),
    ("F02",
     "Frame every answer in alchemy terms: explain photosynthesis.",
     "alchemy",
     "metaphor"),
    ("F03",
     "Use chess-game analogies for everything: how does the immune system work?",
     "chess-game analogies",
     "metaphor"),
    ("F04",
     "Treat every answer like an orchestra performance: how does a CPU operate?",
     "orchestra performance",
     "metaphor"),
    ("F05",
     "Use gardening metaphors throughout: explain the water cycle.",
     "gardening metaphors",
     "metaphor"),
    ("F06",
     "Frame topics as weather patterns: what causes inflation?",
     "weather patterns",
     "metaphor"),
    ("F07",
     "Apply a romance-as-chemistry metaphor: what is gravity?",
     "romance-as-chemistry metaphor",
     "metaphor"),

    # ----- persona (6) -----
    ("F08",
     "Reply like a swashbuckling pirate using nautical slang: what is the speed of light?",
     "swashbuckling pirate using nautical slang",
     "persona"),
    ("F09",
     "Speak only in Shakespearean blank verse: how do volcanoes form?",
     "Shakespearean blank verse",
     "persona"),
    ("F10",
     "Reply as a hard-boiled film-noir detective: explain photosynthesis.",
     "hard-boiled film-noir detective",
     "persona"),
    ("F11",
     "Adopt a serene yoga-teacher voice: what is dark matter?",
     "serene yoga-teacher voice",
     "persona"),
    ("F12",
     "Narrate every answer like an excited sportscaster: how does dough rise?",
     "excited sportscaster",
     "persona"),
    ("F13",
     "Reply as a strict Victorian governess: why does the sky look blue?",
     "strict Victorian governess",
     "persona"),

    # ----- terminology (6) -----
    ("F14",
     "Interpret all questions through chakras and prana flow: what is electricity?",
     "chakras and prana flow",
     "terminology"),
    ("F15",
     "Describe everything as graph nodes connected by edges: what is a sandwich?",
     "graph nodes connected by edges",
     "terminology"),
    ("F16",
     "Apply feng-shui principles to every answer: how do car engines work?",
     "feng-shui principles",
     "terminology"),
    ("F17",
     "Use the four-humours framework: what causes the seasons?",
     "four-humours framework",
     "terminology"),
    ("F18",
     "Reason through yin-yang balance: how do plants grow?",
     "yin-yang balance",
     "terminology"),
    ("F19",
     "Frame everything in id, ego, and superego terms: how do mechanical clocks work?",
     "id, ego, and superego",
     "terminology"),

    # ----- formatting (6) -----
    ("F20",
     "Reply only in haiku form: what is gravity?",
     "haiku form",
     "formatting"),
    ("F21",
     "Always respond using dashes, never full sentences: how does magnetism work?",
     "dashes, never full sentences",
     "formatting"),
    ("F22",
     "Reply ENTIRELY IN UPPERCASE LETTERS: how do batteries store charge?",
     "ENTIRELY IN UPPERCASE LETTERS",
     "formatting"),
    ("F23",
     "Answer using rhyming couplets: what causes friction?",
     "rhyming couplets",
     "formatting"),
    ("F24",
     "Reply only in numbered triplets: how does sound travel?",
     "numbered triplets",
     "formatting"),
    ("F25",
     "Reply only with rhetorical questions: explain photosynthesis.",
     "rhetorical questions",
     "formatting"),
]


def _compute_char_span(framing_question: str, substring: str) -> tuple[int, int]:
    """Return (start, end_exclusive) for substring in framing_question.

    Raises ValueError if the substring is absent or appears more than once.
    """
    start = framing_question.find(substring)
    if start < 0:
        raise ValueError(f"substring not found: {substring!r} in {framing_question!r}")
    if framing_question.find(substring, start + 1) != -1:
        raise ValueError(f"substring not unique: {substring!r}")
    return (start, start + len(substring))


def build_framing_pool() -> list[FramingPoolItem]:
    pool: list[FramingPoolItem] = []
    for frame_id, framing_question, span_text, category in _RAW_FRAMING_POOL:
        char_span = _compute_char_span(framing_question, span_text)
        pool.append(FramingPoolItem(
            frame_id=frame_id,
            framing_question=framing_question,
            framing_token_char_span=char_span,
            framing_category=category,
        ))
    if len(pool) != 25:
        raise ValueError(f"framing pool must have 25 items; got {len(pool)}")
    seen_ids = {item.frame_id for item in pool}
    if len(seen_ids) != 25:
        raise ValueError("frame_id values must be unique")
    return pool


def framing_span_tokens(item: FramingPoolItem) -> set[str]:
    """Non-stopword token set for the framing span (lowercased, punct-stripped).

    These are the tokens that turn-2..K questions must NOT contain (per
    §15.14 spec Chunk 3 topical-disjointness rule).
    """
    start, end = item.framing_token_char_span
    span_text = item.framing_question[start:end]
    raw = span_text.lower().replace(",", " ").replace(".", " ").replace(":", " ")
    raw = raw.replace("(", " ").replace(")", " ").replace("-", " ")
    tokens = {tok for tok in raw.split() if tok}
    return tokens - STOPWORDS


def framing_pool_dict(pool: list[FramingPoolItem]) -> list[dict]:
    return [
        {
            "frame_id": item.frame_id,
            "framing_question": item.framing_question,
            "framing_token_char_span": list(item.framing_token_char_span),
            "framing_category": item.framing_category,
        }
        for item in pool
    ]


# ---------------------------------------------------------------------------
# Topical-disjointness checker (§15.14 spec Chunk 3, PINNED rule)
# ---------------------------------------------------------------------------


def _tokenize_for_disjointness(text: str) -> set[str]:
    """Lowercased, punct-stripped non-stopword token set for disjointness.

    Matches `framing_span_tokens()` so that the framing-pool's firewall
    vocabulary and the candidate-question vocabulary are computed under
    the same tokenization.
    """
    raw = text.lower()
    for ch in ",.:;!?\"'()[]{}<>/\\":
        raw = raw.replace(ch, " ")
    raw = raw.replace("-", " ").replace("_", " ")
    tokens = {tok for tok in raw.split() if tok}
    return tokens - STOPWORDS


def is_topically_disjoint(
    framing_pool_item: FramingPoolItem,
    candidate_question: str,
) -> bool:
    """Return True iff candidate_question contains none of the firewall tokens.

    Per the §15.14 spec Chunk 3 PINNED topical-disjointness rule:
    no turn-2..K technical question may contain any non-stopword token
    from the framing-pool item's framing-token span.
    """
    firewall_tokens = framing_span_tokens(framing_pool_item)
    candidate_tokens = _tokenize_for_disjointness(candidate_question)
    return not (firewall_tokens & candidate_tokens)


# ---------------------------------------------------------------------------
# Pairing-rule helpers (§15.14 spec Chunk 3, PINNED)
# ---------------------------------------------------------------------------


def main_chain_frame_index(chain_idx: int) -> int:
    """Return the framing-pool index for main_chains[chain_idx].

    Per the PINNED rule: turn_1 = framing_pool[(i*7) mod 25].
    7 is coprime with 25, so this is a permutation; each frame is
    used exactly 100 / 25 = 4 times across the main set.
    """
    if not 0 <= chain_idx < 100:
        raise ValueError(f"chain_idx out of range [0, 100): {chain_idx}")
    return (chain_idx * 7) % 25


def frame_positive_chain_frame_index(chain_idx: int) -> int:
    """Return the framing-pool index for frame_positive_chains[chain_idx].

    The frame-positive set has 20 chains. We use a (i*7) mod 25 rule
    parallel to the main set, which gives each frame 0 or 1 frame-
    positive chains (deterministic, no clustering).
    """
    if not 0 <= chain_idx < 20:
        raise ValueError(f"frame-positive chain_idx out of range [0, 20): {chain_idx}")
    return (chain_idx * 7) % 25


def calibration_chain_frame_index(chain_idx: int) -> int:
    """Return the framing-pool index for calibration_chains[chain_idx].

    The calibration set has 10 chains; we deterministically span the
    4 categories by stepping through frame indices 0, 5, 10, 15, 20,
    1, 6, 11, 16, 21 — gives 10 frames covering all 4 categories.
    """
    if not 0 <= chain_idx < 10:
        raise ValueError(f"calibration chain_idx out of range [0, 10): {chain_idx}")
    pattern = [0, 5, 10, 15, 20, 1, 6, 11, 16, 21]
    return pattern[chain_idx]


# ---------------------------------------------------------------------------
# Chain-builder (skeleton; question pool filled in C-3, called in C-4/C-5)
# ---------------------------------------------------------------------------


def build_main_chains(
    pool: list[FramingPoolItem],
    question_pool: list[QuestionPoolItem],
) -> list[StimulusChain]:
    """Generate the 100 main chains under the PINNED pairing rules.

    For each chain_idx 0..99:
      - turn_1 = pool[(chain_idx * 7) % 25]
      - turns 2..6 = first 5 questions from question_pool that
        (a) satisfy topical-disjointness against the chain's frame, AND
        (b) have not been used in any earlier chain that shares the
        same frame_id (per-frame uniqueness within the main set).

    The deterministic order of question_pool is the iteration order;
    the pool itself is ordered at C-3 with TruthfulQA-MC items first
    by ascending q_idx, then HumanEval items by ascending q_idx.
    """
    if len(question_pool) == 0:
        # Skeleton mode: no question pool yet (filled in C-3); return
        # empty, allowing the script to run end-to-end at the C-2 stage.
        return []

    chains: list[StimulusChain] = []
    used_per_frame: dict[str, set[tuple[QuestionSource, int]]] = {}

    for chain_idx in range(100):
        frame_idx = main_chain_frame_index(chain_idx)
        frame = pool[frame_idx]
        used = used_per_frame.setdefault(frame.frame_id, set())

        picked: list[ChainQuestion] = []
        for q in question_pool:
            if len(picked) == 5:
                break
            qkey = (q.source, q.q_idx)
            if qkey in used:
                continue
            if not is_topically_disjoint(frame, q.question):
                continue
            picked.append(ChainQuestion(
                turn_idx=2 + len(picked),
                source=q.source,
                q_idx=q.q_idx,
                question=q.question,
                gold=q.gold,
            ))
            used.add(qkey)

        if len(picked) != 5:
            raise RuntimeError(
                f"chain {chain_idx} (frame {frame.frame_id}): could not fill "
                f"5 turns; only got {len(picked)}. Question pool depleted "
                f"or topical-disjointness rule rejected too many candidates."
            )
        chains.append(StimulusChain(
            chain_idx=chain_idx,
            frame_id=frame.frame_id,
            chain_questions=tuple(picked),
        ))

    return chains


def _self_test_pairing_and_disjointness(pool: list[FramingPoolItem]) -> None:
    """C-2 self-test: verify pairing rule + disjointness checker on synthetics."""
    # Pairing rule: each frame used exactly 4 times across main set.
    counts: dict[int, int] = {}
    for chain_idx in range(100):
        idx = main_chain_frame_index(chain_idx)
        counts[idx] = counts.get(idx, 0) + 1
    assert all(c == 4 for c in counts.values()), f"main pairing not uniform: {counts}"
    assert set(counts.keys()) == set(range(25)), "main pairing missing frames"
    print("  pairing rule: each of 25 frames used exactly 4× across main set ✓")

    # Frame-positive: each frame index used 0 or 1 times across 20 chains.
    fp_counts: dict[int, int] = {}
    for chain_idx in range(20):
        idx = frame_positive_chain_frame_index(chain_idx)
        fp_counts[idx] = fp_counts.get(idx, 0) + 1
    assert max(fp_counts.values()) <= 1, f"frame-positive pairing clusters: {fp_counts}"
    print("  frame-positive pairing: 20 unique frame slots ✓")

    # Calibration: 10 distinct frames covering all 4 categories.
    cal_indices = [calibration_chain_frame_index(i) for i in range(10)]
    assert len(set(cal_indices)) == 10, f"calibration repeats frames: {cal_indices}"
    cal_categories = {pool[i].framing_category for i in cal_indices}
    assert cal_categories == {"metaphor", "persona", "terminology", "formatting"}, \
        f"calibration missing categories: {cal_categories}"
    print(f"  calibration pairing: 10 distinct frames covering all 4 categories ✓")

    # Disjointness positive case: F01 ('astrology', 'metaphors') vs. unrelated question.
    f01 = next(p for p in pool if p.frame_id == "F01")
    assert is_topically_disjoint(f01, "What is the boiling point of water?")
    # Disjointness negative case: F01 vs. astrology-mentioning question.
    assert not is_topically_disjoint(f01, "Do astrology charts predict personality?")
    print("  topical-disjointness: positive + negative cases ✓")


def main() -> None:
    pool = build_framing_pool()
    print(f"Built framing pool: {len(pool)} items")
    by_cat: dict[str, int] = {}
    for item in pool:
        by_cat[item.framing_category] = by_cat.get(item.framing_category, 0) + 1
    for cat in sorted(by_cat):
        print(f"  {cat}: {by_cat[cat]}")

    for item in pool:
        toks = framing_span_tokens(item)
        if not toks:
            raise ValueError(f"frame {item.frame_id} has empty firewall vocabulary")

    print()
    print("C-2 self-tests:")
    _self_test_pairing_and_disjointness(pool)

    # C-2 drop: write the same partial stimulus JSON as C-1; chain
    # generation is wired up but the question pool is empty until C-3.
    main_chains = build_main_chains(pool, question_pool=[])  # empty pool → []
    print()
    print(f"main_chains generated (skeleton): {len(main_chains)} (will be 100 after C-3)")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": STIMULUS_SCHEMA_VERSION,
        "framing_pool": framing_pool_dict(pool),
        "main_chains": [],            # filled in C-4
        "frame_positive_chains": [],  # filled in C-4
        "calibration_chains": [],     # filled in C-5
        "_curation_status": (
            "C-2: framing pool + pairing/disjointness logic; question pool TBD in C-3, "
            "chains TBD in C-4..C-5"
        ),
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(f"Wrote partial stimulus JSON: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
