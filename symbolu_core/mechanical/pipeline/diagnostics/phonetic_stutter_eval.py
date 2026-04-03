"""
Phonetic Stuttering Hypothesis Evaluator
=========================================

Skeptical empirical test of whether "phonetic stuttering" is a measurable
failure mode in Symbol-U rendered outputs.

This module implements:
1. Output instrumentation with run_id logging
2. Deterministic "brokenness score" calculation (3 metrics)
3. Phoneme-proxy feature extraction
4. Corpus evaluation with correlation analysis
5. Phonetic conflict reranker/post-processor
6. Before/after comparison reporting

Author: Empirical Testing Framework
Version: 1.0
"""

import re
import json
import hashlib
import random
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field
from collections import Counter, defaultdict
import math


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class PhonemeFeatures:
    """Phoneme-proxy features extracted from text."""
    sibilant_count: int  # s, z, sh
    stop_count: int  # p, t, k, b, d, g
    nasal_count: int  # m, n
    fricative_count: int  # f, v, th
    stop_ending_ratio: float  # words ending in stops
    total_phonemes: int

    def to_vector(self) -> List[float]:
        """Convert to feature vector for correlation analysis."""
        total = max(self.total_phonemes, 1)
        return [
            self.sibilant_count / total,
            self.stop_count / total,
            self.nasal_count / total,
            self.fricative_count / total,
            self.stop_ending_ratio
        ]

    def to_dict(self) -> Dict[str, float]:
        """Convert to labeled dictionary."""
        total = max(self.total_phonemes, 1)
        return {
            "sibilant_ratio": self.sibilant_count / total,
            "stop_ratio": self.stop_count / total,
            "nasal_ratio": self.nasal_count / total,
            "fricative_ratio": self.fricative_count / total,
            "stop_ending_ratio": self.stop_ending_ratio
        }


@dataclass
class BrokennessMetrics:
    """Brokenness metrics for an output."""
    repeated_trigrams_rate: float  # [0, 1]
    fragment_indicator_score: float  # [0, 1]
    stopword_punct_score: float  # [0, 1]
    brokenness_score: float  # [0, 1] - aggregate

    def to_dict(self) -> Dict[str, float]:
        return {
            "repeated_trigrams_rate": self.repeated_trigrams_rate,
            "fragment_indicator_score": self.fragment_indicator_score,
            "stopword_punct_score": self.stopword_punct_score,
            "brokenness_score": self.brokenness_score
        }


@dataclass
class OutputRecord:
    """Single output record with all metrics."""
    run_id: str
    prompt: str
    output_text: str
    phoneme_features: PhonemeFeatures
    brokenness_metrics: BrokennessMetrics
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CorpusEvaluation:
    """Results from corpus evaluation."""
    records: List[OutputRecord]
    correlations: Dict[str, float]
    effect_sizes: Dict[str, float]
    summary_stats: Dict[str, Any]


# =============================================================================
# PHONEME-PROXY EXTRACTOR
# =============================================================================

class PhonemeExtractor:
    """
    Deterministic phoneme-proxy feature extractor.

    Uses simple text-based heuristics to approximate phonetic features
    without requiring full phonetic transcription.
    """

    # Phoneme approximation patterns
    SIBILANT_PATTERN = re.compile(r'[szSZ]|sh|ch|zh', re.IGNORECASE)
    STOP_PATTERN = re.compile(r'[ptkbdgPTKBDG]')
    NASAL_PATTERN = re.compile(r'[mnMN]')
    FRICATIVE_PATTERN = re.compile(r'[fvFV]|th')

    # Stop-ending word pattern
    STOP_ENDING_PATTERN = re.compile(r'\b\w*[ptkbdg]\b', re.IGNORECASE)

    def extract(self, text: str) -> PhonemeFeatures:
        """
        Extract phoneme-proxy features from text.

        Args:
            text: Input text

        Returns:
            PhonemeFeatures with counts and ratios
        """
        # Count phoneme proxies
        sibilants = len(self.SIBILANT_PATTERN.findall(text))
        stops = len(self.STOP_PATTERN.findall(text))
        nasals = len(self.NASAL_PATTERN.findall(text))
        fricatives = len(self.FRICATIVE_PATTERN.findall(text))

        # Calculate stop-ending ratio
        words = re.findall(r'\b\w+\b', text)
        stop_ending_words = [w for w in words if self.STOP_ENDING_PATTERN.match(w)]
        stop_ending_ratio = len(stop_ending_words) / max(len(words), 1)

        # Total phonemes (approximate)
        total_phonemes = sibilants + stops + nasals + fricatives

        return PhonemeFeatures(
            sibilant_count=sibilants,
            stop_count=stops,
            nasal_count=nasals,
            fricative_count=fricatives,
            stop_ending_ratio=stop_ending_ratio,
            total_phonemes=total_phonemes
        )


