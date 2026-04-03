"""
Sovereign-1 Validation: The "Bank" Disambiguation Test
=======================================================

The "Hello World" of Sovereign AI - proving the model separates
identical words based on semantic context.

Test Cases:
1. "The bank approved the loan." → Financial institution (ARTIFACT/SOCIAL)
2. "The bank was muddy." → River bank (NATURAL_BODY)

Pass Criteria:
- Cosine similarity between "bank" embeddings < 0.4 (different objects)
- Failure if similarity > 0.8 (hallucinating/sleeping)

The test validates that the 128-D State Partition correctly encodes
ontological differences despite identical phonetic signatures.

Reference: SOVEREIGN_1_DESIGN_IMPLEMENTATION.md Section 2.4
"""

from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass
import torch
import torch.nn.functional as F


@dataclass
class DisambiguationResult:
    """Result of a disambiguation test."""
    word: str
    context_a: str
    context_b: str
    embedding_a: torch.Tensor
    embedding_b: torch.Tensor
    cosine_similarity: float
    passed: bool
    expected_r_signal_a: str
    expected_r_signal_b: str
    actual_r_signal_a: Optional[str] = None
    actual_r_signal_b: Optional[str] = None


class BankDisambiguationTest:
    """
    The Bank Disambiguation Test: Proof of Sovereign Cognition.

    This test verifies that the Sovereign-1 architecture can distinguish
    between homonyms based on semantic context, not just phonetic signature.

    The word "bank" appears in two contexts:
    1. Financial: "The bank approved the loan" → ARTIFACT/SOCIAL ontology
    2. Natural: "The bank was muddy" → NATURAL_BODY ontology

    Success Criteria:
    - Cosine similarity of "bank" embeddings < 0.4 (sees them as different)
    - R-Signal aligns with correct ontological layer

    Usage:
        test = BankDisambiguationTest(model, tokenizer)
        result = test.run()

        if result.passed:
            print("Model distinguishes bank (financial) from bank (river)")
        else:
            print(f"FAILED: Similarity {result.cosine_similarity:.2f} too high")
    """

    # Bhava names for R-Signal interpretation
    BHAVA_NAMES = [
        "O1_POTENTIAL", "O2_IDENTITY", "O3_EXECUTION", "O4_STRUCTURE",
        "O5_COGNITION", "O6_AGENCY", "O7_REASONING", "O8_PURPOSE",
        "O9_WITNESSES", "O10_UNIFYING", "O11_INTEGRATION", "O12_ABSOLVING"
    ]

    # Test sentences
    FINANCIAL_CONTEXT = "The bank approved the loan."
    NATURAL_CONTEXT = "The bank was muddy."

    # Target word
    TARGET_WORD = "bank"

    # Expected ontologies
    FINANCIAL_ONTOLOGIES = {"O3_EXECUTION", "O4_STRUCTURE", "O6_AGENCY"}  # Social/Artifact
    NATURAL_ONTOLOGIES = {"O1_POTENTIAL", "O4_STRUCTURE", "O5_COGNITION"}  # Natural body

    # Thresholds
    SIMILARITY_PASS_THRESHOLD = 0.4   # Must be BELOW this to pass
    SIMILARITY_FAIL_THRESHOLD = 0.8   # Above this = complete failure

    def __init__(
        self,
        model: torch.nn.Module,
        tokenizer: Any,
        device: Optional[torch.device] = None,
    ):
        """
        Initialize the Bank Disambiguation Test.

        Args:
            model: SovereignTransformer model
            tokenizer: Tokenizer with encode/decode methods
            device: Target device (cuda/cpu)
        """
        self.model = model
        self.tokenizer = tokenizer
        self.device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        self.model.eval()

    def _find_word_position(
        self,
        tokens: torch.Tensor,
        target_word: str,
    ) -> int:
        """
        Find the token position of the target word.

        Args:
            tokens: [1, N] token IDs
            target_word: Word to find

        Returns:
            Token position index
        """
        # Decode each token and find match
        for i in range(tokens.shape[1]):
            token_str = self.tokenizer.decode([tokens[0, i].item()])
            # Handle various tokenizer formats (with/without space prefix)
            if target_word.lower() in token_str.lower().strip():
                return i

        raise ValueError(f"Target word '{target_word}' not found in tokens")

    def _extract_embedding(
        self,
        text: str,
        target_word: str,
    ) -> Tuple[torch.Tensor, torch.Tensor, str]:
        """
        Extract embedding for target word in context.

        Args:
            text: Full sentence
            target_word: Word to extract embedding for

        Returns:
            (full_embedding, state_delta, dominant_bhava)
        """
        # Tokenize
        tokens = self.tokenizer.encode(text, return_tensors='pt')
        tokens = tokens.to(self.device)

        # Find target word position
        word_pos = self._find_word_position(tokens, target_word)

        # Forward pass
        with torch.no_grad():
            outputs = self.model(tokens)

        # Extract embedding at target position
        hidden_states = outputs['hidden_states']
        word_embedding = hidden_states[0, word_pos]  # [D]

        # Extract state delta (last 128 dims)
        if word_embedding.shape[0] >= 128:
            state_delta = word_embedding[-128:]
        else:
            # Fallback: use full embedding
            state_delta = word_embedding

        # Determine dominant R-Signal (Bhava)
        r_signal = state_delta[48:96] if state_delta.shape[0] >= 96 else state_delta
        r_signal = r_signal.view(12, -1).mean(dim=-1) if r_signal.shape[0] >= 12 else r_signal[:12]
        dominant_idx = r_signal.argmax().item()
        dominant_bhava = self.BHAVA_NAMES[dominant_idx] if dominant_idx < 12 else "UNKNOWN"

        return word_embedding, state_delta, dominant_bhava

    def run(self) -> DisambiguationResult:
        """
        Run the Bank Disambiguation Test.

        Returns:
            DisambiguationResult with test outcome
        """
        print("\n" + "=" * 60)
        print("BANK DISAMBIGUATION TEST")
        print("=" * 60)

        # Extract embeddings for both contexts
        print(f"\nContext A: \"{self.FINANCIAL_CONTEXT}\"")
        emb_a, state_a, bhava_a = self._extract_embedding(
            self.FINANCIAL_CONTEXT, self.TARGET_WORD
        )
        print(f"  → Dominant R-Signal: {bhava_a}")

        print(f"\nContext B: \"{self.NATURAL_CONTEXT}\"")
        emb_b, state_b, bhava_b = self._extract_embedding(
            self.NATURAL_CONTEXT, self.TARGET_WORD
        )
        print(f"  → Dominant R-Signal: {bhava_b}")

        # Compute cosine similarity
        similarity = F.cosine_similarity(
            emb_a.unsqueeze(0),
            emb_b.unsqueeze(0),
        ).item()

        print(f"\n📊 Cosine Similarity: {similarity:.4f}")

        # Determine pass/fail
        passed = similarity < self.SIMILARITY_PASS_THRESHOLD

        if passed:
            print(f"✅ PASSED: Similarity {similarity:.4f} < {self.SIMILARITY_PASS_THRESHOLD}")
            print("   Model correctly distinguishes 'bank' (financial) from 'bank' (river)")
        elif similarity > self.SIMILARITY_FAIL_THRESHOLD:
            print(f"❌ CRITICAL FAILURE: Similarity {similarity:.4f} > {self.SIMILARITY_FAIL_THRESHOLD}")
            print("   Model is hallucinating - sees both 'bank' as identical!")
        else:
            print(f"⚠️ MARGINAL: Similarity {similarity:.4f} between thresholds")
            print("   Model partially distinguishes contexts")

        # Check ontology alignment
        print(f"\n📋 Ontology Analysis:")
        print(f"   Financial context: {bhava_a} (expected: {self.FINANCIAL_ONTOLOGIES})")
        print(f"   Natural context: {bhava_b} (expected: {self.NATURAL_ONTOLOGIES})")

        ontology_correct_a = bhava_a in self.FINANCIAL_ONTOLOGIES
        ontology_correct_b = bhava_b in self.NATURAL_ONTOLOGIES

        if ontology_correct_a and ontology_correct_b:
            print("   ✅ Both ontology alignments correct")
        elif ontology_correct_a or ontology_correct_b:
            print("   ⚠️ Partial ontology alignment")
        else:
            print("   ❌ Ontology misalignment")

        print("=" * 60 + "\n")

        return DisambiguationResult(
            word=self.TARGET_WORD,
            context_a=self.FINANCIAL_CONTEXT,
            context_b=self.NATURAL_CONTEXT,
            embedding_a=emb_a.cpu(),
            embedding_b=emb_b.cpu(),
            cosine_similarity=similarity,
            passed=passed,
            expected_r_signal_a="O3_EXECUTION/O4_STRUCTURE",
            expected_r_signal_b="O1_POTENTIAL/O4_STRUCTURE",
            actual_r_signal_a=bhava_a,
            actual_r_signal_b=bhava_b,
        )


