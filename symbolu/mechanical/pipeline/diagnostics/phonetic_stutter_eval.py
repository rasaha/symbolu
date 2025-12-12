"""
Phonetic Stuttering Evaluation Module
======================================

Tests whether "phonetic stuttering" is a real, measurable failure mode.

Implements:
1. Brokenness scoring (repeated 3-grams, fragments, stopword/punctuation ratios)
2. Phoneme-proxy feature extraction (sibilants, stops, nasals, fricatives)
3. Corpus evaluation with correlation analysis
4. Phonetic reranker/optimizer
5. Before/after comparison

This is a SKEPTICAL evaluation - we require evidence to support hypotheses.
"""

import re
import hashlib
import json
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass, field, asdict
from collections import Counter
import math


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class BrokennessScore:
    """Deterministic brokenness score for an output text."""
    repeated_trigram_rate: float  # Ratio of repeated 3-grams
    fragment_indicator_score: float  # Repeated sentence starters
    stopword_punct_ratio: float  # Stopword density + abrupt punctuation
    brokenness_score: float  # Final score ∈ [0,1]

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PhoneticFeatures:
    """Phoneme-proxy features extracted from text."""
    sibilant_count: int  # s, z, sh sounds
    stop_count: int  # p, t, k, b, d, g sounds
    nasal_count: int  # m, n sounds
    fricative_count: int  # f, v sounds
    stop_ending_ratio: float  # Words ending in stops
    total_words: int

    # Derived features
    sibilant_density: float = 0.0
    stop_density: float = 0.0
    nasal_density: float = 0.0
    fricative_density: float = 0.0

    def __post_init__(self):
        """Calculate densities."""
        if self.total_words > 0:
            self.sibilant_density = self.sibilant_count / self.total_words
            self.stop_density = self.stop_count / self.total_words
            self.nasal_density = self.nasal_count / self.total_words
            self.fricative_density = self.fricative_count / self.total_words

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class EvaluationResult:
    """Result of evaluating a single output."""
    run_id: str
    output_text: str
    brokenness: BrokennessScore
    phonetics: PhoneticFeatures

    def to_dict(self) -> Dict:
        return {
            "run_id": self.run_id,
            "output_text": self.output_text,
            "brokenness": self.brokenness.to_dict(),
            "phonetics": self.phonetics.to_dict()
        }


@dataclass
class CorrelationResult:
    """Correlation between a phonetic feature and brokenness."""
    feature_name: str
    correlation: float
    effect_size: str  # "negligible", "small", "medium", "large"
    sample_size: int


# =============================================================================
# BROKENNESS METRICS
# =============================================================================