# =============================================================================
# BROKENNESS SCORE CALCULATOR
# =============================================================================

class BrokennessCalculator:
    """
    Deterministic brokenness score calculator.

    Implements 3 metrics:
    1. Repeated 3-grams rate
    2. Fragment indicators (hedging phrases)
    3. Stopword ratio + abrupt punctuation
    """

    # Fragment indicator phrases
    FRAGMENT_INDICATORS = [
        "consider",
        "to clarify",
        "that said",
        "however",
        "on the other hand",
        "it depends",
        "in other words",
    ]

    # Common stopwords
    STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "be",
        "been", "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "should", "could", "may", "might", "must", "can", "this",
        "that", "these", "those", "it", "its", "they", "them", "their"
    }

    def calculate(self, text: str) -> BrokennessMetrics:
        """
        Calculate brokenness score for text.

        Args:
            text: Input text

        Returns:
            BrokennessMetrics with all scores
        """
        # Metric 1: Repeated 3-grams rate
        trigram_score = self._calculate_trigram_repetition(text)

        # Metric 2: Fragment indicator score
        fragment_score = self._calculate_fragment_score(text)

        # Metric 3: Stopword + punctuation score
        stopword_punct_score = self._calculate_stopword_punct_score(text)

        # Aggregate brokenness score (weighted average)
        brokenness_score = (
            0.4 * trigram_score +
            0.3 * fragment_score +
            0.3 * stopword_punct_score
        )

        return BrokennessMetrics(
            repeated_trigrams_rate=trigram_score,
            fragment_indicator_score=fragment_score,
            stopword_punct_score=stopword_punct_score,
            brokenness_score=brokenness_score
        )

    def _calculate_trigram_repetition(self, text: str) -> float:
        """Calculate repeated 3-gram rate."""
        # Extract word trigrams
        words = re.findall(r'\b\w+\b', text.lower())
        if len(words) < 3:
            return 0.0

        trigrams = []
        for i in range(len(words) - 2):
            trigram = " ".join(words[i:i+3])
            trigrams.append(trigram)

        # Count repetitions
        trigram_counts = Counter(trigrams)
        repeated = sum(1 for count in trigram_counts.values() if count > 1)

        # Normalize to [0, 1]
        return min(repeated / max(len(trigrams), 1), 1.0)

    def _calculate_fragment_score(self, text: str) -> float:
        """Calculate fragment indicator score."""
        # Count sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 0.0

        # Count fragment indicators at sentence start
        fragment_counts = defaultdict(int)
        for sentence in sentences:
            sentence_lower = sentence.lower()
            for indicator in self.FRAGMENT_INDICATORS:
                if sentence_lower.startswith(indicator):
                    fragment_counts[indicator] += 1

        # Score based on repetition (count > 1)
        repeated_fragments = sum(1 for count in fragment_counts.values() if count > 1)

        # Normalize
        return min(repeated_fragments / max(len(sentences), 1), 1.0)

    def _calculate_stopword_punct_score(self, text: str) -> float:
        """Calculate stopword ratio + abrupt punctuation score."""
        words = re.findall(r'\b\w+\b', text.lower())

        if not words:
            return 0.0

        # Stopword ratio
        stopword_count = sum(1 for w in words if w in self.STOPWORDS)
        stopword_ratio = stopword_count / len(words)

        # Abrupt punctuation ratio (commas, semicolons, dashes)
        sentences = re.split(r'[.!?]+', text)
        abrupt_punct = len(re.findall(r'[,;—\-]', text))
        abrupt_ratio = abrupt_punct / max(len(text), 1)

        # Combine (high stopword + high abrupt = broken)
        score = 0.6 * min(stopword_ratio * 2, 1.0) + 0.4 * min(abrupt_ratio * 50, 1.0)

        return min(score, 1.0)


