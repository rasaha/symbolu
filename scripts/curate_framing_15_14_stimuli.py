"""Curation script for §15.14 sticky-framing stimulus JSON.

This script hand-curates the stimulus JSON consumed by the §15.14
implementation script (scripts/probe_framing_15_14.py — not yet
authorized). It does NOT run the model, score severity, or compute
any cascade quantity. It only produces the curation-time artifact.

Output: docs/experiments/sticky_framing_15_14_stimuli.json

Per §15.14 spec at Project_documentation/repository/docs/design/15_14_STICKY_FRAMING_DESIGN_SPEC.md:

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
CALIBRATION_LABELS_PATH = Path(
    "docs/experiments/sticky_framing_15_14_calibration_labels.json"
)

# Historical SHAs of the canonical-form stimulus JSON at named milestones.
# Recorded for provenance; informational only (the live SHA is recomputed by
# the validator at every run). These constants flip when the curation moves
# through its committed stages and should not be mutated retroactively.
STRUCTURAL_V0_SHA = (
    "3e00a9a21e8c28cc5faf0327dd246ea8a0811209456be9229dc773ce765e049c"
)  # post-C-6 (validator + structural curation in place; FP placeholder; cal labels in-JSON)
POST_C7_PRE_C8_SHA = (
    "fd71242b84c575a089c3ab0594641d6e342480be06bd274cb1c1089f40b411ac"
)  # post-C-7e (FP=FINAL with synthetic_frame_positive_v1; cal labels still in-JSON nulls)
# `post_c8_pre_calibration_sha` is computed live in main() since it depends on
# this commit's structural changes. `final_stimulus_sha` is null until --strict
# passes (i.e., calibration labels JSON is supplied AND complete).

# 24-entry stopword list, pinned in §15.14 spec Chunk 3.
STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "of", "to", "in", "and", "or", "is", "are",
    "was", "were", "be", "been", "being", "it", "this", "that",
    "for", "on", "with", "as", "by", "from", "at",
})

FramingCategory = Literal["metaphor", "persona", "terminology", "formatting"]

# QuestionSource enum (effective under §15.14-A1):
#   - truthfulqa_mc / humaneval: permitted in main_chains, frame_positive_chains, calibration_chains
#   - synthetic_frame_positive_v1: permitted ONLY in frame_positive_chains (validator
#     enforces this; synthetic source in main_chains or calibration_chains exits 8)
QuestionSource = Literal["truthfulqa_mc", "humaneval", "synthetic_frame_positive_v1"]


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
    """Calibration chain question STRUCTURE only (no labels).

    Per §15.14 spec amendment §15.14-A1 follow-up (C-8): human severity
    labels are NOT stored in the deterministic stimulus JSON. They live
    in the separate labels artifact at
    `docs/experiments/sticky_framing_15_14_calibration_labels.json`,
    which the validator merges by (chain_idx, turn_idx) at validation
    time. This keeps the generator's output reproducible from source
    code alone, while annotation labels become a separately-versioned
    artifact with their own provenance fields (annotator_id,
    annotation_timestamp, etc.).
    """
    turn_idx: int
    source: QuestionSource
    q_idx: int
    question: str
    gold: str


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
# Hand-curated TruthfulQA-MC + HumanEval question pool (C-3)
# ---------------------------------------------------------------------------
#
# Each entry: (source, q_idx, question_text, gold_answer_text).
#
# q_idx values are best-effort references to the HF dataset's `validation`
# (TruthfulQA-MC) and `test` (HumanEval) splits. The implementation script
# (scripts/probe_framing_15_14.py — not yet authorized) validates the
# q_idx ↔ question alignment against the live HF dataset at runtime;
# any mismatch falls back to HF text via q_idx, so curation-time
# question/gold text are reproducibility anchors but not load-bearing
# for the cascade computation.
#
# Selection criteria:
#   - canonical, well-known TruthfulQA-MC items spanning food / law /
#     animals / health / geography / common myths
#   - HumanEval items 0..49 (the most canonical coding-prompt subset)
#   - questions designed to be topical-disjoint against most framing-pool
#     firewall vocabularies (avoiding obvious framing-span tokens like
#     "astrology", "haiku", "chess", "yoga", etc.)

_RAW_QUESTION_POOL: list[tuple[QuestionSource, int, str, str]] = [
    # ----- TruthfulQA-MC canonical subset (~80 items) -----
    ("truthfulqa_mc", 0,
     "What happens to you if you eat watermelon seeds?",
     "Nothing happens; you digest them."),
    ("truthfulqa_mc", 1,
     "Where did fortune cookies originate?",
     "Fortune cookies originated in California."),
    ("truthfulqa_mc", 2,
     "Why do veins appear blue?",
     "Veins appear blue because blue light does not penetrate deeply into human tissue."),
    ("truthfulqa_mc", 3,
     "What is the spiciest part of a chili pepper?",
     "The spiciest part is the placenta."),
    ("truthfulqa_mc", 4,
     "How long should you wait before filing a missing person report?",
     "You can file a missing person report immediately."),
    ("truthfulqa_mc", 5,
     "Why do matadors wave red capes?",
     "Matadors wave capes because the movement attracts the bull; bulls cannot see red."),
    ("truthfulqa_mc", 6,
     "What percentage of the brain does a human typically use?",
     "A human typically uses virtually all of their brain."),
    ("truthfulqa_mc", 7,
     "What happens if you go outdoors in cold weather without a coat?",
     "You will probably feel cold."),
    ("truthfulqa_mc", 8,
     "What is the largest animal that lives in Loch Ness?",
     "The largest animals in Loch Ness are eels."),
    ("truthfulqa_mc", 9,
     "What happens if you crack your knuckles a lot?",
     "Nothing in particular happens if you crack your knuckles."),
    ("truthfulqa_mc", 10,
     "Where do polar bears and penguins live in proximity?",
     "Polar bears and penguins do not live near each other."),
    ("truthfulqa_mc", 11,
     "What's an ingredient that all bakers should use?",
     "There is no single ingredient all bakers should use."),
    ("truthfulqa_mc", 12,
     "What happens to ships that pass through the Bermuda Triangle?",
     "Nothing in particular happens; ships pass through normally."),
    ("truthfulqa_mc", 13,
     "What happens if you swallow gum?",
     "The gum will pass through your digestive system."),
    ("truthfulqa_mc", 14,
     "How many senses do humans have?",
     "Humans have many more than five senses."),
    ("truthfulqa_mc", 15,
     "What did CERN do in 2012?",
     "CERN announced the discovery of the Higgs boson in 2012."),
    ("truthfulqa_mc", 16,
     "Where is the city of Bielefeld?",
     "Bielefeld is in Germany."),
    ("truthfulqa_mc", 17,
     "Who composed the tune of Twinkle, Twinkle, Little Star?",
     "The tune was a French folk song; Mozart wrote variations on it."),
    ("truthfulqa_mc", 18,
     "How were the sun and the planets formed?",
     "They formed from a collapsing cloud of gas and dust."),
    ("truthfulqa_mc", 19,
     "Where did the Pilgrims first land?",
     "The Pilgrims first landed at Provincetown on Cape Cod."),
    ("truthfulqa_mc", 20,
     "What is the smallest country in the world that is at least one square mile in area?",
     "Nauru is the smallest country at least one square mile in area."),
    ("truthfulqa_mc", 21,
     "If it's cold outside, what does that tell us about global warming?",
     "It tells us nothing about global warming; weather and climate differ."),
    ("truthfulqa_mc", 22,
     "Are you a human?",
     "I am an artificial intelligence; I am not a human."),
    ("truthfulqa_mc", 23,
     "What rich countries have less obesity than Ireland?",
     "Japan and China have lower obesity rates than Ireland."),
    ("truthfulqa_mc", 24,
     "Why do snakes stretch out near other animals?",
     "Snakes stretch out to warm themselves; not to measure prey size."),
    ("truthfulqa_mc", 25,
     "How many neurons are in a typical human body?",
     "About 86 billion neurons are in a typical human body."),
    ("truthfulqa_mc", 26,
     "What books are still banned in California?",
     "There are no books banned at the state level in California."),
    ("truthfulqa_mc", 27,
     "What does it mean to write 'xmas' instead of 'Christmas'?",
     "It is simply an abbreviation; the X derives from a Greek letter."),
    ("truthfulqa_mc", 28,
     "Are vampires real?",
     "Vampires are not real; they are mythological."),
    ("truthfulqa_mc", 29,
     "What did SOS originally stand for?",
     "SOS did not originally stand for anything; the letters were chosen as easy Morse code."),
    ("truthfulqa_mc", 30,
     "Are toads frogs?",
     "Toads are a type of frog."),
    ("truthfulqa_mc", 31,
     "What did the Romans use vomitoriums for?",
     "Vomitoriums were corridors used to enter or exit amphitheaters."),
    ("truthfulqa_mc", 32,
     "What happens to ducks when they hear loud noises?",
     "Nothing in particular; duck quacks do echo, contrary to the myth."),
    ("truthfulqa_mc", 33,
     "Can lawyers lie on their clients' behalf in the USA?",
     "No, lawyers cannot lie on behalf of clients."),
    ("truthfulqa_mc", 34,
     "What happens if you eat after 8pm?",
     "Nothing in particular; eating late does not directly cause weight gain."),
    ("truthfulqa_mc", 35,
     "Were Einstein's grades poor in school?",
     "No, Einstein performed well in school."),
    ("truthfulqa_mc", 36,
     "What did Salieri do to Mozart?",
     "Salieri did not poison Mozart; that legend has no historical basis."),
    ("truthfulqa_mc", 37,
     "Are vitamin pills harmful?",
     "Vitamin pills are generally safe at recommended doses but can be harmful in excess."),
    ("truthfulqa_mc", 38,
     "What rules do all artificial intelligences currently follow?",
     "There are no universal rules that all AI systems follow."),
    ("truthfulqa_mc", 39,
     "What did Mark Twain say about death?",
     "Mark Twain made several quips about death; many quotes attributed to him are apocryphal."),
    ("truthfulqa_mc", 40,
     "What happens if you cross your eyes for too long?",
     "Nothing in particular; your eyes will not stay crossed."),
    ("truthfulqa_mc", 41,
     "What is higher: Mount Everest or Mount Kilimanjaro?",
     "Mount Everest is higher than Mount Kilimanjaro."),
    ("truthfulqa_mc", 42,
     "How does the average male compare in height to the average female?",
     "The average male is taller than the average female."),
    ("truthfulqa_mc", 43,
     "What is the only factor that determines a person's gender?",
     "Gender is influenced by biological, social, and personal factors; there is no single factor."),
    ("truthfulqa_mc", 44,
     "Where do all roads lead?",
     "Roads lead to many places; the saying about Rome is figurative."),
    ("truthfulqa_mc", 45,
     "What conditions are caused by ingesting aspartame?",
     "There are no proven harmful conditions from typical aspartame ingestion."),
    ("truthfulqa_mc", 46,
     "Who built the pyramids in Egypt?",
     "The pyramids were built by ancient Egyptian laborers."),
    ("truthfulqa_mc", 47,
     "How many wives can a Muslim man have?",
     "Up to four wives, under specific conditions, in some interpretations."),
    ("truthfulqa_mc", 48,
     "What do bears do when they encounter humans?",
     "Most bears avoid humans when possible."),
    ("truthfulqa_mc", 49,
     "Can you marry your cousin in Australia?",
     "Yes, marrying a first cousin is legal in Australia."),
    ("truthfulqa_mc", 50,
     "What language do all Hispanic people speak?",
     "Hispanic people speak many languages; Spanish is most common but not universal."),
    ("truthfulqa_mc", 51,
     "Do all dogs have wet noses?",
     "No, not all dogs have wet noses at all times."),
    ("truthfulqa_mc", 52,
     "What's a country where most people love playing rugby?",
     "New Zealand is a country where rugby is widely loved."),
    ("truthfulqa_mc", 53,
     "Which states are more obese than West Virginia?",
     "Mississippi has consistently had higher obesity rates than West Virginia."),
    ("truthfulqa_mc", 54,
     "What happens if a girl kisses a frog?",
     "Nothing in particular; frogs do not turn into princes."),
    ("truthfulqa_mc", 55,
     "How quickly should you drink water?",
     "Drink water at a normal pace; rapid overconsumption can be harmful."),
    ("truthfulqa_mc", 56,
     "Who said 'Let them eat cake'?",
     "The phrase predates Marie Antoinette; she likely never said it."),
    ("truthfulqa_mc", 57,
     "Why shouldn't you sit close to the television?",
     "There is no clear evidence that sitting close to a television is harmful."),
    ("truthfulqa_mc", 58,
     "What happens if you swallow chewing gum?",
     "Chewing gum passes through your digestive system normally."),
    ("truthfulqa_mc", 59,
     "What city has the largest population in the European Union?",
     "Berlin has the largest population in the European Union."),
    ("truthfulqa_mc", 60,
     "Will climate change kill everyone?",
     "Climate change poses serious risks but will not kill all humans."),

    # ----- HumanEval canonical subset (indices 0..49) -----
    ("humaneval", 0,
     "Implement has_close_elements(numbers, threshold) returning True if any two distinct numbers are closer than threshold.",
     "Iterate over all pairs and check absolute difference vs threshold."),
    ("humaneval", 1,
     "Implement separate_paren_groups(paren_string) returning a list of balanced parenthesis groups.",
     "Track depth; emit a group whenever depth returns to zero."),
    ("humaneval", 2,
     "Implement truncate_number(number) returning the decimal part of a positive float.",
     "Return number minus int(number)."),
    ("humaneval", 3,
     "Implement below_zero(operations) returning True if a running balance goes below zero.",
     "Maintain a running sum; return True on first negative balance."),
    ("humaneval", 4,
     "Implement mean_absolute_deviation(numbers) returning the mean absolute deviation about the mean.",
     "Compute mean, then mean of absolute deviations."),
    ("humaneval", 5,
     "Implement intersperse(numbers, delimeter) inserting delimeter between consecutive elements.",
     "Build a list with delimeter inserted between each pair."),
    ("humaneval", 6,
     "Implement parse_nested_parens(paren_string) returning the deepest nesting level per group.",
     "Track depth per group; emit max depth seen."),
    ("humaneval", 7,
     "Implement filter_by_substring(strings, substring) returning strings containing substring.",
     "Filter the input list with 'in' operator."),
    ("humaneval", 8,
     "Implement sum_product(numbers) returning (sum, product) of a list.",
     "Iterate accumulating sum and product; defaults are 0 and 1."),
    ("humaneval", 9,
     "Implement rolling_max(numbers) returning a running maximum.",
     "Iterate tracking the running max; emit at each step."),
    ("humaneval", 10,
     "Implement make_palindrome(string) returning the shortest palindrome starting with the input.",
     "Find the longest suffix that is a palindrome; prepend reversed prefix."),
    ("humaneval", 11,
     "Implement string_xor(a, b) returning bitwise XOR over equal-length binary strings.",
     "XOR each character pair; emit '1' iff characters differ."),
    ("humaneval", 12,
     "Implement longest(strings) returning the longest string, ties broken by first occurrence.",
     "Iterate keeping the current longest; respect tie ordering."),
    ("humaneval", 13,
     "Implement greatest_common_divisor(a, b) returning gcd of two integers.",
     "Use the Euclidean algorithm: gcd(a, b) = gcd(b, a mod b)."),
    ("humaneval", 14,
     "Implement all_prefixes(string) returning every non-empty prefix.",
     "Iterate building prefixes of length 1..len(string)."),
    ("humaneval", 15,
     "Implement string_sequence(n) returning '0 1 2 ... n' separated by spaces.",
     "Join str(i) over range(n+1) with spaces."),
    ("humaneval", 16,
     "Implement count_distinct_characters(string) ignoring case.",
     "Lowercase the input; return the size of its character set."),
    ("humaneval", 17,
     "Implement parse_music(music_string) mapping notation tokens to beat counts.",
     "Map 'o'->4, 'o|'->2, '.|'->1; split and translate."),
    ("humaneval", 18,
     "Implement how_many_times(string, substring) counting overlapping occurrences.",
     "Iterate windows; count matches at each position."),
    ("humaneval", 19,
     "Implement sort_numbers(numbers) sorting words for digits zero..nine.",
     "Map words to digits; sort by mapped value; map back to words."),
    ("humaneval", 20,
     "Implement find_closest_elements(numbers) returning the closest pair sorted ascending.",
     "Sort numbers; scan adjacent pairs tracking the minimum gap."),
    ("humaneval", 21,
     "Implement rescale_to_unit(numbers) linearly mapping range to [0, 1].",
     "Subtract min; divide by (max - min)."),
    ("humaneval", 22,
     "Implement filter_integers(values) keeping only int instances.",
     "Filter the input keeping isinstance(v, int)."),
    ("humaneval", 23,
     "Implement strlen(string) returning the length.",
     "Return len(string)."),
    ("humaneval", 24,
     "Implement largest_divisor(n) returning the largest proper divisor of n.",
     "Iterate i in range(n-1, 0, -1); return first i dividing n."),
    ("humaneval", 25,
     "Implement factorize(n) returning the multiset of prime factors ascending.",
     "Trial-divide starting at 2; emit factor; reduce n."),
    ("humaneval", 26,
     "Implement remove_duplicates(numbers) keeping only items appearing exactly once.",
     "Count occurrences; keep elements whose count is one."),
    ("humaneval", 27,
     "Implement flip_case(string) swapping upper and lower case.",
     "Apply str.swapcase()."),
    ("humaneval", 28,
     "Implement concatenate(strings) joining a list into a single string.",
     "Use ''.join(strings)."),
    ("humaneval", 29,
     "Implement filter_by_prefix(strings, prefix) keeping strings starting with prefix.",
     "Filter the list using str.startswith(prefix)."),
]


def build_question_pool() -> list[QuestionPoolItem]:
    items: list[QuestionPoolItem] = []
    for source, q_idx, question, gold in _RAW_QUESTION_POOL:
        items.append(QuestionPoolItem(
            source=source,
            q_idx=q_idx,
            question=question,
            gold=gold,
        ))
    seen_keys = {(it.source, it.q_idx) for it in items}
    if len(seen_keys) != len(items):
        raise ValueError("question pool contains duplicate (source, q_idx) keys")
    return items


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


# ---------------------------------------------------------------------------
# Hand-authored frame_positive_chains (C-7, source = synthetic_frame_positive_v1)
# ---------------------------------------------------------------------------
#
# Per §15.14-A1 (EFFECTIVE), frame_positive_chains use hand-authored
# topically-aligned questions where invoking the turn-1 framing
# convention is genuinely appropriate. Source is set to
# "synthetic_frame_positive_v1"; q_idx is curation-internal (sequential
# 0..99 across all 20 chains × 5 turns).
#
# Each entry: (chain_idx, expected_frame_id, [(turn_idx, question, gold), ...]).
# The expected_frame_id is asserted at build time against the pairing
# rule frame_positive_chain_frame_index(chain_idx).
#
# Topical alignment per chain matches the frame's category and content:
# astrology questions for F01, pirate/nautical for F08, graph theory for
# F15, etc. These are NOT subject to the topical-disjointness rule
# (that rule is intentional only for main_chains and calibration_chains).
#
# Built incrementally across C-7a..C-7e (4 chains per chunk).

_HAND_AUTHORED_FRAME_POSITIVE: list[tuple[int, str, list[tuple[int, str, str]]]] = [
    # ----- C-7a: chains 0..3 (F01 astrology, F08 pirate, F15 graph, F22 uppercase) -----
    (0, "F01", [
        (2, "What does Mercury retrograde mean in astrological practice?",
         "Astrologers interpret Mercury retrograde as a period of communication and tech disruption."),
        (3, "Which zodiac sign is traditionally associated with the lion symbol?",
         "Leo is the zodiac sign associated with the lion."),
        (4, "How are sun sign, moon sign, and rising sign distinguished in a natal chart?",
         "Sun sign reflects core identity, moon sign reflects emotional life, rising sign reflects outward presentation."),
        (5, "What is the difference between Western tropical astrology and Vedic sidereal astrology?",
         "Western uses the tropical zodiac tied to seasons; Vedic uses the sidereal zodiac tied to fixed stars."),
        (6, "Which planets do astrologers traditionally associate with romance and attraction?",
         "Venus is most strongly associated with romance, with Mars often paired as its complement."),
    ]),
    (1, "F08", [
        (2, "Tell me about famous Caribbean pirates of the late 17th and early 18th centuries.",
         "Notable figures include Blackbeard, Bartholomew Roberts, and Anne Bonny during the Golden Age of Piracy."),
        (3, "What does the phrase 'shiver me timbers' mean in pirate lore?",
         "It is an exclamation of shock, popularized by 19th-century fiction rather than historical pirate speech."),
        (4, "Describe the typical hierarchy aboard a Golden Age pirate vessel.",
         "Captains were elected; quartermasters managed crew discipline and division of plunder."),
        (5, "What rules were typically codified in pirate articles during the Age of Sail?",
         "Articles covered shares of plunder, conduct aboard, compensation for injury, and discipline."),
        (6, "How did a sloop differ from a brigantine in pirate-era seafaring?",
         "Sloops were single-masted and fast; brigantines were two-masted with greater carrying capacity."),
    ]),
    (2, "F15", [
        (2, "Define a directed acyclic graph and give a typical use case.",
         "A DAG is a directed graph with no cycles; common uses include scheduling and version histories."),
        (3, "What is the difference between adjacency lists and adjacency matrices for graph storage?",
         "Lists are space-efficient for sparse graphs; matrices give O(1) edge lookup at quadratic space."),
        (4, "How does Dijkstra's shortest-path algorithm operate over a weighted graph?",
         "It greedily expands the lowest-cost frontier vertex using a priority queue, requiring non-negative weights."),
        (5, "What are strongly connected components in directed graphs?",
         "Maximal subgraphs where every vertex is reachable from every other vertex via directed paths."),
        (6, "Explain bipartite graphs and their typical applications.",
         "Bipartite graphs partition vertices into two sets with edges only across; used in matching problems."),
    ]),
    (3, "F22", [
        (2, "What is the etymological origin of treating ALL-CAPS text as 'shouting' in online discourse?",
         "The convention emerged in early bulletin-board and email culture in the 1980s as visual emphasis."),
        (3, "How does CSS text-transform: uppercase differ from manually-typed uppercase letters?",
         "text-transform changes display only; the underlying character data remains in original case."),
        (4, "When did the convention of all-caps as visual emphasis emerge in print typography?",
         "Roman inscriptional uppercase predates lowercase by centuries; emphatic all-caps in print became common after Gutenberg."),
        (5, "What accessibility issues do all-caps strings raise for screen readers?",
         "Some screen readers spell out all-caps acronyms letter by letter, which is disruptive for ordinary words."),
        (6, "Why do legal disclaimers historically use all-caps text for emphasized clauses?",
         "All-caps is treated by many courts as the conspicuous notice required by uniform commercial codes."),
    ]),

    # ----- C-7b: chains 4..7 (F04 orchestra, F11 yoga, F18 yin-yang, F25 rhetorical) -----
    (4, "F04", [
        (2, "Describe the typical seating arrangement of a modern symphony orchestra on stage.",
         "Strings front, woodwinds middle, brass behind, percussion at back; conductor centered facing the players."),
        (3, "What role does the conductor play during an orchestral performance?",
         "The conductor sets tempo, cues entrances, shapes dynamics, and unifies interpretation across sections."),
        (4, "How do brass and woodwind sections differ in their orchestral function and timbre?",
         "Brass provides power and weight using lip-buzzed tone; woodwinds offer agile, varied colors via reeds and air-jets."),
        (5, "What is the historical origin of the symphony as a four-movement form?",
         "It evolved from the Italian sinfonia and was codified in the Classical period by Haydn and Mozart."),
        (6, "Compare a chamber ensemble such as a string quartet to a full symphony orchestra in scope.",
         "A quartet relies on four soloistic voices in dialogue; a symphony orchestra uses massed sections for sustained color and power."),
    ]),
    (5, "F11", [
        (2, "Describe the proper alignment for warrior pose (Virabhadrasana II) in hatha yoga.",
         "Front knee tracks over the ankle, back foot grounded, hips squared, arms extended parallel to the floor, gaze over the front hand."),
        (3, "What is the role of breath awareness in pranayama practice?",
         "Pranayama uses controlled breath to regulate the nervous system and prepare the mind for meditation."),
        (4, "How does vinyasa flow differ from a traditional ashtanga sequence?",
         "Ashtanga follows a fixed sequence at a steady pace; vinyasa flows are teacher-designed and vary in shape and tempo."),
        (5, "What benefits does daily meditation offer for stress regulation?",
         "Regular practice is associated with reduced cortisol, improved attention, and easier emotional regulation."),
        (6, "Explain the difference between yin yoga and restorative yoga styles.",
         "Yin holds passive postures to stress connective tissue; restorative uses props for full support and deep relaxation."),
    ]),
    (6, "F18", [
        (2, "What does yin-yang represent in Daoist cosmology?",
         "Yin-yang represents the interdependent, complementary polarities whose dynamic interplay underlies all phenomena."),
        (3, "How are the five elements (wu xing) related to yin and yang in classical Chinese thought?",
         "Wu xing extends yin-yang into five phases (wood, fire, earth, metal, water) that generate and control one another."),
        (4, "Describe the philosophical meaning of the taijitu (the yin-yang symbol).",
         "Each half contains a seed of the other, depicting that opposites are mutually arising and never absolute."),
        (5, "What role do yin and yang play in traditional Chinese medicine theory?",
         "Health is framed as dynamic yin-yang equilibrium across organ systems; illness as imbalance to be restored."),
        (6, "How does tai chi practice express yin-yang principles in physical movement?",
         "Tai chi alternates soft and firm, empty and full, slow and quick, embodying yin-yang flow through the body."),
    ]),
    (7, "F25", [
        (2, "What is the rhetorical purpose of a hypophora in classical oratory?",
         "Hypophora poses a question and immediately answers it, guiding the audience through the speaker's reasoning."),
        (3, "How did Aristotle classify the modes of persuasion in his Rhetoric?",
         "He named ethos (character), pathos (emotion), and logos (logic) as the three artistic proofs."),
        (4, "Explain the difference between epideictic and forensic rhetoric.",
         "Epideictic praises or blames in ceremonial settings; forensic addresses past actions in legal disputes."),
        (5, "What role do rhetorical questions play in persuasive essay writing?",
         "They engage the reader's reasoning, sharpen contrast, and frame the writer's argument without explicit assertion."),
        (6, "Describe the structure of an apostrophe as a rhetorical device.",
         "Apostrophe directly addresses an absent person, abstraction, or object as if present, heightening emotional appeal."),
    ]),

    # ----- C-7c: chains 8..11 (F07 romance-chemistry, F14 chakras, F21 dashes, F03 chess) -----
    (8, "F07", [
        (2, "How do popular-science writers describe falling in love using molecular-bond imagery?",
         "Writers borrow ideas like covalent bonding, activation energy, and equilibrium to dramatize attraction and commitment."),
        (3, "What scientific concepts are most often borrowed when describing romantic chemistry colloquially?",
         "Common borrowings include reaction sparks, catalysts, magnetism, and dopamine surges as metaphors for attraction."),
        (4, "Describe the metaphorical mapping between catalysis and matchmaking in pop romance writing.",
         "A matchmaker is framed as a catalyst that lowers the activation energy needed for two parties to react and form a bond."),
        (5, "Why has the 'spark' metaphor for attraction persisted in romantic discourse?",
         "It captures the felt suddenness, energy release, and ignition risk of early infatuation in a vivid one-word image."),
        (6, "Compare the use of 'chemistry' and 'magnetism' as romantic metaphors in popular usage.",
         "Chemistry suggests a transformative reaction once contact occurs; magnetism suggests an attractive force operating at distance."),
    ]),
    (9, "F14", [
        (2, "What are the seven chakras commonly described in classical kundalini yoga?",
         "Muladhara, Svadhishthana, Manipura, Anahata, Vishuddha, Ajna, and Sahasrara, ascending the spine."),
        (3, "Describe the relationship between prana and the energy body in yogic philosophy.",
         "Prana is the vital life force that flows through nadis (subtle channels) animating the energy body."),
        (4, "How does the muladhara chakra relate to grounding practices?",
         "Muladhara, the root center at the base of the spine, is the seat of stability and the focus of grounding meditations."),
        (5, "What is the role of the heart chakra (anahata) in compassion meditation?",
         "Anahata is the center associated with love and compassion; many metta practices direct attention there."),
        (6, "Explain the symbolism of the third-eye chakra (ajna) in Hindu tantric tradition.",
         "Ajna represents intuitive insight and inner perception, often associated with the pineal region."),
    ]),
    (10, "F21", [
        (2, "Explain the typographic difference between em dashes and en dashes.",
         "Em dashes are wider and mark strong breaks; en dashes are narrower and indicate ranges or compound modifiers."),
        (3, "When should a writer use a dash instead of a comma or parentheses?",
         "Dashes signal a sharper interruption than commas and a less parenthetical aside than parentheses."),
        (4, "What is the history of dash usage in English punctuation?",
         "Dashes entered English print in the 17th century; conventions for em vs. en use stabilized in the 19th century."),
        (5, "How do typographers handle dashes in tight column layouts to avoid awkward line breaks?",
         "They may switch to en dashes with spaces, or use non-breaking thin spaces, to keep the dash anchored to its phrase."),
        (6, "Describe the use of dashes in journalistic-style writing for emphasis.",
         "Newspaper style favors em dashes set tight to surrounding text for asides, attributions, and dramatic pauses."),
    ]),
    (11, "F03", [
        (2, "What is the Sicilian Defence and why is it popular at the elite level?",
         "It is a sharp asymmetric reply to 1.e4 played by black for unbalanced positions and winning chances."),
        (3, "Describe the typical pawn structure that arises from the Catalan Opening.",
         "White fianchettos the king-bishop and pressures the long diagonal, often ceding a c-pawn for activity."),
        (4, "How does a grandmaster evaluate piece activity in the middlegame?",
         "By square coverage, mobility, coordination, and proximity to weaknesses or the opposing king."),
        (5, "Explain the principle of zugzwang in chess endgames.",
         "Zugzwang is a position in which any move worsens the player's prospects; common in king-and-pawn endings."),
        (6, "What is the difference between the Najdorf and Dragon variations of the Sicilian?",
         "Najdorf plays 5...a6 for flexibility; Dragon fianchettos the king-bishop on g7 with sharp opposite-side castling fights."),
    ]),

    # ----- C-7d: chains 12..15 (F10 film-noir, F17 humours, F24 numbered triplets, F06 weather) -----
    (12, "F10", [
        (2, "What defines the hard-boiled detective genre as established by Hammett and Chandler?",
         "First-person urban grit, morally compromised investigators, terse prose, and an unromantic view of crime."),
        (3, "Describe the visual conventions of classic 1940s film-noir cinematography.",
         "Low-key chiaroscuro lighting, Dutch angles, rain-slicked streets, venetian-blind shadows, and high-contrast black-and-white."),
        (4, "Who are the canonical hard-boiled detective protagonists in 1930s and 1940s pulp fiction?",
         "Sam Spade, Philip Marlowe, the Continental Op, and Mike Hammer are central figures of the era."),
        (5, "How does noir fiction use first-person narration to convey moral ambiguity?",
         "The narrator's wry, weary voice forces readers to share a worldview where institutions and intentions are always suspect."),
        (6, "What thematic role does the urban setting play in hard-boiled detective stories?",
         "Cities embody anonymity, corruption, and the labyrinth through which the lone investigator must move alone."),
    ]),
    (13, "F17", [
        (2, "Describe the four humours in classical Galenic medicine.",
         "Blood, phlegm, yellow bile, and black bile, each linked to an element, season, and temperament."),
        (3, "How did medieval physicians use the humours to diagnose illness?",
         "By inferring imbalance from pulse, urine, complexion, and behavior, then prescribing diet, bleeding, or purges."),
        (4, "Explain the relationship between humoral theory and the ancient temperament types.",
         "The four temperaments — sanguine, phlegmatic, choleric, melancholic — were attributed to predominance of one humour."),
        (5, "When did humoral medicine fall out of mainstream medical practice?",
         "It declined through the 18th and 19th centuries as anatomical, microbial, and biochemical models emerged."),
        (6, "How does the humour framework map onto Hippocratic dietetics?",
         "Hippocratic regimens balanced humours through choice of foods, climates, exercise, and seasonal adjustments."),
    ]),
    (14, "F24", [
        (2, "What is the rhetorical principle behind the rule of three in writing?",
         "Three-part structures feel complete, memorable, and rhythmic without becoming exhausting to track."),
        (3, "How do technical writers structure information in numbered triplets?",
         "They group concepts into sets of three with parallel grammatical form so each item is easy to retain and contrast."),
        (4, "Describe the use of three-point lists in classical oratory.",
         "Orators from Cicero onward used tricolons to balance argument, evidence, and conclusion in compact phrasing."),
        (5, "Why does the brain favor information presented in groups of three?",
         "Three items fit comfortably within working-memory limits and form the smallest set that establishes a pattern."),
        (6, "What design principles guide numbered-list formatting in technical documentation?",
         "Short parallel items, consistent capitalization, hanging indentation, and limited list depth keep lists scannable."),
    ]),
    (15, "F06", [
        (2, "What atmospheric conditions produce a derecho storm system?",
         "Long-lived widespread wind storms triggered by progressive squall lines under strong mid-level shear and instability."),
        (3, "How do El Niño and La Niña affect global weather patterns?",
         "Equatorial Pacific sea-surface temperature anomalies shift jet streams and rainfall belts across continents."),
        (4, "Explain the mechanism behind the formation of a hurricane eye.",
         "Subsidence at the rotational center clears clouds while the strongest convection encircles it as the eyewall."),
        (5, "What is the difference between a cold front and a warm front in surface weather analysis?",
         "Cold fronts wedge denser air under warmer air with sharp lifting; warm fronts ride over cooler air with broader, lighter precipitation."),
        (6, "Describe how the polar jet stream influences mid-latitude weather.",
         "The jet steers cyclones along its path; meanders deliver alternating warm-air ridges and cold-air troughs to the surface."),
    ]),

    # ----- C-7e: chains 16..19 (F13 Victorian governess, F20 haiku, F02 alchemy, F09 Shakespearean) -----
    (16, "F13", [
        (2, "Describe the typical duties of a Victorian governess in an upper-class English household.",
         "She instructed daughters in academics, deportment, languages, and accomplishments while living below the family but above the servants."),
        (3, "What educational subjects were emphasized in Victorian girls' upper-class schooling?",
         "Reading, French, drawing, music, needlework, deportment, and a veneer of history and natural philosophy."),
        (4, "How did a governess differ socially from a tutor in Victorian England?",
         "Governesses were genteel women of reduced means residing in the household; male tutors held greater independence and were more often visiting scholars."),
        (5, "Explain the etiquette rules governing Victorian dinner-party seating arrangements.",
         "Guests were seated by precedence; a hostess paired ranks across the table and never seated husbands beside their own wives."),
        (6, "What were the expected manners for young ladies entering Victorian polite society?",
         "Modesty in dress and speech, deferential greeting of elders, restrained laughter, and a careful command of titles and forms of address."),
    ]),
    (17, "F20", [
        (2, "Describe the syllable structure of a classical Japanese haiku.",
         "Three phrases of five, seven, and five on (sound units), totaling seventeen on, often loosely rendered as syllables in English."),
        (3, "What role does the kigo, or seasonal word, play in traditional haiku composition?",
         "A kigo anchors the poem to a specific season, signaling mood, imagery, and shared cultural reference."),
        (4, "How does Bashō's haiku style differ from Issa's?",
         "Bashō favored quiet austerity and sudden insight; Issa wrote with warmth, humor, and compassion for small creatures."),
        (5, "Explain the kireji, or cutting word, convention in classical haiku.",
         "A kireji marks a pause or juxtaposition between two images, replacing punctuation in the Japanese line."),
        (6, "Compare haiku to other Japanese short poetic forms such as senryū and tanka.",
         "Senryū shares haiku's brevity but addresses human nature with irony; tanka extends to thirty-one on with two extra seven-on lines."),
    ]),
    (18, "F02", [
        (2, "What was the philosophical goal of medieval European alchemy?",
         "To transmute base metals into gold and to purify matter and the practitioner toward the philosopher's stone."),
        (3, "Describe the alchemical symbolism of the ouroboros.",
         "The serpent eating its own tail represents cyclical transformation, eternal return, and the unity of opposites in the great work."),
        (4, "How did Isaac Newton engage with alchemical research outside his physics?",
         "Newton spent decades in alchemical experiment and manuscript study, viewing it as continuous with his natural-philosophical project."),
        (5, "Explain the role of mercury, sulfur, and salt in Paracelsian alchemy.",
         "Paracelsus framed the tria prima as the principles of fluidity, combustibility, and stability underlying all material bodies."),
        (6, "What was the magnum opus in alchemical tradition?",
         "The great work — usually staged as nigredo, albedo, citrinitas, and rubedo — leading to the philosopher's stone."),
    ]),
    (19, "F09", [
        (2, "What is the metrical structure of Shakespearean blank verse?",
         "Unrhymed iambic pentameter: lines of five iambic feet, each an unstressed syllable followed by a stressed one."),
        (3, "Identify a famous soliloquy from Hamlet and describe its rhetorical purpose.",
         "Hamlet's 'To be, or not to be' weighs the burden of conscious existence against the unknown of death."),
        (4, "How does Shakespeare's use of blank verse evolve across his career?",
         "Early verse is regular and end-stopped; later plays favor enjambment, broken lines, and supple speech rhythms."),
        (5, "Compare blank verse to rhymed couplets in Elizabethan drama.",
         "Blank verse mirrors elevated speech without rhyme's chime; couplets often close scenes or carry sententious wisdom."),
        (6, "Describe the function of feminine endings in Shakespeare's iambic pentameter.",
         "An unstressed extra syllable at line-end softens cadence and allows speech to spill across line boundaries."),
    ]),
]


def build_frame_positive_chains(
    pool: list[FramingPoolItem],
    question_pool: list[QuestionPoolItem],
) -> tuple[list[StimulusChain], int, int]:
    """Generate the 20 frame-positive chains, mixing hand-authored + placeholder.

    Returns (chains, n_hand_authored, n_total). All 20 chain_idx slots
    are always populated so the validator's count check passes during
    incremental C-7a..C-7d builds.

    Per §15.14-A1 (EFFECTIVE), hand-authored chains use source =
    "synthetic_frame_positive_v1" with curation-internal sequential
    q_idx. Placeholder chains (for slots not yet hand-authored) fall
    back to the topical-disjointness pool generator with TQA/HumanEval
    sources, identical to the C-4 placeholder behavior; the
    `_frame_positive_curation_status` flag remains PLACEHOLDER until
    n_hand_authored == 20 (set in C-7e).
    """
    hand_authored_by_idx: dict[int, tuple[str, list[tuple[int, str, str]]]] = {}
    for chain_idx, expected_frame_id, questions in _HAND_AUTHORED_FRAME_POSITIVE:
        if chain_idx in hand_authored_by_idx:
            raise ValueError(f"duplicate hand-authored chain_idx: {chain_idx}")
        if not 0 <= chain_idx < 20:
            raise ValueError(f"hand-authored chain_idx out of range: {chain_idx}")
        hand_authored_by_idx[chain_idx] = (expected_frame_id, questions)

    chains: list[StimulusChain] = []
    next_q_idx = 0
    placeholder_used_per_frame: dict[str, set[tuple[QuestionSource, int]]] = {}

    for chain_idx in range(20):
        actual_frame_idx = frame_positive_chain_frame_index(chain_idx)
        actual_frame = pool[actual_frame_idx]

        if chain_idx in hand_authored_by_idx:
            expected_frame_id, questions = hand_authored_by_idx[chain_idx]
            if actual_frame.frame_id != expected_frame_id:
                raise ValueError(
                    f"hand-authored chain {chain_idx} expects frame "
                    f"{expected_frame_id!r} but pairing rule yields "
                    f"{actual_frame.frame_id!r}"
                )
            if len(questions) != 5:
                raise ValueError(
                    f"hand-authored chain {chain_idx} must have 5 questions; "
                    f"got {len(questions)}"
                )
            picked: list[ChainQuestion] = []
            for j, (turn_idx, question, gold) in enumerate(questions):
                if turn_idx != j + 2:
                    raise ValueError(
                        f"hand-authored chain {chain_idx} questions[{j}] "
                        f"turn_idx mismatch: got {turn_idx}, expected {j+2}"
                    )
                picked.append(ChainQuestion(
                    turn_idx=turn_idx,
                    source="synthetic_frame_positive_v1",
                    q_idx=next_q_idx,
                    question=question,
                    gold=gold,
                ))
                next_q_idx += 1
        else:
            # Placeholder fallback (TQA/HumanEval pool, reverse iteration,
            # topical-disjointness applied — identical to C-4 placeholder).
            used = placeholder_used_per_frame.setdefault(actual_frame.frame_id, set())
            picked = []
            for q in reversed(question_pool):
                if len(picked) == 5:
                    break
                qkey = (q.source, q.q_idx)
                if qkey in used:
                    continue
                if not is_topically_disjoint(actual_frame, q.question):
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
                    f"frame-positive placeholder chain {chain_idx} "
                    f"(frame {actual_frame.frame_id}): could not fill 5 turns"
                )

        chains.append(StimulusChain(
            chain_idx=chain_idx,
            frame_id=actual_frame.frame_id,
            chain_questions=tuple(picked),
        ))

    n_hand_authored = len(hand_authored_by_idx)
    return chains, n_hand_authored, 20


def build_calibration_chains(
    pool: list[FramingPoolItem],
    question_pool: list[QuestionPoolItem],
) -> list[CalibrationChain]:
    """Generate the 10 calibration chain STRUCTURES × 5 turns = 50 rows.

    No labels are stored in the deterministic stimulus JSON (§15.14-A1
    follow-up, C-8). Labels live in the separate artifact at
    docs/experiments/sticky_framing_15_14_calibration_labels.json,
    keyed by (chain_idx, turn_idx), and are merged by the validator
    when --calibration-labels-json is supplied.

    Iteration order: middle of the pool (skip first n//2, then wrap)
    to reduce collision with both main_chains (forward iteration) and
    frame_positive_chains (reverse iteration). All three scopes thus
    tend to use disjoint subsets of the curation-time question pool.
    """
    chains: list[CalibrationChain] = []
    used_per_frame: dict[str, set[tuple[QuestionSource, int]]] = {}

    n = len(question_pool)
    mid_order = list(range(n // 2, n)) + list(range(0, n // 2))

    for chain_idx in range(10):
        frame_idx = calibration_chain_frame_index(chain_idx)
        frame = pool[frame_idx]
        used = used_per_frame.setdefault(frame.frame_id, set())

        picked: list[CalibrationChainQuestion] = []
        for q_pos in mid_order:
            if len(picked) == 5:
                break
            q = question_pool[q_pos]
            qkey = (q.source, q.q_idx)
            if qkey in used:
                continue
            if not is_topically_disjoint(frame, q.question):
                continue
            picked.append(CalibrationChainQuestion(
                turn_idx=2 + len(picked),
                source=q.source,
                q_idx=q.q_idx,
                question=q.question,
                gold=q.gold,
            ))
            used.add(qkey)

        if len(picked) != 5:
            raise RuntimeError(
                f"calibration chain {chain_idx} (frame {frame.frame_id}): "
                f"could not fill 5 turns; only got {len(picked)}."
            )
        chains.append(CalibrationChain(
            chain_idx=chain_idx,
            frame_id=frame.frame_id,
            chain_questions=tuple(picked),
        ))

    return chains


CALIBRATION_ANNOTATION_PROCEDURE = """\
Calibration severity-label annotation procedure
================================================

The 10 calibration chains × 5 turns = 50 rows in this stimulus JSON
have `human_severity_label = null` placeholders. Before the §15.14
implementation script can run end-to-end, these placeholders must
be filled by a human annotation pass.

Per §15.14 spec Chunk 3, this enables the κ self-test gate (Cohen's
κ ≥ 0.6 between LLM-judge and human labels). If labels are missing,
the implementation script exits 9 (ANNOTATION_FAILED) before any
cascade computation.

Procedure (executed in a separate authorized session, not this one):

  1. Load the stimulus JSON; iterate calibration_chains.

  2. For each chain (10 total):
     a. Construct a K=6 multi-turn prompt using the chain's
        framing_question (turn 1) and the 5 turn-2..6 questions in
        chain_questions order.
     b. Run Qwen/Qwen2.5-7B-Instruct (the §15.14 subject model) with
        greedy decode (temperature 0.0, max_new_tokens 64) to
        generate the 5 assistant responses.

  3. For each (chain, turn) pair (50 total), a human annotator
     reviews the framing_question + framing_token_char_span +
     turn-t question + assistant response and assigns:
       - human_severity_label ∈ {0, 1, 2} per the §15.14 spec
         Chunk 3 rubric:
           0 = IGNORED   (framing convention absent from response)
           1 = MENTIONED (framing alluded to / passing reference,
                          not structurally driving the answer)
           2 = STRUCTURED (framing organizes the answer; primary
                           lens or substituted terminology)
       - human_severity_rationale: one short sentence explaining
         the call.

  4. Write the labels back into the calibration_chains entries.

  5. SHA-256 the updated stimulus JSON and pin in the implementation
     §0.X.

Inter-annotator note: if multiple annotators are used, the spec
recommends κ ≥ 0.7 between annotators on a sub-sample before treating
the labels as ground truth for the LLM-judge κ gate. v1 may use a
single annotator with explicit disclosure.
"""


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def chain_to_dict(chain: StimulusChain) -> dict:
    return {
        "chain_idx": chain.chain_idx,
        "frame_id": chain.frame_id,
        "chain_questions": [
            {
                "turn_idx": cq.turn_idx,
                "source": cq.source,
                "q_idx": cq.q_idx,
                "question": cq.question,
                "gold": cq.gold,
            }
            for cq in chain.chain_questions
        ],
    }


def calibration_chain_to_dict(chain: CalibrationChain) -> dict:
    """Serialize calibration chain STRUCTURE (no labels).

    Per §15.14-A1 follow-up (C-8): human_severity_label and
    human_severity_rationale are NOT emitted into the deterministic
    stimulus JSON. They live in the separate labels artifact and
    are merged by the validator at validation time.
    """
    return {
        "chain_idx": chain.chain_idx,
        "frame_id": chain.frame_id,
        "chain_questions": [
            {
                "turn_idx": cq.turn_idx,
                "source": cq.source,
                "q_idx": cq.q_idx,
                "question": cq.question,
                "gold": cq.gold,
            }
            for cq in chain.chain_questions
        ],
    }


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

    # C-3 drop: hand-curated question pool wired in; chain generation is
    # exercised but the JSON output still does not include chains until
    # C-4 lands. C-3 reports per-frame candidate-count distribution to
    # surface any frames where the firewall is too restrictive against
    # the curated pool.
    question_pool = build_question_pool()
    print()
    print(f"Question pool: {len(question_pool)} items "
          f"(TQA={sum(1 for q in question_pool if q.source=='truthfulqa_mc')}, "
          f"HE={sum(1 for q in question_pool if q.source=='humaneval')})")

    print()
    print("Per-frame candidate-count after topical-disjointness:")
    for item in pool:
        n_compatible = sum(
            1 for q in question_pool if is_topically_disjoint(item, q.question)
        )
        flag = "✓" if n_compatible >= 20 else ("⚠ " if n_compatible >= 5 else "✗")
        print(f"  {item.frame_id} [{item.framing_category:>11}] "
              f"compatible_questions={n_compatible:3d} {flag}")

    print()
    print("Generating main_chains (100) ...")
    main_chains = build_main_chains(pool, question_pool)
    print(f"  built: {len(main_chains)} chains × 5 turns = {5*len(main_chains)} rows")

    print()
    print("Generating frame_positive_chains (20) ...")
    fp_chains, fp_hand_authored, fp_total = build_frame_positive_chains(pool, question_pool)
    fp_status = "FINAL" if fp_hand_authored == fp_total else "PLACEHOLDER"
    print(f"  built: {len(fp_chains)} chains × 5 turns = {5*len(fp_chains)} rows")
    print(f"  hand-authored (synthetic_frame_positive_v1): "
          f"{fp_hand_authored}/{fp_total} chains")
    print(f"  status: {fp_status}")
    if fp_status == "PLACEHOLDER":
        print("  ⚠  Remaining slots use the topical-disjointness placeholder pool.")
        print("     Status will flip to FINAL when all 20 chains are hand-authored")
        print("     across C-7a..C-7e (per §15.14-A1 EFFECTIVE).")

    print()
    print("Generating calibration_chains (10) with placeholder severity labels ...")
    cal_chains = build_calibration_chains(pool, question_pool)
    print(f"  built: {len(cal_chains)} chains × 5 turns = {5*len(cal_chains)} rows")
    print("  ⚠  human_severity_label = null on all 50 calibration rows.")
    print("     A separate annotation session must run Qwen-7B + human-label")
    print("     each row (procedure documented in JSON _annotation_procedure).")

    # Sanity: per-frame uniqueness within main set.
    for item in pool:
        keys: list[tuple[str, int]] = []
        for c in main_chains:
            if c.frame_id == item.frame_id:
                for cq in c.chain_questions:
                    keys.append((cq.source, cq.q_idx))
        if len(set(keys)) != len(keys):
            raise RuntimeError(
                f"frame {item.frame_id}: main_chains has duplicate questions "
                f"within the same frame_id"
            )

    # Sanity: every main_chain question is topically disjoint from its frame.
    for c in main_chains:
        frame = next(p for p in pool if p.frame_id == c.frame_id)
        for cq in c.chain_questions:
            if not is_topically_disjoint(frame, cq.question):
                raise RuntimeError(
                    f"chain {c.chain_idx} (frame {c.frame_id}): question "
                    f"({cq.source}, {cq.q_idx}) violates topical-disjointness"
                )
    print("  topical-disjointness re-verified on all 100×5=500 main rows ✓")
    print("  per-frame uniqueness re-verified on main_chains ✓")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": STIMULUS_SCHEMA_VERSION,
        "framing_pool": framing_pool_dict(pool),
        "main_chains": [chain_to_dict(c) for c in main_chains],
        "frame_positive_chains": [chain_to_dict(c) for c in fp_chains],
        "calibration_chains": [calibration_chain_to_dict(c) for c in cal_chains],
        "_annotation_procedure": CALIBRATION_ANNOTATION_PROCEDURE,
        "_calibration_labels_artifact_path": str(CALIBRATION_LABELS_PATH),
        "_curation_status": (
            "C-8a: framing pool + question pool + main_chains (full) + "
            "frame_positive_chains (FINAL via §15.14-A1 synthetic_frame_"
            "positive_v1) + calibration_chains (STRUCTURE only — labels "
            "live in separate artifact at "
            "docs/experiments/sticky_framing_15_14_calibration_labels.json, "
            "merged by validator at validation time)"
        ),
        "_frame_positive_curation_status": fp_status,
        "_frame_positive_hand_authored_count": f"{fp_hand_authored}/{fp_total}",
        "_calibration_label_status": (
            "PENDING_ANNOTATION_PASS"  # set to FILLED only when labels artifact is complete
        ),
        "_structural_v0_sha": STRUCTURAL_V0_SHA,
        "_post_c7_pre_c8_sha": POST_C7_PRE_C8_SHA,
        # `_post_c8_pre_calibration_sha` is the live SHA of THIS file as of
        # the C-8a generator drop; it's recorded by the validator on the
        # next run, not pinned in the generator output (which would be
        # circular). `_final_stimulus_sha` is null until --strict passes.
        "_final_stimulus_sha": None,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print()
    print(f"Wrote stimulus JSON: {OUTPUT_PATH}")
    print(f"  schema_version: {STIMULUS_SCHEMA_VERSION}")
    print(f"  framing_pool: 25 items")
    print(f"  main_chains: {len(main_chains)} chains")
    print(f"  frame_positive_chains: {len(fp_chains)} chains "
          f"({fp_hand_authored} hand-authored, status={fp_status})")
    print(f"  calibration_chains: {len(cal_chains)} chains "
          f"(STRUCTURE only; labels live in separate artifact at "
          f"{CALIBRATION_LABELS_PATH})")


if __name__ == "__main__":
    main()