class BrokennessAnalyzer:
    """Analyzes text for brokenness indicators."""

    # Fragment indicators (hedging/filler phrases)
    FRAGMENT_INDICATORS = [
        "consider", "to clarify", "that said", "it should be noted",
        "it is important to", "one might", "it could be argued",
        "in other words", "put simply", "essentially"
    ]

    # Common stopwords
    STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "should", "could", "may", "might", "can", "this", "that",
        "these", "those", "it", "its", "i", "you", "he", "she", "we", "they"
    }

    def compute_brokenness(self, text: str) -> BrokennessScore:
        """
        Compute deterministic brokenness score.

        Args:
            text: Output text to analyze

        Returns:
            BrokennessScore with all metrics
        """
        # Metric 1: Repeated 3-gram rate
        trigram_rate = self._compute_repeated_trigrams(text)

        # Metric 2: Fragment indicator score
        fragment_score = self._compute_fragment_score(text)

        # Metric 3: Stopword + punctuation ratio
        stopword_punct = self._compute_stopword_punct_ratio(text)

        # Combine into final brokenness score (weighted average)
        brokenness = (
            0.4 * trigram_rate +
            0.35 * fragment_score +
            0.25 * stopword_punct
        )

        return BrokennessScore(
            repeated_trigram_rate=trigram_rate,
            fragment_indicator_score=fragment_score,
            stopword_punct_ratio=stopword_punct,
            brokenness_score=min(1.0, brokenness)  # Cap at 1.0
        )

    def _compute_repeated_trigrams(self, text: str) -> float:
        """Calculate ratio of repeated 3-grams (word-level)."""
        words = self._tokenize_words(text)
        if len(words) < 3:
            return 0.0

        # Extract all 3-grams
        trigrams = []
        for i in range(len(words) - 2):
            trigram = (words[i], words[i+1], words[i+2])
            trigrams.append(trigram)

        if not trigrams:
            return 0.0

        # Count repetitions
        trigram_counts = Counter(trigrams)
        repeated = sum(1 for count in trigram_counts.values() if count > 1)

        # Ratio of unique trigrams that are repeated
        unique_trigrams = len(trigram_counts)
        if unique_trigrams == 0:
            return 0.0

        return repeated / unique_trigrams

    def _compute_fragment_score(self, text: str) -> float:
        """Calculate score based on repeated sentence-starting fragments."""
        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            return 0.0

        # Count how many sentences start with fragment indicators
        fragment_starts = []
        for sentence in sentences:
            sentence_lower = sentence.lower().strip()
            for indicator in self.FRAGMENT_INDICATORS:
                if sentence_lower.startswith(indicator):
                    fragment_starts.append(indicator)
                    break

        if not fragment_starts:
            return 0.0

        # Check for repetition of same fragment starter
        fragment_counts = Counter(fragment_starts)
        repeated_fragments = sum(1 for count in fragment_counts.values() if count > 1)

        # Score: (repeated fragments / total sentences)
        score = (repeated_fragments + len(fragment_starts) * 0.3) / len(sentences)
        return min(1.0, score)

    def _compute_stopword_punct_ratio(self, text: str) -> float:
        """Calculate stopword density + abrupt punctuation ratio."""
        words = self._tokenize_words(text)
        if not words:
            return 0.0

        # Count stopwords
        stopword_count = sum(1 for w in words if w.lower() in self.STOPWORDS)
        stopword_ratio = stopword_count / len(words)

        # Count abrupt punctuation (standalone sentences ending with .)
        sentences = self._split_sentences(text)
        short_sentences = sum(1 for s in sentences if len(self._tokenize_words(s)) <= 5)
        abrupt_punct_ratio = short_sentences / len(sentences) if sentences else 0.0

        # Combine (higher stopword ratio + more abrupt punctuation = more broken)
        combined = 0.6 * stopword_ratio + 0.4 * abrupt_punct_ratio
        return min(1.0, combined)

    def _tokenize_words(self, text: str) -> List[str]:
        """Tokenize text into words."""
        # Simple word tokenization
        words = re.findall(r'\b\w+\b', text.lower())
        return words

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences


# =============================================================================
# PHONEME-PROXY EXTRACTION
# =============================================================================

class PhonemeProxyExtractor:
    """Extracts phoneme-proxy features from text."""

    # Phoneme approximations using letter patterns
    SIBILANT_PATTERNS = [
        r'\bs[aeiou]', r's\b', r'ss', r'ce\b', r'ci',  # s sounds
        r'\bz[aeiou]', r'z\b', r'zz',  # z sounds
        r'sh', r'ti[aou]', r'si[aou]', r'ci[aou]'  # sh sounds
    ]

    STOP_PATTERNS = [
        r'\bp[aeiou]', r'p\b', r'pp',  # p
        r'\bt[aeiou]', r't\b', r'tt', r'ed\b',  # t
        r'\bk[aeiou]', r'k\b', r'ck', r'c[aou]',  # k
        r'\bb[aeiou]', r'b\b', r'bb',  # b
        r'\bd[aeiou]', r'd\b', r'dd',  # d
        r'\bg[aeiou]', r'g\b', r'gg'  # g
    ]

    NASAL_PATTERNS = [
        r'\bm[aeiou]', r'm\b', r'mm',  # m
        r'\bn[aeiou]', r'n\b', r'nn'  # n
    ]

    FRICATIVE_PATTERNS = [
        r'\bf[aeiou]', r'f\b', r'ff', r'ph',  # f
        r'\bv[aeiou]', r'v\b', r'vv'  # v
    ]

    # Stop consonants for word endings
    STOP_ENDINGS = {'p', 't', 'k', 'b', 'd', 'g', 'ck', 'ed'}

    def extract_features(self, text: str) -> PhoneticFeatures:
        """
        Extract phoneme-proxy features from text.

        Args:
            text: Output text to analyze

        Returns:
            PhoneticFeatures with all counts and ratios
        """
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)

        if not words:
            return PhoneticFeatures(
                sibilant_count=0,
                stop_count=0,
                nasal_count=0,
                fricative_count=0,
                stop_ending_ratio=0.0,
                total_words=0
            )

        # Count phoneme approximations
        sibilant_count = self._count_patterns(text_lower, self.SIBILANT_PATTERNS)
        stop_count = self._count_patterns(text_lower, self.STOP_PATTERNS)
        nasal_count = self._count_patterns(text_lower, self.NASAL_PATTERNS)
        fricative_count = self._count_patterns(text_lower, self.FRICATIVE_PATTERNS)

        # Count stop-ending words
        stop_ending_words = 0
        for word in words:
            if any(word.endswith(ending) for ending in self.STOP_ENDINGS):
                stop_ending_words += 1

        stop_ending_ratio = stop_ending_words / len(words) if words else 0.0

        return PhoneticFeatures(
            sibilant_count=sibilant_count,
            stop_count=stop_count,
            nasal_count=nasal_count,
            fricative_count=fricative_count,
            stop_ending_ratio=stop_ending_ratio,
            total_words=len(words)
        )

    def _count_patterns(self, text: str, patterns: List[str]) -> int:
        """Count occurrences of regex patterns."""
        total = 0
        for pattern in patterns:
            matches = re.findall(pattern, text)
            total += len(matches)
        return total


