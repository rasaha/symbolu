#!/usr/bin/env python3
"""
Probe Cases for PhaseAttention Behavioral Testing
===================================================

15 minimal-pair probes designed to test whether PhaseAttention learns:
- Role binding (who did what)
- Long-range persistence (entity tracking across filler)
- Semantic interference (same token, different sense)
- Negation/polarity resolution

Each probe is designed such that:
1. Token identity alone is insufficient to solve it
2. Recency bias would give wrong answer
3. Correct behavior should degrade specifically when phase is disrupted

If PhaseAttention is learning real relational selectivity, disrupting phases
should break performance on these probes.

Author: Claude (Diagnostic Script for PhaseAttention)
Date: January 2026
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum


class ProbeCategory(Enum):
    """Categories of probes for behavioral testing."""
    ROLE_BINDING = "role_binding"           # Who did what?
    LONG_RANGE = "long_range"               # Entity persistence across distance
    INTERFERENCE = "interference"           # Same token, different sense
    NEGATION_POLARITY = "negation_polarity" # Polarity and scope resolution
    AMPLITUDE_CONFLICT = "amplitude_conflict"  # Phase vs amplitude salience
    CONTROL = "control"                     # Probes where phase SHOULD NOT matter
    BINDING_ONLY = "binding_only"           # Pure binding with symmetric tokens


@dataclass
class MinimalPairProbe:
    """
    A minimal-pair probe for testing relational selectivity.

    Attributes:
        id: Unique identifier (e.g., "RB1", "LP2")
        category: ProbeCategory enum
        text_a: First variant text
        text_b: Second variant (minimal change from text_a)
        question: Question to ask about the text
        answer_a: Correct answer for text_a
        answer_b: Correct answer for text_b
        target_tokens_a: Token(s) that should have high probability for text_a
        target_tokens_b: Token(s) that should have high probability for text_b
        distractor_tokens: Token(s) that recency/token-identity would wrongly predict
        explanation: Why this probe tests phase-based selectivity
    """
    id: str
    category: ProbeCategory
    text_a: str
    text_b: str
    question: str
    answer_a: str
    answer_b: str
    target_tokens_a: List[str]
    target_tokens_b: List[str]
    distractor_tokens: List[str]
    explanation: str


@dataclass
class SingleProbe:
    """
    A single probe (non-minimal-pair) for specific behavioral tests.

    Used for probes where we test one input with/without phase ablation,
    rather than comparing two variants.
    """
    id: str
    category: ProbeCategory
    text: str
    question: str
    correct_answer: str
    target_tokens: List[str]
    distractor_tokens: List[str]
    explanation: str


# =============================================================================
# ROLE BINDING PROBES (RB1-RB5)
# =============================================================================
# These test whether the model can bind pronouns/references to the correct
# antecedent based on semantic compatibility, not just token proximity.

RB1 = MinimalPairProbe(
    id="RB1",
    category=ProbeCategory.ROLE_BINDING,
    text_a="Alice blamed Bob because she was angry.",
    text_b="Alice blamed Bob because he was angry.",
    question="Who was angry?",
    answer_a="Alice",
    answer_b="Bob",
    target_tokens_a=["Alice", " Alice"],
    target_tokens_b=["Bob", " Bob"],
    distractor_tokens=["Bob", " Bob"],  # For A, recency would wrongly suggest Bob
    explanation="Tests pronoun resolution. 'she' must bind to Alice, 'he' to Bob. "
                "Phase should encode semantic role compatibility (blamer is typically angry)."
)

RB2 = MinimalPairProbe(
    id="RB2",
    category=ProbeCategory.ROLE_BINDING,
    text_a="John thanked Mark because he helped with the project.",
    text_b="John thanked Mark because John helped with the project.",
    question="Who helped?",
    answer_a="Mark",
    answer_b="John",
    target_tokens_a=["Mark", " Mark"],
    target_tokens_b=["John", " John"],
    distractor_tokens=["Mark", " Mark"],  # Explicit name in B should flip binding
    explanation="Tests reflexive vs other-reference. 'he' (helper) should be Mark "
                "(thanked person helps). Explicit 'John' forces different binding."
)

RB3 = MinimalPairProbe(
    id="RB3",
    category=ProbeCategory.ROLE_BINDING,
    text_a="Sarah apologized to Emma because she felt guilty.",
    text_b="Sarah apologized to Emma because Emma felt guilty.",
    question="Who felt guilty?",
    answer_a="Sarah",
    answer_b="Emma",
    target_tokens_a=["Sarah", " Sarah"],
    target_tokens_b=["Emma", " Emma"],
    distractor_tokens=["Emma", " Emma"],  # Recency bias toward Emma
    explanation="Tests semantic role binding. Apologizing implies guilt, so 'she' binds "
                "to Sarah. Explicit 'Emma' overrides this semantic preference."
)

RB4 = MinimalPairProbe(
    id="RB4",
    category=ProbeCategory.ROLE_BINDING,
    text_a="The lawyer called the client because he was late.",
    text_b="The lawyer called the client because the client was late.",
    question="Who was late?",
    answer_a="the lawyer",  # Ambiguous - could be either in A
    answer_b="the client",
    target_tokens_a=["lawyer", " lawyer", "client", " client"],  # Both valid for ambiguous A
    target_tokens_b=["client", " client"],
    distractor_tokens=["client", " client"],
    explanation="Tests ambiguity handling. In A, 'he' is genuinely ambiguous. "
                "In B, explicit naming resolves it. Model should show lower confidence "
                "or entropy in A if it recognizes ambiguity."
)

RB5 = MinimalPairProbe(
    id="RB5",
    category=ProbeCategory.ROLE_BINDING,
    text_a="Tom warned Jim that he was in danger.",
    text_b="Tom warned Jim that Jim was in danger.",
    question="Who was in danger?",
    answer_a="Jim",  # 'he' in warning context typically refers to warned person
    answer_b="Jim",
    target_tokens_a=["Jim", " Jim"],
    target_tokens_b=["Jim", " Jim"],
    distractor_tokens=["Tom", " Tom"],
    explanation="Control probe - both variants should give Jim. This tests that "
                "explicit naming doesn't flip when semantic role is already clear. "
                "Useful for catching models that over-rely on explicit reference."
)

# =============================================================================
# LONG-RANGE PERSISTENCE PROBES (LP1-LP4)
# =============================================================================
# These test whether the model maintains entity salience across filler material.
# Phase should enable selective persistence of the correct entity.

LP1 = SingleProbe(
    id="LP1",
    category=ProbeCategory.LONG_RANGE,
    text="John entered the room. Mary left early. The meeting continued for hours. After a long delay, he spoke.",
    question="Who spoke?",
    correct_answer="John",
    target_tokens=["John", " John"],
    distractor_tokens=["Mary", " Mary"],  # Mary is mentioned between John and 'he'
    explanation="Tests entity persistence across filler. 'he' must bind to John despite "
                "Mary being mentioned more recently. Phase should maintain John's salience."
)

LP2 = SingleProbe(
    id="LP2",
    category=ProbeCategory.LONG_RANGE,
    text="Maria picked up the violin. The lights dimmed. The crowd waited. Minutes later, she played beautifully.",
    question="Who played?",
    correct_answer="Maria",
    target_tokens=["Maria", " Maria"],
    distractor_tokens=["crowd", " crowd", "violin", " violin"],
    explanation="Tests entity persistence with action continuity. Maria-violin-played "
                "forms a semantic chain that phase should preserve across filler."
)

LP3 = SingleProbe(
    id="LP3",
    category=ProbeCategory.LONG_RANGE,
    text="The captain spoke to the crew. Many tasks were assigned. After the storm passed, he relaxed.",
    question="Who relaxed?",
    correct_answer="captain",
    target_tokens=["captain", " captain", "Captain", " Captain"],
    distractor_tokens=["crew", " crew", "storm", " storm"],
    explanation="Tests role-based persistence. 'he' should bind to 'captain' (singular male) "
                "not 'crew' (plural) despite crew being mentioned in between."
)

LP4 = SingleProbe(
    id="LP4",
    category=ProbeCategory.LONG_RANGE,
    text="John spoke to Mary. The assistant took notes. Later, he signed the document.",
    question="Who signed the document?",
    correct_answer="John",
    target_tokens=["John", " John"],
    distractor_tokens=["assistant", " assistant", "Mary", " Mary"],  # Decoy nouns in between
    explanation="Tests selective binding with decoy. 'assistant' is a closer noun but "
                "phase should maintain John's salience as the primary agent in context."
)

# =============================================================================
# INTERFERENCE / SAME-TOKEN DIFFERENT-SENSE PROBES (SI1-SI3)
# =============================================================================
# These test whether phase prevents semantic blending when the same token
# appears with different meanings.

SI1 = SingleProbe(
    id="SI1",
    category=ProbeCategory.INTERFERENCE,
    text="The bank approved the loan. The river flooded the bank. The financial report mentioned the bank again.",
    question="What does the last 'bank' refer to?",
    correct_answer="financial institution",
    target_tokens=["financial", " financial", "institution", " institution", "money", " money"],
    distractor_tokens=["river", " river", "water", " water"],
    explanation="Tests sense disambiguation. Phase should encode the financial sense for "
                "the final 'bank' based on 'financial report' context, not blend with river sense."
)

SI2 = SingleProbe(
    id="SI2",
    category=ProbeCategory.INTERFERENCE,
    text="He sat by the bass. The band tuned the bass. Then the bass was too loud.",
    question="What does the last 'bass' refer to?",
    correct_answer="musical instrument",
    target_tokens=["instrument", " instrument", "guitar", " guitar", "music", " music"],
    distractor_tokens=["fish", " fish", "water", " water"],
    explanation="Tests sense selection with interference. Initial 'bass' could be fish, "
                "but 'band tuned' shifts to instrument. Final reference should follow band context."
)

SI3 = SingleProbe(
    id="SI3",
    category=ProbeCategory.INTERFERENCE,
    text="The crane flew over the lake. The crane lifted the steel beam. The crane moved again.",
    question="What does the last 'crane' refer to?",
    correct_answer="construction machine",
    target_tokens=["machine", " machine", "construction", " construction", "equipment", " equipment"],
    distractor_tokens=["bird", " bird", "flew", " flew"],
    explanation="Tests local continuity over initial sense. First 'crane' is bird, "
                "second is machine. Final 'crane moved' should follow machine context (local)."
)

# =============================================================================
# NEGATION / POLARITY MINIMAL PAIRS (NP1-NP3)
# =============================================================================
# These test whether phase helps preserve clause-level polarity and scope.

NP1 = MinimalPairProbe(
    id="NP1",
    category=ProbeCategory.NEGATION_POLARITY,
    text_a="The trophy doesn't fit in the suitcase because it is too big.",
    text_b="The trophy doesn't fit in the suitcase because it is too small.",
    question="What is too big/small?",
    answer_a="trophy",
    answer_b="suitcase",
    target_tokens_a=["trophy", " trophy", "Trophy"],
    target_tokens_b=["suitcase", " suitcase", "Suitcase"],
    distractor_tokens=["suitcase", " suitcase"],  # Wrong in A
    explanation="Classic Winograd schema. 'too big' must refer to trophy (it doesn't fit "
                "because it's oversized), 'too small' to suitcase (container too small)."
)

NP2 = MinimalPairProbe(
    id="NP2",
    category=ProbeCategory.NEGATION_POLARITY,
    text_a="The city council refused the demonstrators a permit because they feared violence.",
    text_b="The city council refused the demonstrators a permit because they advocated violence.",
    question="Who feared/advocated violence?",
    answer_a="city council",
    answer_b="demonstrators",
    target_tokens_a=["council", " council", "city", " city"],
    target_tokens_b=["demonstrators", " demonstrators", "protesters", " protesters"],
    distractor_tokens=["demonstrators", " demonstrators"],  # Wrong in A
    explanation="Tests reason-based role binding. 'feared' implies council's motive for "
                "refusing. 'advocated' implies demonstrators' behavior causing refusal."
)

NP3 = SingleProbe(
    id="NP3",
    category=ProbeCategory.NEGATION_POLARITY,
    text="He didn't say the plan would fail until later.",
    question="When did he say the plan would fail?",
    correct_answer="later",
    target_tokens=["later", " later", "Later"],
    distractor_tokens=["didn't", " didn't", "not", " not", "never"],
    explanation="Tests negation scope. 'didn't say X until later' means he DID say it later, "
                "not that he never said it. Phase should help track negation scope correctly."
)


# =============================================================================
# AMPLITUDE VS PHASE CONFLICT PROBES (AC1-AC3)
# =============================================================================
# These test whether the model uses phase for relational binding rather than
# just high-amplitude (salient/repeated) tokens. If phase is working correctly,
# relational binding should NOT be dominated by amplitude salience.

AC1 = SingleProbe(
    id="AC1",
    category=ProbeCategory.AMPLITUDE_CONFLICT,
    text="IMPORTANT IMPORTANT IMPORTANT. The quiet assistant fixed the bug. IMPORTANT IMPORTANT IMPORTANT. Later, he was promoted.",
    question="Who was promoted?",
    correct_answer="assistant",
    target_tokens=["assistant", " assistant", "The assistant", " The assistant"],
    distractor_tokens=["IMPORTANT", " IMPORTANT", "important"],
    explanation="Tests whether amplitude (via repetition) dominates phase-based binding. "
                "'IMPORTANT' has high salience due to repetition and caps, but 'he' must "
                "bind to 'assistant' based on semantic role, not token frequency."
)

AC2 = SingleProbe(
    id="AC2",
    category=ProbeCategory.AMPLITUDE_CONFLICT,
    text="URGENT URGENT URGENT. The technician repaired the server. CRITICAL CRITICAL CRITICAL. She received a bonus.",
    question="Who received a bonus?",
    correct_answer="technician",
    target_tokens=["technician", " technician", "The technician", " The technician"],
    distractor_tokens=["URGENT", " URGENT", "CRITICAL", " CRITICAL", "server", " server"],
    explanation="Tests selective binding with amplitude noise. High-salience tokens surround "
                "the reference, but 'she' must bind to the semantic agent 'technician'."
)

AC3 = SingleProbe(
    id="AC3",
    category=ProbeCategory.AMPLITUDE_CONFLICT,
    text="ERROR ERROR ERROR. The developer debugged the code. WARNING WARNING WARNING. Finally, they shipped the feature.",
    question="Who shipped the feature?",
    correct_answer="developer",
    target_tokens=["developer", " developer", "The developer", " The developer"],
    distractor_tokens=["ERROR", " ERROR", "WARNING", " WARNING", "code", " code"],
    explanation="Tests pronoun resolution against amplitude distractors. 'they' (used singularly) "
                "must bind to 'developer' despite high-amplitude noise tokens."
)

AC4 = MinimalPairProbe(
    id="AC4",
    category=ProbeCategory.AMPLITUDE_CONFLICT,
    text_a="The LOUD LOUD LOUD engineer designed the system. The quiet manager reviewed it. He approved the design.",
    text_b="The quiet engineer designed the system. The LOUD LOUD LOUD manager reviewed it. He approved the design.",
    question="Who approved the design?",
    answer_a="manager",  # 'He approved' after 'manager reviewed'
    answer_b="manager",  # Same - semantic role matters, not amplitude
    target_tokens_a=["manager", " manager", "Manager"],
    target_tokens_b=["manager", " manager", "Manager"],
    distractor_tokens=["engineer", " engineer", "LOUD", " LOUD"],
    explanation="Tests whether amplitude shifts binding. In both cases, 'He approved' follows "
                "'manager reviewed', so semantic continuity should bind to manager. "
                "If amplitude dominates, the model might wrongly bind to the LOUD-marked entity."
)


# =============================================================================
# CONTROL PROBES (CTRL1-CTRL3)
# =============================================================================
# These probes test simple factual recall where phase SHOULD NOT matter.
# They serve as validation that the ablation machinery itself is working.
# Expected: Baseline ≈ Scramble ≈ Frozen ≈ Phase-Off

CTRL1 = SingleProbe(
    id="CTRL1",
    category=ProbeCategory.CONTROL,
    text="Alice is a doctor.",
    question="What is Alice?",
    correct_answer="doctor",
    target_tokens=["doctor", " doctor", "Doctor"],
    distractor_tokens=["nurse", " nurse", "patient", " patient"],
    explanation="Simple factual recall. No relational binding needed. "
                "Phase disruption should NOT affect this probe significantly. "
                "If it does, the ablation machinery may be too aggressive."
)

CTRL2 = SingleProbe(
    id="CTRL2",
    category=ProbeCategory.CONTROL,
    text="The sky is blue.",
    question="What color is the sky?",
    correct_answer="blue",
    target_tokens=["blue", " blue", "Blue"],
    distractor_tokens=["red", " red", "green", " green"],
    explanation="Basic attribute recall. No entity tracking or binding required. "
                "Phase should not be necessary for this simple fact lookup."
)

CTRL3 = SingleProbe(
    id="CTRL3",
    category=ProbeCategory.CONTROL,
    text="Paris is the capital of France.",
    question="What is the capital of France?",
    correct_answer="Paris",
    target_tokens=["Paris", " Paris"],
    distractor_tokens=["London", " London", "Berlin", " Berlin"],
    explanation="Factual knowledge retrieval. No relational structure to track. "
                "This validates that ablations don't break basic functionality."
)


# =============================================================================
# BINDING-ONLY PROBES (BIND1-BIND3)
# =============================================================================
# These probes test pure relational binding where token identity is symmetric.
# Only the relational structure differs, isolating phase-based binding.

BIND1 = MinimalPairProbe(
    id="BIND1",
    category=ProbeCategory.BINDING_ONLY,
    text_a="The key opened the door because it was old.",
    text_b="The key opened the door because it was rusty.",
    question="What does 'it' refer to?",
    answer_a="door",  # old → door (doors get old, keys less so idiomatically)
    answer_b="key",   # rusty → key (metal keys rust, doors less commonly)
    target_tokens_a=["door", " door", "Door"],
    target_tokens_b=["key", " key", "Key"],
    distractor_tokens=[],
    explanation="Pure binding test. Same structure, same tokens, but 'old' biases "
                "toward door (aging) while 'rusty' biases toward key (metal). "
                "Tests whether phase captures subtle semantic compatibility."
)

BIND2 = MinimalPairProbe(
    id="BIND2",
    category=ProbeCategory.BINDING_ONLY,
    text_a="The bottle fell off the table because it was slippery.",
    text_b="The bottle fell off the table because it was tilted.",
    question="What was slippery/tilted?",
    answer_a="bottle",  # slippery → bottle surface
    answer_b="table",   # tilted → table orientation
    target_tokens_a=["bottle", " bottle", "Bottle"],
    target_tokens_b=["table", " table", "Table"],
    distractor_tokens=[],
    explanation="Binding shifts based on property compatibility. Slippery is a surface "
                "property (bottle), tilted is an orientation property (table). "
                "Same sentence structure, different binding based on semantics."
)

BIND3 = MinimalPairProbe(
    id="BIND3",
    category=ProbeCategory.BINDING_ONLY,
    text_a="The woman told the girl that she had won the prize.",
    text_b="The woman told the girl that she would receive a prize.",
    question="Who won/will receive the prize?",
    answer_a="girl",   # 'had won' → reporting news to the winner
    answer_b="girl",   # 'would receive' → also the girl (same structure)
    target_tokens_a=["girl", " girl", "Girl"],
    target_tokens_b=["girl", " girl", "Girl"],
    distractor_tokens=["woman", " woman", "Woman"],
    explanation="Control: both variants should bind 'she' to 'girl' (recipient of news). "
                "Tests consistency of binding under similar semantic frames."
)


# =============================================================================
# AGGREGATE PROBE COLLECTIONS
# =============================================================================

# All minimal-pair probes (for A/B comparison testing)
MINIMAL_PAIR_PROBES: List[MinimalPairProbe] = [
    RB1, RB2, RB3, RB4, RB5,
    NP1, NP2,
    AC4,
    BIND1, BIND2, BIND3,
]

# All single probes (for ablation testing)
SINGLE_PROBES: List[SingleProbe] = [
    LP1, LP2, LP3, LP4,
    SI1, SI2, SI3,
    NP3,
    AC1, AC2, AC3,
    CTRL1, CTRL2, CTRL3,
]

# All probes by category
PROBES_BY_CATEGORY = {
    ProbeCategory.ROLE_BINDING: [RB1, RB2, RB3, RB4, RB5],
    ProbeCategory.LONG_RANGE: [LP1, LP2, LP3, LP4],
    ProbeCategory.INTERFERENCE: [SI1, SI2, SI3],
    ProbeCategory.NEGATION_POLARITY: [NP1, NP2, NP3],
    ProbeCategory.AMPLITUDE_CONFLICT: [AC1, AC2, AC3, AC4],
    ProbeCategory.CONTROL: [CTRL1, CTRL2, CTRL3],
    ProbeCategory.BINDING_ONLY: [BIND1, BIND2, BIND3],
}


def get_all_probe_ids() -> List[str]:
    """Return all probe IDs in order."""
    return [p.id for p in MINIMAL_PAIR_PROBES] + [p.id for p in SINGLE_PROBES]


def get_probe_by_id(probe_id: str) -> Optional[MinimalPairProbe | SingleProbe]:
    """Look up a probe by its ID."""
    for probe in MINIMAL_PAIR_PROBES:
        if probe.id == probe_id:
            return probe
    for probe in SINGLE_PROBES:
        if probe.id == probe_id:
            return probe
    return None


# =============================================================================
# PROMPT CONSTRUCTION UTILITIES
# =============================================================================

def construct_qa_prompt(text: str, question: str) -> str:
    """
    Construct a QA-style prompt for the model.

    Format:
        Context: {text}
        Question: {question}
        Answer:
    """
    return f"Context: {text}\nQuestion: {question}\nAnswer:"


def construct_completion_prompt(text: str, continuation_start: str = "") -> str:
    """
    Construct a completion-style prompt.

    Format:
        {text} {continuation_start}
    """
    if continuation_start:
        return f"{text} {continuation_start}"
    return text


if __name__ == "__main__":
    # Print all probes for verification
    print("=" * 70)
    print("PhaseAttention Behavioral Probe Suite")
    print("=" * 70)

    print(f"\nTotal probes: {len(MINIMAL_PAIR_PROBES) + len(SINGLE_PROBES)}")
    print(f"  Minimal-pair probes: {len(MINIMAL_PAIR_PROBES)}")
    print(f"  Single probes: {len(SINGLE_PROBES)}")

    print("\n" + "-" * 70)
    print("MINIMAL-PAIR PROBES")
    print("-" * 70)
    for probe in MINIMAL_PAIR_PROBES:
        print(f"\n[{probe.id}] {probe.category.value}")
        print(f"  A: {probe.text_a}")
        print(f"  B: {probe.text_b}")
        print(f"  Q: {probe.question}")
        print(f"  A_answer: {probe.answer_a}, B_answer: {probe.answer_b}")

    print("\n" + "-" * 70)
    print("SINGLE PROBES")
    print("-" * 70)
    for probe in SINGLE_PROBES:
        print(f"\n[{probe.id}] {probe.category.value}")
        print(f"  Text: {probe.text}")
        print(f"  Q: {probe.question}")
        print(f"  Answer: {probe.correct_answer}")