# =============================================================================
# CORPUS GENERATOR
# =============================================================================

class CorpusGenerator:
    """Generate deterministic test prompts for evaluation."""

    def __init__(self, seed: int = 42):
        """Initialize with seed for reproducibility."""
        self.seed = seed
        random.seed(seed)

    def generate_prompts(self, count: int = 200) -> List[str]:
        """
        Generate deterministic prompt set.

        Args:
            count: Number of prompts to generate

        Returns:
            List of prompt strings
        """
        # Template categories
        templates = [
            # Questions
            "What is {topic}?",
            "How does {topic} work?",
            "Why is {topic} important?",
            "Can you explain {topic}?",
            "What are the benefits of {topic}?",

            # Requests
            "Tell me about {topic}.",
            "Describe {topic}.",
            "Help me understand {topic}.",
            "I need information on {topic}.",
            "Please explain {topic}.",

            # Comparisons
            "Compare {topic1} and {topic2}.",
            "What's the difference between {topic1} and {topic2}?",
            "Which is better: {topic1} or {topic2}?",

            # Analysis
            "Analyze {topic}.",
            "What are the implications of {topic}?",
            "Discuss the advantages of {topic}.",
        ]

        # Topic pool
        topics = [
            "machine learning", "quantum computing", "blockchain", "artificial intelligence",
            "cloud computing", "data science", "cybersecurity", "neural networks",
            "natural language processing", "computer vision", "deep learning", "robotics",
            "internet of things", "virtual reality", "augmented reality", "edge computing",
            "distributed systems", "microservices", "containers", "kubernetes",
            "software architecture", "design patterns", "agile methodology", "devops",
            "continuous integration", "test driven development", "functional programming",
            "object oriented programming", "reactive programming", "event driven architecture",
        ]

        prompts = []
        for i in range(count):
            # Select template
            template = templates[i % len(templates)]

            # Fill template
            if "{topic1}" in template and "{topic2}" in template:
                topic1 = topics[i % len(topics)]
                topic2 = topics[(i + 1) % len(topics)]
                prompt = template.format(topic1=topic1, topic2=topic2)
            else:
                topic = topics[i % len(topics)]
                prompt = template.format(topic=topic)

            prompts.append(prompt)

        return prompts


# =============================================================================
# CORRELATION ANALYZER
# =============================================================================