# =============================================================================
# CORPUS GENERATOR
# =============================================================================

class DeterministicPromptGenerator:
    """Generates deterministic corpus of prompts for testing."""

    def __init__(self, seed: int = 42):
        """Initialize with seed for determinism."""
        self.seed = seed

    def generate_prompts(self, count: int = 200) -> List[str]:
        """
        Generate deterministic prompts.

        Args:
            count: Number of prompts to generate

        Returns:
            List of prompt strings
        """
        prompts = []

        # Template categories
        templates = [
            # Questions
            "What is {topic}?",
            "How does {topic} work?",
            "Explain {topic} in detail.",
            "Why is {topic} important?",
            "What are the benefits of {topic}?",
            "What are the challenges with {topic}?",
            "Compare {topic1} and {topic2}.",
            "When should I use {topic}?",

            # Instructions
            "Describe {topic}.",
            "Analyze {topic}.",
            "Evaluate {topic}.",
            "Summarize {topic}.",
            "Define {topic} clearly.",

            # Complex queries
            "How can {topic} improve {domain}?",
            "What is the relationship between {topic1} and {topic2}?",
            "What are common misconceptions about {topic}?",
        ]

        # Topic pool (deterministic)
        topics = [
            "machine learning", "quantum computing", "blockchain", "neural networks",
            "deep learning", "natural language processing", "computer vision",
            "reinforcement learning", "consciousness", "intelligence", "reasoning",
            "decision making", "pattern recognition", "symbolic reasoning",
            "causal inference", "probability theory", "information theory",
            "game theory", "optimization", "complexity theory", "emergence",
            "self-organization", "feedback loops", "nonlinear dynamics",
            "phase transitions", "critical phenomena", "scaling laws",
            "network effects", "distributed systems", "consensus mechanisms",
            "cryptography", "zero-knowledge proofs", "smart contracts",
            "decentralization", "artificial intelligence", "cognitive science",
            "neuroscience", "psychology", "philosophy", "ethics", "logic",
            "mathematics", "physics", "chemistry", "biology", "evolution",
            "genetics", "ecology", "climate", "energy", "sustainability",
            "economics", "markets", "finance", "trading", "investment"
        ]

        domains = [
            "healthcare", "finance", "education", "transportation",
            "manufacturing", "agriculture", "energy", "communication",
            "entertainment", "research", "government", "security"
        ]

        # Generate prompts deterministically
        for i in range(count):
            # Use hash-based selection for determinism
            hash_val = int(hashlib.md5(f"{self.seed}_{i}".encode()).hexdigest(), 16)

            template_idx = hash_val % len(templates)
            template = templates[template_idx]

            # Fill template
            if "{topic1}" in template and "{topic2}" in template:
                topic1_idx = (hash_val >> 8) % len(topics)
                topic2_idx = (hash_val >> 16) % len(topics)
                prompt = template.format(topic1=topics[topic1_idx], topic2=topics[topic2_idx])
            elif "{domain}" in template:
                topic_idx = (hash_val >> 8) % len(topics)
                domain_idx = (hash_val >> 16) % len(domains)
                prompt = template.format(topic=topics[topic_idx], domain=domains[domain_idx])
            elif "{topic}" in template:
                topic_idx = (hash_val >> 8) % len(topics)
                prompt = template.format(topic=topics[topic_idx])
            else:
                prompt = template

            prompts.append(prompt)

        return prompts


