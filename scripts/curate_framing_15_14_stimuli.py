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