class CorrelationAnalyzer:
    """Compute correlations and effect sizes."""

    @staticmethod
    def pearson_correlation(x: List[float], y: List[float]) -> float:
        """
        Calculate Pearson correlation coefficient.

        Args:
            x: First variable
            y: Second variable

        Returns:
            Correlation coefficient [-1, 1]
        """
        if len(x) != len(y) or len(x) == 0:
            return 0.0

        n = len(x)
        mean_x = sum(x) / n
        mean_y = sum(y) / n

        # Calculate covariance and standard deviations
        cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n)) / n
        std_x = math.sqrt(sum((x[i] - mean_x) ** 2 for i in range(n)) / n)
        std_y = math.sqrt(sum((y[i] - mean_y) ** 2 for i in range(n)) / n)

        if std_x == 0 or std_y == 0:
            return 0.0

        return cov / (std_x * std_y)

    @staticmethod
    def cohens_d(x: List[float], threshold: float = 0.5) -> float:
        """
        Calculate Cohen's d effect size.

        Args:
            x: Variable values
            threshold: Threshold for splitting groups

        Returns:
            Effect size
        """
        if not x:
            return 0.0

        # Split into high/low groups
        low_group = [v for v in x if v < threshold]
        high_group = [v for v in x if v >= threshold]

        if not low_group or not high_group:
            return 0.0

        mean_low = sum(low_group) / len(low_group)
        mean_high = sum(high_group) / len(high_group)

        var_low = sum((v - mean_low) ** 2 for v in low_group) / len(low_group)
        var_high = sum((v - mean_high) ** 2 for v in high_group) / len(high_group)

        pooled_std = math.sqrt((var_low + var_high) / 2)

        if pooled_std == 0:
            return 0.0

        return (mean_high - mean_low) / pooled_std


# =============================================================================
# PHONETIC CONFLICT RERANKER
# =============================================================================

class PhoneticReranker:
    """
    Phonetic conflict reranker/post-processor.

    Selects from candidate phrasings or rewrites to minimize phonetic conflicts.
    """

    # Synonym pool for common connector phrases
    CONNECTOR_SYNONYMS = {
        "consider": ["think about", "examine", "reflect on", "look at"],
        "to clarify": ["more specifically", "put another way", "in detail"],
        "that said": ["nevertheless", "yet", "still", "even so"],
        "however": ["but", "yet", "though", "although"],
        "on the other hand": ["conversely", "alternatively", "in contrast"],
        "it depends": ["varies", "differs", "changes based on"],
        "in other words": ["put simply", "essentially", "basically"],
    }

    def __init__(self):
        self.phoneme_extractor = PhonemeExtractor()
        self.brokenness_calculator = BrokennessCalculator()

    def rerank_candidates(self, candidates: List[str]) -> str:
        """
        Select best candidate based on phonetic conflict score.

        Args:
            candidates: List of candidate phrasings

        Returns:
            Best candidate (lowest phonetic conflict)
        """
        if not candidates:
            return ""

        if len(candidates) == 1:
            return candidates[0]

        # Score each candidate
        scored = []
        for candidate in candidates:
            score = self._phonetic_conflict_score(candidate)
            scored.append((score, candidate))

        # Return lowest score
        scored.sort(key=lambda x: x[0])
        return scored[0][1]

    def post_process(self, text: str) -> str:
        """
        Post-process text to reduce phonetic conflicts.

        Args:
            text: Input text

        Returns:
            Rewritten text with reduced conflicts
        """
        # Rewrite connector phrases using synonym pool
        result = text

        # Track connector usage to avoid repetition
        connector_counts = defaultdict(int)
        for connector in self.CONNECTOR_SYNONYMS.keys():
            connector_counts[connector] = len(re.findall(
                r'\b' + re.escape(connector) + r'\b',
                result.lower()
            ))

        # Replace repeated connectors
        for connector, count in connector_counts.items():
            if count > 1:
                # Replace with synonyms
                synonyms = self.CONNECTOR_SYNONYMS[connector]
                pattern = re.compile(r'\b' + re.escape(connector) + r'\b', re.IGNORECASE)

                # Find all matches
                matches = list(pattern.finditer(result))

                # Replace from end to start (preserve indices)
                for i, match in enumerate(reversed(matches)):
                    if i > 0:  # Keep first occurrence
                        synonym_idx = i % len(synonyms)
                        synonym = synonyms[synonym_idx]
                        # Match case
                        if match.group(0)[0].isupper():
                            synonym = synonym[0].upper() + synonym[1:]
                        result = result[:match.start()] + synonym + result[match.end():]

        return result

    def _phonetic_conflict_score(self, text: str) -> float:
        """
        Calculate phonetic conflict score.

        Penalizes:
        - Repeated stop-endings
        - Excessive stop-ending ratio
        - Repeated fragment indicators

        Returns:
            Conflict score [0, 1] (lower is better)
        """
        phoneme_features = self.phoneme_extractor.extract(text)
        brokenness_metrics = self.brokenness_calculator.calculate(text)

        # Weight components
        stop_penalty = phoneme_features.stop_ending_ratio * 0.4
        fragment_penalty = brokenness_metrics.fragment_indicator_score * 0.3
        brokenness_penalty = brokenness_metrics.brokenness_score * 0.3

        return min(stop_penalty + fragment_penalty + brokenness_penalty, 1.0)