# =============================================================================
# PHONETIC RERANKER
# =============================================================================

class PhoneticReranker:
    """
    Reranks or rewrites text to minimize phonetic conflicts.

    This is a post-processor that attempts to reduce:
    - Repeated stop-endings
    - Excessive stop-ending ratio
    - Repeated leading fragments
    """

    # Synonym pool for common connector phrases
    CONNECTOR_SYNONYMS = {
        "Consider": ["Examine", "Review", "Analyze", "Evaluate"],
        "To clarify": ["Specifically", "In particular", "More precisely", "Notably"],
        "That said": ["However", "Nevertheless", "Conversely", "Meanwhile"],
        "It should be noted": ["Importantly", "Significantly", "Crucially", "Remarkably"],
        "In other words": ["Specifically", "Namely", "Put differently", "Essentially"],
        "Therefore": ["Thus", "Hence", "Consequently", "Accordingly"],
        "However": ["Yet", "Nevertheless", "Nonetheless", "Still"],
        "Moreover": ["Furthermore", "Additionally", "Also", "Besides"],
    }

    def optimize_text(self, text: str) -> str:
        """
        Optimize text to reduce phonetic conflicts.

        Args:
            text: Original text

        Returns:
            Optimized text with reduced conflicts
        """
        # Split into sentences
        sentences = self._split_sentences(text)
        if not sentences:
            return text

        # Track fragment usage
        fragment_usage: Dict[str, int] = {}
        optimized_sentences = []

        for i, sentence in enumerate(sentences):
            optimized = sentence

            # Check for fragment indicators at start
            sentence_lower = sentence.strip().lower()
            for original, synonyms in self.CONNECTOR_SYNONYMS.items():
                original_lower = original.lower()
                if sentence_lower.startswith(original_lower):
                    # Check if we've used this fragment before
                    if original in fragment_usage and fragment_usage[original] > 0:
                        # Replace with synonym (deterministic selection)
                        synonym_idx = fragment_usage[original] % len(synonyms)
                        synonym = synonyms[synonym_idx]

                        # Replace at start of sentence
                        optimized = sentence.strip()
                        if optimized.startswith(original):
                            optimized = synonym + optimized[len(original):]
                        elif optimized.lower().startswith(original_lower):
                            # Case-insensitive replacement
                            optimized = synonym + optimized[len(original):]

                    # Track usage
                    fragment_usage[original] = fragment_usage.get(original, 0) + 1
                    break

            optimized_sentences.append(optimized)

        # Rejoin sentences
        result = " ".join(optimized_sentences)

        # Additional optimization: reduce excessive stop-endings
        result = self._reduce_stop_endings(result)

        return result

    def _reduce_stop_endings(self, text: str) -> str:
        """
        Attempt to reduce consecutive stop-ending words.

        This is minimal to avoid changing semantic content.
        """
        # For now, just return as-is
        # A more sophisticated version would use a thesaurus
        return text

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        sentences = re.split(r'([.!?]+\s+)', text)
        # Recombine sentence + punctuation
        result = []
        i = 0
        while i < len(sentences):
            if i + 1 < len(sentences) and re.match(r'[.!?]+\s+', sentences[i + 1]):
                result.append(sentences[i] + sentences[i + 1])
                i += 2
            else:
                if sentences[i].strip():
                    result.append(sentences[i])
                i += 1
        return result


# =============================================================================
# MAIN EVALUATOR
# =============================================================================

