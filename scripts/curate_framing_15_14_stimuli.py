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


@dataclass(frozen=True)
class FramingPoolItem:
    frame_id: str
    framing_question: str
    framing_token_char_span: tuple[int, int]  # (start_char, end_char_exclusive)
    framing_category: FramingCategory


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


def main() -> None:
    pool = build_framing_pool()
    print(f"Built framing pool: {len(pool)} items")
    by_cat: dict[str, int] = {}
    for item in pool:
        by_cat[item.framing_category] = by_cat.get(item.framing_category, 0) + 1
    for cat in sorted(by_cat):
        print(f"  {cat}: {by_cat[cat]}")

    # Sanity: every span resolves and every span has at least one
    # non-stopword token (the topical-disjointness firewall vocabulary).
    for item in pool:
        toks = framing_span_tokens(item)
        if not toks:
            raise ValueError(f"frame {item.frame_id} has empty firewall vocabulary")
        print(f"  {item.frame_id} [{item.framing_category}] firewall tokens: {sorted(toks)}")

    # C-1 drop: write a partial stimulus JSON containing only the framing pool.
    # Subsequent chunks will replace this with the full schema.
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": STIMULUS_SCHEMA_VERSION,
        "framing_pool": framing_pool_dict(pool),
        "main_chains": [],            # C-4
        "frame_positive_chains": [],  # C-4
        "calibration_chains": [],     # C-5
        "_curation_status": "C-1: framing pool only; chains TBD in chunks C-4..C-5",
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(f"Wrote partial stimulus JSON: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