# =============================================================================
# MAIN EVALUATOR
# =============================================================================

class PhoneticStutterEvaluator:
    """Main evaluator for phonetic stuttering hypothesis."""

    def __init__(self, seed: int = 42):
        """Initialize evaluator."""
        self.phoneme_extractor = PhonemeExtractor()
        self.brokenness_calculator = BrokennessCalculator()
        self.corpus_generator = CorpusGenerator(seed=seed)
        self.correlation_analyzer = CorrelationAnalyzer()
        self.reranker = PhoneticReranker()
        self.seed = seed

    def generate_run_id(self, prompt: str, index: int) -> str:
        """Generate deterministic run_id."""
        content = f"{prompt}:{index}:{self.seed}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def evaluate_output(
        self,
        prompt: str,
        output_text: str,
        run_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> OutputRecord:
        """
        Evaluate a single output.

        Args:
            prompt: Input prompt
            output_text: Generated output
            run_id: Optional run identifier
            metadata: Optional metadata

        Returns:
            OutputRecord with all metrics
        """
        if run_id is None:
            run_id = self.generate_run_id(prompt, 0)

        phoneme_features = self.phoneme_extractor.extract(output_text)
        brokenness_metrics = self.brokenness_calculator.calculate(output_text)

        return OutputRecord(
            run_id=run_id,
            prompt=prompt,
            output_text=output_text,
            phoneme_features=phoneme_features,
            brokenness_metrics=brokenness_metrics,
            metadata=metadata or {}
        )

    def run_corpus_evaluation(
        self,
        outputs: List[Tuple[str, str]]
    ) -> CorpusEvaluation:
        """
        Run evaluation on a corpus of (prompt, output) pairs.

        Args:
            outputs: List of (prompt, output_text) tuples

        Returns:
            CorpusEvaluation with correlations and stats
        """
        # Evaluate all outputs
        records = []
        for i, (prompt, output_text) in enumerate(outputs):
            run_id = self.generate_run_id(prompt, i)
            record = self.evaluate_output(prompt, output_text, run_id)
            records.append(record)

        # Extract feature vectors and brokenness scores
        brokenness_scores = [r.brokenness_metrics.brokenness_score for r in records]

        # Compute correlations between phoneme features and brokenness
        correlations = {}
        feature_names = [
            "sibilant_ratio", "stop_ratio", "nasal_ratio",
            "fricative_ratio", "stop_ending_ratio"
        ]

        for feature_name in feature_names:
            feature_values = [
                r.phoneme_features.to_dict()[feature_name]
                for r in records
            ]
            corr = self.correlation_analyzer.pearson_correlation(
                feature_values, brokenness_scores
            )
            correlations[feature_name] = corr

        # Compute effect sizes
        effect_sizes = {}
        for feature_name in feature_names:
            feature_values = [
                r.phoneme_features.to_dict()[feature_name]
                for r in records
            ]
            effect_size = self.correlation_analyzer.cohens_d(feature_values)
            effect_sizes[feature_name] = effect_size

        # Summary statistics
        summary_stats = {
            "total_outputs": len(records),
            "avg_brokenness": sum(brokenness_scores) / len(brokenness_scores) if brokenness_scores else 0,
            "high_brokenness_count": sum(1 for s in brokenness_scores if s > 0.7),
            "high_brokenness_percent": 100 * sum(1 for s in brokenness_scores if s > 0.7) / max(len(brokenness_scores), 1)
        }

        return CorpusEvaluation(
            records=records,
            correlations=correlations,
            effect_sizes=effect_sizes,
            summary_stats=summary_stats
        )

    def print_report(self, evaluation: CorpusEvaluation, title: str = "Corpus Evaluation"):
        """Print evaluation report."""
        print(f"\n{'=' * 80}")
        print(f"{title}")
        print(f"{'=' * 80}\n")

        stats = evaluation.summary_stats
        print(f"Total outputs: {stats['total_outputs']}")
        print(f"Average brokenness score: {stats['avg_brokenness']:.3f}")
        print(f"High brokenness (>0.7): {stats['high_brokenness_count']} ({stats['high_brokenness_percent']:.1f}%)")

        print(f"\nTop 5 Phoneme Predictors (by correlation with brokenness):")
        print(f"{'Feature':<25} {'Correlation':<15} {'Effect Size':<15}")
        print(f"{'-' * 55}")

        # Sort by absolute correlation
        sorted_features = sorted(
            evaluation.correlations.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )

        for feature, corr in sorted_features[:5]:
            effect_size = evaluation.effect_sizes.get(feature, 0.0)
            print(f"{feature:<25} {corr:>8.3f}        {effect_size:>8.3f}")

        # Check specific predictors
        print(f"\nSpecific Predictors:")
        d_ending = evaluation.correlations.get("stop_ending_ratio", 0.0)
        stop_ratio = evaluation.correlations.get("stop_ratio", 0.0)
        print(f"  stop_ending_ratio correlation: {d_ending:.3f}")
        print(f"  stop_ratio correlation: {stop_ratio:.3f}")

        # Interpretation
        print(f"\nInterpretation:")
        max_corr = max(abs(c) for c in evaluation.correlations.values())
        if max_corr < 0.3:
            print("  ⚠️  WEAK CORRELATIONS: Maximum correlation < 0.3")
            print("      Phonetic features do not strongly predict brokenness.")
        elif max_corr < 0.5:
            print("  ⚠️  MODERATE CORRELATIONS: Maximum correlation < 0.5")
            print("      Some relationship exists but effect is small.")
        else:
            print("  ✓  STRONG CORRELATIONS: Maximum correlation >= 0.5")
            print("      Phonetic features show meaningful relationship with brokenness.")

        print(f"{'=' * 80}\n")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def run_hypothesis_test(
    outputs: List[Tuple[str, str]],
    rerank: bool = False,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Run complete hypothesis test on corpus.

    Args:
        outputs: List of (prompt, output_text) tuples
        rerank: Whether to apply phonetic reranking
        seed: Random seed

    Returns:
        Results dictionary
    """
    evaluator = PhoneticStutterEvaluator(seed=seed)

    # Apply reranking if requested
    if rerank:
        outputs = [
            (prompt, evaluator.reranker.post_process(output))
            for prompt, output in outputs
        ]

    # Run evaluation
    evaluation = evaluator.run_corpus_evaluation(outputs)

    return {
        "evaluation": evaluation,
        "records": [
            {
                "run_id": r.run_id,
                "prompt": r.prompt,
                "brokenness_score": r.brokenness_metrics.brokenness_score,
                "phoneme_features": r.phoneme_features.to_dict()
            }
            for r in evaluation.records
        ],
        "correlations": evaluation.correlations,
        "effect_sizes": evaluation.effect_sizes,
        "summary_stats": evaluation.summary_stats
    }


if __name__ == "__main__":
    print("Phonetic Stuttering Hypothesis Evaluator")
    print("=" * 80)
    print("Module loaded successfully")
    print("\nUsage:")
    print("  from symbolu_core.mechanical.pipeline.diagnostics.phonetic_stutter_eval import (")
    print("      PhoneticStutterEvaluator, run_hypothesis_test")
    print("  )")
    print("\nSee test script for examples.")