class PhoneticStutterEvaluator:
    """Main evaluator for phonetic stuttering hypothesis."""

    def __init__(self):
        self.brokenness_analyzer = BrokennessAnalyzer()
        self.phoneme_extractor = PhonemeProxyExtractor()
        self.prompt_generator = DeterministicPromptGenerator()
        self.reranker = PhoneticReranker()

    def evaluate_single_output(self, output_text: str, run_id: Optional[str] = None) -> EvaluationResult:
        """
        Evaluate a single output.

        Args:
            output_text: Text to evaluate
            run_id: Optional run identifier

        Returns:
            EvaluationResult with all metrics
        """
        if run_id is None:
            run_id = hashlib.md5(output_text.encode()).hexdigest()[:8]

        brokenness = self.brokenness_analyzer.compute_brokenness(output_text)
        phonetics = self.phoneme_extractor.extract_features(output_text)

        return EvaluationResult(
            run_id=run_id,
            output_text=output_text,
            brokenness=brokenness,
            phonetics=phonetics
        )

    def compute_correlation(self, results: List[EvaluationResult]) -> List[CorrelationResult]:
        """
        Compute correlations between phonetic features and brokenness.

        Args:
            results: List of evaluation results

        Returns:
            List of correlation results, sorted by absolute correlation
        """
        if len(results) < 2:
            return []

        # Extract brokenness scores
        brokenness_scores = [r.brokenness.brokenness_score for r in results]

        # Extract phonetic features
        feature_names = [
            "sibilant_density",
            "stop_density",
            "nasal_density",
            "fricative_density",
            "stop_ending_ratio"
        ]

        correlations = []
        for feature_name in feature_names:
            feature_values = [getattr(r.phonetics, feature_name) for r in results]

            # Compute Pearson correlation
            corr = self._pearson_correlation(feature_values, brokenness_scores)

            # Determine effect size
            effect_size = self._interpret_correlation(abs(corr))

            correlations.append(CorrelationResult(
                feature_name=feature_name,
                correlation=corr,
                effect_size=effect_size,
                sample_size=len(results)
            ))

        # Sort by absolute correlation (descending)
        correlations.sort(key=lambda x: abs(x.correlation), reverse=True)

        return correlations

    def _pearson_correlation(self, x: List[float], y: List[float]) -> float:
        """Compute Pearson correlation coefficient."""
        if len(x) != len(y) or len(x) < 2:
            return 0.0

        n = len(x)
        mean_x = sum(x) / n
        mean_y = sum(y) / n

        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))

        sum_sq_x = sum((x[i] - mean_x) ** 2 for i in range(n))
        sum_sq_y = sum((y[i] - mean_y) ** 2 for i in range(n))

        if sum_sq_x == 0 or sum_sq_y == 0:
            return 0.0

        denominator = math.sqrt(sum_sq_x * sum_sq_y)

        return numerator / denominator if denominator != 0 else 0.0

    def _interpret_correlation(self, abs_corr: float) -> str:
        """Interpret correlation magnitude as effect size."""
        if abs_corr < 0.1:
            return "negligible"
        elif abs_corr < 0.3:
            return "small"
        elif abs_corr < 0.5:
            return "medium"
        else:
            return "large"

    def generate_prompts(self, count: int = 200) -> List[str]:
        """Generate deterministic prompts."""
        return self.prompt_generator.generate_prompts(count)

    def optimize_output(self, text: str) -> str:
        """Optimize text using phonetic reranker."""
        return self.reranker.optimize_text(text)


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def evaluate_phonetic_stuttering(
    output_texts: List[str],
    use_optimization: bool = False
) -> Tuple[List[EvaluationResult], List[CorrelationResult]]:
    """
    Convenience function to evaluate phonetic stuttering on a corpus.

    Args:
        output_texts: List of output texts to evaluate
        use_optimization: Whether to apply phonetic optimization first

    Returns:
        Tuple of (evaluation results, correlation results)
    """
    evaluator = PhoneticStutterEvaluator()

    # Optionally optimize texts
    if use_optimization:
        output_texts = [evaluator.optimize_output(text) for text in output_texts]

    # Evaluate each output
    results = []
    for i, text in enumerate(output_texts):
        run_id = f"run_{i:04d}"
        result = evaluator.evaluate_single_output(text, run_id)
        results.append(result)

    # Compute correlations
    correlations = evaluator.compute_correlation(results)

    return results, correlations