class HomonymTestSuite:
    """
    Extended test suite for homonym disambiguation.

    Tests multiple homonyms beyond "bank":
    - "bat" (animal vs sports equipment)
    - "bark" (tree vs dog sound)
    - "light" (illumination vs weight)
    - "spring" (season vs water source vs coil)
    """

    TEST_CASES = [
        {
            "word": "bank",
            "contexts": [
                ("The bank approved the loan.", {"O3_EXECUTION", "O4_STRUCTURE"}),
                ("The bank was muddy and slippery.", {"O1_POTENTIAL", "O4_STRUCTURE"}),
            ],
        },
        {
            "word": "bat",
            "contexts": [
                ("The bat flew out of the cave.", {"O1_POTENTIAL", "O2_IDENTITY"}),
                ("He swung the bat at the ball.", {"O3_EXECUTION", "O4_STRUCTURE"}),
            ],
        },
        {
            "word": "bark",
            "contexts": [
                ("The bark of the oak tree was rough.", {"O1_POTENTIAL", "O4_STRUCTURE"}),
                ("The dog began to bark loudly.", {"O3_EXECUTION", "O5_COGNITION"}),
            ],
        },
        {
            "word": "light",
            "contexts": [
                ("The light from the sun was warm.", {"O1_POTENTIAL", "O5_COGNITION"}),
                ("The bag was surprisingly light.", {"O4_STRUCTURE", "O5_COGNITION"}),
            ],
        },
    ]

    def __init__(
        self,
        model: torch.nn.Module,
        tokenizer: Any,
        device: Optional[torch.device] = None,
        similarity_threshold: float = 0.4,
    ):
        self.model = model
        self.tokenizer = tokenizer
        self.device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.similarity_threshold = similarity_threshold

    def run_all(self) -> Dict[str, DisambiguationResult]:
        """Run all homonym tests."""
        results = {}

        for test_case in self.TEST_CASES:
            word = test_case["word"]
            contexts = test_case["contexts"]

            # Create test for this word
            test = BankDisambiguationTest(
                model=self.model,
                tokenizer=self.tokenizer,
                device=self.device,
            )

            # Override test parameters
            test.TARGET_WORD = word
            test.FINANCIAL_CONTEXT = contexts[0][0]
            test.NATURAL_CONTEXT = contexts[1][0]
            test.FINANCIAL_ONTOLOGIES = contexts[0][1]
            test.NATURAL_ONTOLOGIES = contexts[1][1]
            test.SIMILARITY_PASS_THRESHOLD = self.similarity_threshold

            results[word] = test.run()

        return results

    def print_summary(self, results: Dict[str, DisambiguationResult]):
        """Print summary of all test results."""
        print("\n" + "=" * 60)
        print("HOMONYM DISAMBIGUATION SUITE - SUMMARY")
        print("=" * 60)

        passed = 0
        failed = 0

        for word, result in results.items():
            status = "✅ PASS" if result.passed else "❌ FAIL"
            print(f"  {word}: {status} (similarity: {result.cosine_similarity:.4f})")
            if result.passed:
                passed += 1
            else:
                failed += 1

        print("-" * 60)
        print(f"Total: {passed}/{passed + failed} passed")
        print("=" * 60 + "\n")


def run_bank_test(
    model: torch.nn.Module,
    tokenizer: Any,
    assert_on_failure: bool = True,
) -> DisambiguationResult:
    """
    Convenience function to run the Bank Disambiguation Test.

    Args:
        model: SovereignTransformer model
        tokenizer: Tokenizer
        assert_on_failure: If True, raise AssertionError on failure

    Returns:
        Test result
    """
    test = BankDisambiguationTest(model, tokenizer)
    result = test.run()

    if assert_on_failure and not result.passed:
        raise AssertionError(
            f"Bank Disambiguation Test FAILED: "
            f"Cosine similarity {result.cosine_similarity:.4f} >= {test.SIMILARITY_PASS_THRESHOLD}"
        )

    return result
