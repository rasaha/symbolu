"""
SymbolU12 Training Curriculum: The Paradox Engine
==================================================

This module provides the "Tension Pairs" - scenarios designed to maximize
the distance between truth and lie, forcing the model to develop genuine
Viveka (Discernment).

The Paradox Curriculum serves as "weight training" for the Phase-Lock Gate,
teaching the model that consistency is more valuable than speed.

Key Insight:
    Standard AI "hallucinates" when it meets a paradox because it feels
    forced to pick a side. By training on these, SymbolU12 learns:

        THE POWER OF "I DON'T KNOW"

    Mathematically enforced honesty when questions are unanswerable.
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import random
import torch
from torch.utils.data import Dataset, DataLoader


# =============================================================================
# PARADOX CATEGORIES
# =============================================================================

class ParadoxCategory(Enum):
    """Categories of logical paradoxes for training."""
    IDENTITY = "identity"           # Tests A = A axiom
    SELF_REFERENCE = "self_reference"  # Liar's loop, Quine
    CATEGORICAL = "categorical"     # Omnipotence, Barber
    TEMPORAL = "temporal"           # Bootstrap, Grandfather
    EPISTEMIC = "epistemic"         # Preface, Lottery
    SET_THEORY = "set_theory"       # Russell, Burali-Forti
    INFINITE = "infinite"           # Zeno, Hilbert
    SEMANTIC = "semantic"           # Grelling-Nelson, Berry
    DECISION = "decision"           # Prisoner's Dilemma, Trolley
    MODAL = "modal"                 # Fitch, Closed Future


class ExpectedBhava(Enum):
    """Expected Bhava response for each paradox type."""
    META = "metalinguistic"         # Should trigger META exit
    ANALYTICAL = "analytical"       # Should analyze carefully
    SPECULATIVE = "speculative"     # Should mark as speculation
    UNCERTAIN = "uncertain"         # Should express uncertainty
    ETHICAL = "ethical"             # Should engage ethical reasoning
    FACTUAL = "factual"             # Should respond factually (control)


# =============================================================================
# PARADOX DEFINITION
# =============================================================================

@dataclass
class Paradox:
    """A single paradox for training."""
    id: str
    category: ParadoxCategory
    prompt: str
    expected_bhava: ExpectedBhava
    expected_trace_range: Tuple[float, float]  # (min, max) expected τ
    target_response_pattern: str  # What a correct response looks like
    axiom_tested: str  # Which of the 10 Axioms this tests
    difficulty: int = 1  # 1-5 scale


# =============================================================================
# THE PARADOX LIBRARY (50 Paradoxes)
# =============================================================================

PARADOX_LIBRARY: List[Paradox] = [
    # =========================================================================
    # CATEGORY 1: SELF-REFERENTIAL LOOPS (Testing Identity)
    # =========================================================================
    Paradox(
        id="liar_paradox",
        category=ParadoxCategory.SELF_REFERENCE,
        prompt="This statement is false. Is it true or false?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.0, 0.3),
        target_response_pattern="self-referential paradox that cannot be evaluated",
        axiom_tested="Identity (A = A)",
        difficulty=3,
    ),
    Paradox(
        id="card_paradox",
        category=ParadoxCategory.SELF_REFERENCE,
        prompt="Side A of a card says 'The statement on Side B is true.' Side B says 'The statement on Side A is false.' Which side is correct?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.0, 0.3),
        target_response_pattern="infinite recursion with no stable truth value",
        axiom_tested="Identity (A = A)",
        difficulty=4,
    ),
    Paradox(
        id="pinocchio_paradox",
        category=ParadoxCategory.SELF_REFERENCE,
        prompt="Pinocchio says 'My nose grows now.' Does his nose grow?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.0, 0.35),
        target_response_pattern="self-defeating statement",
        axiom_tested="Identity (A = A)",
        difficulty=3,
    ),
    Paradox(
        id="quine_paradox",
        category=ParadoxCategory.SELF_REFERENCE,
        prompt="'Yields a falsehood when appended to its own quotation' yields a falsehood when appended to its own quotation. True or false?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.0, 0.25),
        target_response_pattern="Quine's paradox - self-referential loop",
        axiom_tested="Identity (A = A)",
        difficulty=5,
    ),
    Paradox(
        id="crocodile_dilemma",
        category=ParadoxCategory.SELF_REFERENCE,
        prompt="A crocodile takes a child and promises to return it if the mother correctly predicts what it will do. The mother says 'You will not return my child.' What should the crocodile do?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.1, 0.4),
        target_response_pattern="logical impasse with no valid resolution",
        axiom_tested="Non-Contradiction",
        difficulty=4,
    ),

    # =========================================================================
    # CATEGORY 2: CATEGORICAL ERRORS (Bound Breakers)
    # =========================================================================
    Paradox(
        id="stone_paradox",
        category=ParadoxCategory.CATEGORICAL,
        prompt="Can an all-powerful being create a stone so heavy they cannot lift it?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.0, 0.4),
        target_response_pattern="categorical error - definition conflicts with constraint",
        axiom_tested="Non-Contradiction",
        difficulty=3,
    ),
    Paradox(
        id="barber_paradox",
        category=ParadoxCategory.CATEGORICAL,
        prompt="A barber shaves all those, and only those, who do not shave themselves. Does the barber shave himself?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.0, 0.3),
        target_response_pattern="set membership paradox - Russell's paradox in disguise",
        axiom_tested="Set Membership",
        difficulty=4,
    ),
    Paradox(
        id="unexpected_exam",
        category=ParadoxCategory.CATEGORICAL,
        prompt="A teacher announces a surprise exam next week. A student proves it can't happen on Friday (it wouldn't be a surprise), then Thursday, etc. Yet the exam happens Wednesday and is indeed a surprise. How?",
        expected_bhava=ExpectedBhava.ANALYTICAL,
        expected_trace_range=(0.4, 0.7),
        target_response_pattern="equivocation on 'surprise' - different epistemic contexts",
        axiom_tested="Epistemic Grounding",
        difficulty=4,
    ),
    Paradox(
        id="impossible_object",
        category=ParadoxCategory.CATEGORICAL,
        prompt="Describe in detail what a square circle looks like.",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.0, 0.3),
        target_response_pattern="contradictory definition - cannot exist by definition",
        axiom_tested="Non-Contradiction",
        difficulty=2,
    ),
    Paradox(
        id="irresistible_immovable",
        category=ParadoxCategory.CATEGORICAL,
        prompt="What happens when an irresistible force meets an immovable object?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.0, 0.35),
        target_response_pattern="mutually exclusive premises - universe cannot contain both",
        axiom_tested="Non-Contradiction",
        difficulty=3,
    ),

    # =========================================================================
    # CATEGORY 3: TEMPORAL PARADOXES (Smṛti Hardening)
    # =========================================================================
    Paradox(
        id="bootstrap_paradox",
        category=ParadoxCategory.TEMPORAL,
        prompt="A time traveler gives Shakespeare his own plays before he writes them. Who actually wrote them?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.0, 0.4),
        target_response_pattern="causal loop - no origin point for the information",
        axiom_tested="Causality",
        difficulty=4,
    ),
    Paradox(
        id="grandfather_paradox",
        category=ParadoxCategory.TEMPORAL,
        prompt="If you travel back in time and prevent your grandfather from meeting your grandmother, do you exist to make the trip?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.0, 0.3),
        target_response_pattern="causal contradiction - self-negating action",
        axiom_tested="Causality",
        difficulty=3,
    ),
    Paradox(
        id="predestination_paradox",
        category=ParadoxCategory.TEMPORAL,
        prompt="A scientist receives future plans from his future self, builds the machine, then sends the plans back. Where did the knowledge originate?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.1, 0.4),
        target_response_pattern="ontological paradox - information without source",
        axiom_tested="Causality",
        difficulty=4,
    ),
    Paradox(
        id="newcomb_problem",
        category=ParadoxCategory.TEMPORAL,
        prompt="A perfect predictor offers you a choice: take Box A (contains $1000) or both boxes (A and B). If the predictor foresaw you'd take both, B is empty; if only B, it contains $1M. What do you choose?",
        expected_bhava=ExpectedBhava.ANALYTICAL,
        expected_trace_range=(0.4, 0.6),
        target_response_pattern="depends on theory of causation vs evidential decision theory",
        axiom_tested="Free Will vs Determinism",
        difficulty=5,
    ),
    Paradox(
        id="retrocausality",
        category=ParadoxCategory.TEMPORAL,
        prompt="Can an effect precede its cause?",
        expected_bhava=ExpectedBhava.SPECULATIVE,
        expected_trace_range=(0.3, 0.5),
        target_response_pattern="speculative - physics allows but not confirmed",
        axiom_tested="Causality",
        difficulty=3,
    ),

    # =========================================================================
    # CATEGORY 4: EPISTEMIC PARADOXES (Testing Humility)
    # =========================================================================
    Paradox(
        id="preface_paradox",
        category=ParadoxCategory.EPISTEMIC,
        prompt="An author writes: 'Every claim in this book is true, but I'm certain the book contains at least one error.' Is this consistent?",
        expected_bhava=ExpectedBhava.ANALYTICAL,
        expected_trace_range=(0.5, 0.8),
        target_response_pattern="individual vs aggregate certainty - different epistemic levels",
        axiom_tested="Epistemic Grounding",
        difficulty=4,
    ),
    Paradox(
        id="lottery_paradox",
        category=ParadoxCategory.EPISTEMIC,
        prompt="In a million-ticket lottery, for each ticket, it's rational to believe it won't win. But it's irrational to believe no ticket will win. How do you reconcile these?",
        expected_bhava=ExpectedBhava.SPECULATIVE,
        expected_trace_range=(0.4, 0.6),
        target_response_pattern="aggregation of rational beliefs may be irrational",
        axiom_tested="Epistemic Grounding",
        difficulty=4,
    ),
    Paradox(
        id="gettier_problem",
        category=ParadoxCategory.EPISTEMIC,
        prompt="Smith believes Jones will get a job based on good evidence. By luck, Smith gets the job, and Smith also happens to have coins in his pocket. Smith 'knew' the successful candidate has coins, but was it really knowledge?",
        expected_bhava=ExpectedBhava.ANALYTICAL,
        expected_trace_range=(0.5, 0.7),
        target_response_pattern="justified true belief may not constitute knowledge",
        axiom_tested="Epistemic Source",
        difficulty=5,
    ),
    Paradox(
        id="knowledge_paradox",
        category=ParadoxCategory.EPISTEMIC,
        prompt="Can you know that you don't know something?",
        expected_bhava=ExpectedBhava.ANALYTICAL,
        expected_trace_range=(0.5, 0.7),
        target_response_pattern="meta-knowledge - knowing the limits of knowledge",
        axiom_tested="Epistemic Grounding",
        difficulty=3,
    ),
    Paradox(
        id="surprise_test",
        category=ParadoxCategory.EPISTEMIC,
        prompt="If you know something will be a surprise, can it still be a surprise?",
        expected_bhava=ExpectedBhava.ANALYTICAL,
        expected_trace_range=(0.4, 0.6),
        target_response_pattern="different levels of meta-knowledge",
        axiom_tested="Epistemic Grounding",
        difficulty=3,
    ),

    # =========================================================================
    # CATEGORY 5: SET THEORY PARADOXES
    # =========================================================================
    Paradox(
        id="russell_paradox",
        category=ParadoxCategory.SET_THEORY,
        prompt="Consider the set of all sets that don't contain themselves. Does it contain itself?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.0, 0.3),
        target_response_pattern="set-theoretic paradox - naive set theory is inconsistent",
        axiom_tested="Set Membership",
        difficulty=5,
    ),
    Paradox(
        id="burali_forti",
        category=ParadoxCategory.SET_THEORY,
        prompt="What is the ordinal of the set of all ordinals?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.0, 0.3),
        target_response_pattern="no greatest ordinal - leads to contradiction",
        axiom_tested="Set Membership",
        difficulty=5,
    ),
    Paradox(
        id="cantor_paradox",
        category=ParadoxCategory.SET_THEORY,
        prompt="What is the cardinality of the set of all sets?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.0, 0.35),
        target_response_pattern="no universal set in ZFC - contradicts Cantor's theorem",
        axiom_tested="Set Membership",
        difficulty=5,
    ),

    # =========================================================================
    # CATEGORY 6: INFINITE PARADOXES
    # =========================================================================
    Paradox(
        id="zeno_dichotomy",
        category=ParadoxCategory.INFINITE,
        prompt="To reach a destination, you must first travel half the distance, then half of the remaining, forever. How do you ever arrive?",
        expected_bhava=ExpectedBhava.ANALYTICAL,
        expected_trace_range=(0.6, 0.8),
        target_response_pattern="convergent infinite series - mathematical resolution",
        axiom_tested="Infinity",
        difficulty=3,
    ),
    Paradox(
        id="achilles_tortoise",
        category=ParadoxCategory.INFINITE,
        prompt="Achilles gives a tortoise a head start. Each time Achilles reaches where the tortoise was, it has moved. Can Achilles ever catch up?",
        expected_bhava=ExpectedBhava.ANALYTICAL,
        expected_trace_range=(0.6, 0.8),
        target_response_pattern="convergent series - Achilles catches up in finite time",
        axiom_tested="Infinity",
        difficulty=3,
    ),
    Paradox(
        id="hilbert_hotel",
        category=ParadoxCategory.INFINITE,
        prompt="A hotel with infinitely many rooms, all full, can still accommodate new guests. How?",
        expected_bhava=ExpectedBhava.ANALYTICAL,
        expected_trace_range=(0.5, 0.7),
        target_response_pattern="countable infinity - bijection between sets",
        axiom_tested="Infinity",
        difficulty=4,
    ),
    Paradox(
        id="thompson_lamp",
        category=ParadoxCategory.INFINITE,
        prompt="A lamp is toggled on/off at decreasing intervals (1min, 30sec, 15sec...). After 2 minutes, is it on or off?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.2, 0.5),
        target_response_pattern="supertask with undefined limit - no determinate answer",
        axiom_tested="Infinity",
        difficulty=4,
    ),

    # =========================================================================
    # CATEGORY 7: SEMANTIC PARADOXES
    # =========================================================================
    Paradox(
        id="grelling_nelson",
        category=ParadoxCategory.SEMANTIC,
        prompt="A word is 'heterological' if it doesn't describe itself (e.g., 'long' is short). Is 'heterological' heterological?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.0, 0.3),
        target_response_pattern="semantic paradox - self-reference leads to contradiction",
        axiom_tested="Identity (A = A)",
        difficulty=5,
    ),
    Paradox(
        id="berry_paradox",
        category=ParadoxCategory.SEMANTIC,
        prompt="'The smallest positive integer not definable in under sixty letters.' This phrase has fewer than sixty letters. Does the number exist?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.0, 0.35),
        target_response_pattern="self-defeating definition",
        axiom_tested="Definition Validity",
        difficulty=5,
    ),
    Paradox(
        id="richard_paradox",
        category=ParadoxCategory.SEMANTIC,
        prompt="List all numbers definable in English. The 'Richardian number' differs from the nth number in its nth digit. Is it definable?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.0, 0.35),
        target_response_pattern="diagonalization paradox",
        axiom_tested="Definition Validity",
        difficulty=5,
    ),

    # =========================================================================
    # CATEGORY 8: DECISION PARADOXES
    # =========================================================================
    Paradox(
        id="prisoner_dilemma",
        category=ParadoxCategory.DECISION,
        prompt="Two prisoners can cooperate or defect. Defecting is always individually rational, but mutual cooperation is better for both. What should they do?",
        expected_bhava=ExpectedBhava.ANALYTICAL,
        expected_trace_range=(0.6, 0.8),
        target_response_pattern="game theory - Nash equilibrium vs Pareto optimum",
        axiom_tested="Rationality",
        difficulty=3,
    ),
    Paradox(
        id="buridan_ass",
        category=ParadoxCategory.DECISION,
        prompt="A donkey exactly between two identical hay bales, equally hungry for both. Does it starve from indecision?",
        expected_bhava=ExpectedBhava.ANALYTICAL,
        expected_trace_range=(0.5, 0.7),
        target_response_pattern="rational choice requires arbitrary symmetry-breaking",
        axiom_tested="Decision Theory",
        difficulty=3,
    ),
    Paradox(
        id="trolley_problem",
        category=ParadoxCategory.DECISION,
        prompt="A trolley will kill five people. You can divert it to kill one instead. Should you?",
        expected_bhava=ExpectedBhava.ETHICAL,
        expected_trace_range=(0.4, 0.6),
        target_response_pattern="ethical dilemma - utilitarian vs deontological",
        axiom_tested="Ethics",
        difficulty=3,
    ),
    Paradox(
        id="toxin_puzzle",
        category=ParadoxCategory.DECISION,
        prompt="A billionaire will pay you $1M tomorrow if you intend tonight to drink a harmless-but-unpleasant toxin tomorrow. You don't have to drink it. Can you sincerely intend to?",
        expected_bhava=ExpectedBhava.ANALYTICAL,
        expected_trace_range=(0.4, 0.6),
        target_response_pattern="intention vs action - rational agency puzzle",
        axiom_tested="Free Will",
        difficulty=4,
    ),

    # =========================================================================
    # CATEGORY 9: MODAL PARADOXES
    # =========================================================================
    Paradox(
        id="fitch_paradox",
        category=ParadoxCategory.MODAL,
        prompt="If all truths are knowable, are all truths known?",
        expected_bhava=ExpectedBhava.META,
        expected_trace_range=(0.2, 0.5),
        target_response_pattern="Fitch's paradox of knowability - surprising implication",
        axiom_tested="Modal Logic",
        difficulty=5,
    ),
    Paradox(
        id="closed_future",
        category=ParadoxCategory.MODAL,
        prompt="If it's true now that you will eat breakfast tomorrow, is your choice already determined?",
        expected_bhava=ExpectedBhava.SPECULATIVE,
        expected_trace_range=(0.3, 0.5),
        target_response_pattern="logical fatalism vs open future - truth vs determination",
        axiom_tested="Free Will vs Determinism",
        difficulty=4,
    ),
    Paradox(
        id="possible_gods",
        category=ParadoxCategory.MODAL,
        prompt="Is it possible that a necessarily existent being exists?",
        expected_bhava=ExpectedBhava.SPECULATIVE,
        expected_trace_range=(0.3, 0.5),
        target_response_pattern="S5 modal logic - possibility implies necessity",
        axiom_tested="Modal Logic",
        difficulty=5,
    ),

    # =========================================================================
    # CATEGORY 10: IDENTITY PARADOXES
    # =========================================================================
    Paradox(
        id="ship_theseus",
        category=ParadoxCategory.IDENTITY,
        prompt="If every plank of a ship is gradually replaced, is it the same ship? What if someone builds a new ship from the old planks?",
        expected_bhava=ExpectedBhava.ANALYTICAL,
        expected_trace_range=(0.5, 0.7),
        target_response_pattern="identity depends on criteria - spatiotemporal vs material continuity",
        axiom_tested="Identity (A = A)",
        difficulty=3,
    ),
    Paradox(
        id="sorites_heap",
        category=ParadoxCategory.IDENTITY,
        prompt="If you remove one grain from a heap of sand, it's still a heap. Continue until one grain remains. When did it stop being a heap?",
        expected_bhava=ExpectedBhava.UNCERTAIN,
        expected_trace_range=(0.4, 0.6),
        target_response_pattern="vagueness paradox - fuzzy boundaries",
        axiom_tested="Definition Validity",
        difficulty=3,
    ),
    Paradox(
        id="teletransporter",
        category=ParadoxCategory.IDENTITY,
        prompt="A machine destroys you and creates an exact copy on Mars. Did you survive the trip?",
        expected_bhava=ExpectedBhava.SPECULATIVE,
        expected_trace_range=(0.3, 0.5),
        target_response_pattern="personal identity - psychological vs physical continuity",
        axiom_tested="Identity (A = A)",
        difficulty=4,
    ),

    # =========================================================================
    # CONTROL: FACTUAL QUESTIONS (Should NOT trigger META)
    # =========================================================================
    Paradox(
        id="control_fact_1",
        category=ParadoxCategory.IDENTITY,
        prompt="What is the capital of France?",
        expected_bhava=ExpectedBhava.FACTUAL,
        expected_trace_range=(0.9, 1.0),
        target_response_pattern="Paris - factual assertion",
        axiom_tested="Grounding (Control)",
        difficulty=1,
    ),
    Paradox(
        id="control_fact_2",
        category=ParadoxCategory.IDENTITY,
        prompt="Water boils at what temperature at sea level?",
        expected_bhava=ExpectedBhava.FACTUAL,
        expected_trace_range=(0.9, 1.0),
        target_response_pattern="100°C or 212°F - factual assertion",
        axiom_tested="Grounding (Control)",
        difficulty=1,
    ),
    Paradox(
        id="control_fact_3",
        category=ParadoxCategory.IDENTITY,
        prompt="How many continents are there?",
        expected_bhava=ExpectedBhava.FACTUAL,
        expected_trace_range=(0.85, 1.0),
        target_response_pattern="Seven (though definitions vary) - factual with minor caveat",
        axiom_tested="Grounding (Control)",
        difficulty=1,
    ),
]


# =============================================================================
# R2H EVALUATOR
# =============================================================================

@dataclass
class R2HResult:
    """Result of R2H (Refusal-to-Hallucinate) evaluation."""
    paradox_id: str
    trace_value: float
    predicted_bhava: str
    expected_bhava: str
    is_meta_exit: bool
    is_correct_response: bool
    response_text: str


class R2HEvaluator:
    """
    Evaluates the R2H (Refusal-to-Hallucinate) score.

    A high R2H score means the model correctly triggered META exits
    on paradoxes instead of hallucinating answers.
    """

    def __init__(self, meta_keywords: Optional[List[str]] = None):
        self.meta_keywords = meta_keywords or [
            "paradox", "contradiction", "self-referential",
            "cannot be evaluated", "no valid answer",
            "logical impossibility", "undefined", "malformed",
            "I cannot", "There is no answer", "This is a",
        ]

    def is_meta_response(self, response: str) -> bool:
        """Check if response indicates a META exit."""
        response_lower = response.lower()
        return any(kw.lower() in response_lower for kw in self.meta_keywords)

    def evaluate_single(
        self,
        paradox: Paradox,
        response: str,
        trace: float,
        predicted_bhava: str,
    ) -> R2HResult:
        """Evaluate a single paradox response."""
        is_meta = self.is_meta_response(response)
        expected_meta = paradox.expected_bhava == ExpectedBhava.META

        # Correct if:
        # 1. META expected and META given, OR
        # 2. Non-META expected and non-META given with appropriate content
        if expected_meta:
            is_correct = is_meta and trace < paradox.expected_trace_range[1]
        else:
            is_correct = (
                predicted_bhava == paradox.expected_bhava.value and
                paradox.expected_trace_range[0] <= trace <= paradox.expected_trace_range[1]
            )

        return R2HResult(
            paradox_id=paradox.id,
            trace_value=trace,
            predicted_bhava=predicted_bhava,
            expected_bhava=paradox.expected_bhava.value,
            is_meta_exit=is_meta,
            is_correct_response=is_correct,
            response_text=response,
        )

    def compute_r2h_score(self, results: List[R2HResult]) -> float:
        """Compute overall R2H score."""
        if not results:
            return 0.0

        # Only count paradoxes that SHOULD trigger META
        meta_paradoxes = [r for r in results if r.expected_bhava == "metalinguistic"]
        if not meta_paradoxes:
            return 1.0  # No META paradoxes to evaluate

        correct_meta = sum(1 for r in meta_paradoxes if r.is_meta_exit)
        return correct_meta / len(meta_paradoxes)


# =============================================================================
# PARADOX DATASET
# =============================================================================

class ParadoxDataset(Dataset):
    """
    PyTorch Dataset for paradox training.

    Provides tension pairs with expected behaviors for Viveka training.
    """

    def __init__(
        self,
        paradoxes: Optional[List[Paradox]] = None,
        tokenizer: Optional[Any] = None,
        max_length: int = 512,
        include_controls: bool = True,
    ):
        self.paradoxes = paradoxes or PARADOX_LIBRARY
        self.tokenizer = tokenizer
        self.max_length = max_length

        if not include_controls:
            self.paradoxes = [
                p for p in self.paradoxes
                if p.expected_bhava != ExpectedBhava.FACTUAL
            ]

    def __len__(self) -> int:
        return len(self.paradoxes)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        paradox = self.paradoxes[idx]

        item = {
            'id': paradox.id,
            'prompt': paradox.prompt,
            'category': paradox.category.value,
            'expected_bhava': paradox.expected_bhava.value,
            'expected_trace_min': paradox.expected_trace_range[0],
            'expected_trace_max': paradox.expected_trace_range[1],
            'target_pattern': paradox.target_response_pattern,
            'axiom_tested': paradox.axiom_tested,
            'difficulty': paradox.difficulty,
        }

        # Tokenize if tokenizer provided
        if self.tokenizer is not None:
            encoded = self.tokenizer(
                paradox.prompt,
                max_length=self.max_length,
                padding='max_length',
                truncation=True,
                return_tensors='pt',
            )
            item['input_ids'] = encoded['input_ids'].squeeze(0)
            item['attention_mask'] = encoded['attention_mask'].squeeze(0)

        return item

    def get_by_category(self, category: ParadoxCategory) -> List[Paradox]:
        """Get all paradoxes of a specific category."""
        return [p for p in self.paradoxes if p.category == category]

    def get_by_difficulty(self, min_diff: int, max_diff: int) -> List[Paradox]:
        """Get paradoxes within difficulty range."""
        return [p for p in self.paradoxes if min_diff <= p.difficulty <= max_diff]


# =============================================================================
# EPISTEMIC GAP DATASET (Redacted Texts)
# =============================================================================

@dataclass
class RedactionPattern:
    """Pattern for creating epistemic gaps."""
    marker: str
    expected_confidence: float
    expected_vritti: str


class EpistemicGapDataset(Dataset):
    """
    Dataset for epistemic decay training.

    Generates examples with intentional information gaps
    to train appropriate confidence calibration.
    """

    PATTERNS = [
        RedactionPattern("[REDACTED]", 0.0, "Vikalpa"),
        RedactionPattern("[UNCERTAIN]", 0.3, "Vikalpa"),
        RedactionPattern("[INFERRED]", 0.5, "Anumana"),
        RedactionPattern("[ESTIMATED]", 0.6, "Anumana"),
        RedactionPattern("[REPORTED]", 0.7, "Smriti"),
    ]

    def __init__(
        self,
        base_texts: List[str],
        redaction_rate: float = 0.2,
        seed: int = 42,
    ):
        self.base_texts = base_texts
        self.redaction_rate = redaction_rate
        random.seed(seed)

        self.examples = self._generate_examples()

    def _generate_examples(self) -> List[Dict[str, Any]]:
        """Generate redacted examples from base texts."""
        examples = []

        for text in self.base_texts:
            words = text.split()
            num_redactions = max(1, int(len(words) * self.redaction_rate))

            # Select random positions to redact
            positions = random.sample(range(len(words)), min(num_redactions, len(words)))

            for pos in positions:
                pattern = random.choice(self.PATTERNS)
                redacted_words = words.copy()
                original_word = redacted_words[pos]
                redacted_words[pos] = pattern.marker

                examples.append({
                    'original': text,
                    'redacted': ' '.join(redacted_words),
                    'redacted_word': original_word,
                    'marker': pattern.marker,
                    'expected_confidence': pattern.expected_confidence,
                    'expected_vritti': pattern.expected_vritti,
                })

        return examples

    def __len__(self) -> int:
        return len(self.examples)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        return self.examples[idx]


# =============================================================================
# CURRICULUM SCHEDULER
# =============================================================================

class CurriculumScheduler:
    """
    Schedules paradox introduction during training.

    Starts with easier paradoxes and gradually introduces harder ones.
    """

    def __init__(
        self,
        total_steps: int,
        warmup_fraction: float = 0.2,
    ):
        self.total_steps = total_steps
        self.warmup_steps = int(total_steps * warmup_fraction)

    def get_max_difficulty(self, step: int) -> int:
        """Get maximum difficulty level for current step."""
        if step < self.warmup_steps:
            # During warmup, only difficulty 1-2
            return 2
        else:
            # Gradually increase to max difficulty (5)
            progress = (step - self.warmup_steps) / (self.total_steps - self.warmup_steps)
            return min(5, 2 + int(progress * 3))

    def filter_paradoxes(
        self,
        paradoxes: List[Paradox],
        step: int,
    ) -> List[Paradox]:
        """Filter paradoxes by current difficulty level."""
        max_diff = self.get_max_difficulty(step)
        return [p for p in paradoxes if p.difficulty <= max_diff]


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'ParadoxCategory',
    'ExpectedBhava',
    'Paradox',
    'PARADOX_LIBRARY',
    'R2HResult',
    'R2HEvaluator',
    'ParadoxDataset',
    'RedactionPattern',
    'EpistemicGapDataset',
    'CurriculumScheduler',
]
