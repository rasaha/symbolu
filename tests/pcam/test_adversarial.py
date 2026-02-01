"""
Adversarial and Pathological Workload Tests.

Tests controlled degradation under worst-case scenarios:
- Rapid topic drift
- Distractor documents
- Template repetition
- Far dependencies
"""

import pytest
import random
import math
from typing import Dict, List
from dataclasses import dataclass

from simulator.pcam.traces.format import TraceStep
from simulator.pcam.interface import SoftwarePCAMInterface
from simulator.pcam.baselines import IndustryStyleController
from simulator.pcam.baselines.base import ControllerConfig


@dataclass
class AdversarialResult:
    """Result of adversarial test."""
    scenario: str
    pcam_coverage: float
    baseline_coverage: float
    pcam_mass: float
    baseline_mass: float
    degradation: str  # "graceful" or "catastrophic"


class AdversarialTraceGenerator:
    """Generate adversarial traces designed to stress PCAM."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def generate_rapid_drift(
        self,
        num_topics: int = 10,
        tokens_per_topic: int = 50,
        block_size: int = 16,
    ) -> List[TraceStep]:
        """
        Generate trace with rapid topic drift.

        Attention switches completely to new blocks every N tokens.
        This tests: does PCAM forget old topics fast enough?
        """
        steps = []
        total_tokens = 0

        for topic in range(num_topics):
            topic_start = topic * tokens_per_topic
            topic_blocks = list(range(
                topic_start // block_size,
                (topic_start + tokens_per_topic) // block_size
            ))

            for pos in range(tokens_per_topic):
                query_block = (topic_start + pos) // block_size
                attention_scores = {}

                # Strong attention only to current topic blocks
                for block in topic_blocks:
                    distance = abs(block - query_block)
                    attention_scores[block] = math.exp(-distance / 3)

                # Normalize
                total = sum(attention_scores.values())
                attention_scores = {k: v / total for k, v in attention_scores.items()}

                sorted_blocks = sorted(attention_scores.items(), key=lambda x: -x[1])
                true_top_k = [b for b, _ in sorted_blocks[:64]]

                steps.append(TraceStep(
                    step_id=len(steps),
                    blocks_accessed=list(attention_scores.keys()),
                    attention_scores=attention_scores,
                    true_top_k=true_top_k,
                    query_block_id=query_block,
                ))

        return steps

    def generate_distractor_docs(
        self,
        num_docs: int = 5,
        doc_length: int = 1024,
        relevant_doc: int = 0,
        distractor_overlap: float = 0.8,  # How similar distractors are
        block_size: int = 16,
    ) -> List[TraceStep]:
        """
        Generate RAG trace with misleading distractor documents.

        Distractors have high lexical overlap (simulated by similar attention patterns)
        but are not actually relevant.
        """
        steps = []
        total_length = num_docs * doc_length

        relevant_start = relevant_doc * doc_length
        relevant_blocks = set(range(
            relevant_start // block_size,
            (relevant_start + doc_length) // block_size
        ))

        # Generate queries about the relevant doc
        for i in range(50):
            query_pos = total_length + i * 10
            query_block = query_pos // block_size

            attention_scores = {}

            # Relevant doc gets true attention
            for block in relevant_blocks:
                attention_scores[block] = self.rng.uniform(0.05, 0.15)

            # Distractors get misleading attention (high overlap pattern)
            for doc in range(num_docs):
                if doc == relevant_doc:
                    continue
                doc_start = doc * doc_length
                doc_blocks = range(
                    doc_start // block_size,
                    (doc_start + doc_length) // block_size
                )
                for block in doc_blocks:
                    # Distractors have similar but lower attention
                    attention_scores[block] = self.rng.uniform(0.02, 0.08) * distractor_overlap

            # Normalize
            total = sum(attention_scores.values())
            attention_scores = {k: v / total for k, v in attention_scores.items()}

            # True top-k should favor relevant doc
            sorted_blocks = sorted(attention_scores.items(), key=lambda x: -x[1])
            true_top_k = [b for b, _ in sorted_blocks[:64]]

            steps.append(TraceStep(
                step_id=len(steps),
                blocks_accessed=list(attention_scores.keys()),
                attention_scores=attention_scores,
                true_top_k=true_top_k,
                query_block_id=query_block,
            ))

        return steps

    def generate_template_repetition(
        self,
        num_repeats: int = 20,
        template_length: int = 50,
        block_size: int = 16,
    ) -> List[TraceStep]:
        """
        Generate trace with repeated template prompts.

        Same pattern repeats, forcing sinks and recency to dominate.
        Tests: does PCAM over-memorize templates?
        """
        steps = []
        template_blocks = list(range(template_length // block_size))

        for repeat in range(num_repeats):
            offset = repeat * template_length

            for pos in range(template_length):
                query_block = (offset + pos) // block_size
                attention_scores = {}

                # Attention to template pattern (relative positions)
                for i, block in enumerate(template_blocks):
                    actual_block = block + (offset // block_size)
                    # Same attention pattern each repeat
                    if i < len(template_blocks) // 3:
                        attention_scores[actual_block] = 0.4 / (len(template_blocks) // 3)
                    else:
                        attention_scores[actual_block] = 0.6 / (len(template_blocks) * 2 // 3)

                # Also attend to sinks
                for sink in range(4):
                    attention_scores[sink] = attention_scores.get(sink, 0) + 0.1

                # Normalize
                total = sum(attention_scores.values())
                attention_scores = {k: v / total for k, v in attention_scores.items()}

                sorted_blocks = sorted(attention_scores.items(), key=lambda x: -x[1])
                true_top_k = [b for b, _ in sorted_blocks[:64]]

                steps.append(TraceStep(
                    step_id=len(steps),
                    blocks_accessed=list(attention_scores.keys()),
                    attention_scores=attention_scores,
                    true_top_k=true_top_k,
                    query_block_id=query_block,
                ))

        return steps

    def generate_far_dependencies(
        self,
        file_length: int = 8192,
        dependency_distance: int = 4000,  # Tokens between definition and use
        num_queries: int = 50,
        block_size: int = 16,
    ) -> List[TraceStep]:
        """
        Generate code trace with far dependencies.

        Imports/type definitions at top, usage at bottom.
        Tests: can PCAM maintain long-range edges?
        """
        steps = []

        # Important blocks at the start (imports/types)
        import_blocks = set(range(10))  # First 10 blocks

        for i in range(num_queries):
            # Query position near end of file
            query_pos = file_length - num_queries + i
            query_block = query_pos // block_size

            attention_scores = {}

            # Strong attention to far imports
            for block in import_blocks:
                attention_scores[block] = 0.3 / len(import_blocks)

            # Some local attention
            for local in range(max(0, query_block - 5), query_block + 1):
                attention_scores[local] = attention_scores.get(local, 0) + 0.05

            # Scattered middle references
            for _ in range(5):
                mid_block = self.rng.randint(20, query_block - 10)
                attention_scores[mid_block] = 0.02

            # Normalize
            total = sum(attention_scores.values())
            attention_scores = {k: v / total for k, v in attention_scores.items()}

            sorted_blocks = sorted(attention_scores.items(), key=lambda x: -x[1])
            true_top_k = [b for b, _ in sorted_blocks[:64]]

            steps.append(TraceStep(
                step_id=len(steps),
                blocks_accessed=list(attention_scores.keys()),
                attention_scores=attention_scores,
                true_top_k=true_top_k,
                query_block_id=query_block,
            ))

        return steps


class TestAdversarialWorkloads:
    """Tests for adversarial scenarios."""

    @pytest.fixture
    def generator(self):
        return AdversarialTraceGenerator(seed=42)

    def run_evaluation(
        self,
        steps: List[TraceStep],
        k: int = 64,
    ) -> tuple:
        """Run PCAM and baseline on steps, return (pcam_cov, pcam_mass, base_cov, base_mass)."""
        interface = SoftwarePCAMInterface(max_sequences=4, max_blocks_per_sequence=1024)
        interface.allocate_sequence(0, 1024)

        config = ControllerConfig(cache_capacity=256, num_sinks=4, recent_window=64, top_k=k)
        baseline = IndustryStyleController(config)

        pcam_coverages = []
        pcam_masses = []
        base_coverages = []
        base_masses = []

        for step in steps:
            # PCAM
            candidates, _, _ = interface.attend(step.query_block_id, k=k, sequence_id=0)
            pcam_ids = set(c[0] for c in candidates)

            # Baseline
            base_cands = baseline.get_candidates(step.query_block_id, k=k, sequence_id=0)
            base_ids = set(c[0] for c in base_cands)

            # Coverage
            true_set = set(step.true_top_k[:k])
            pcam_coverages.append(len(pcam_ids & true_set) / max(1, len(true_set)))
            base_coverages.append(len(base_ids & true_set) / max(1, len(true_set)))

            # Mass
            total = sum(step.attention_scores.values())
            pcam_mass = sum(step.attention_scores.get(b, 0) for b in pcam_ids)
            base_mass = sum(step.attention_scores.get(b, 0) for b in base_ids)
            pcam_masses.append(pcam_mass / max(0.001, total))
            base_masses.append(base_mass / max(0.001, total))

            # Update both
            for block_id, weight in step.attention_scores.items():
                interface.update(step.query_block_id, block_id, weight, 0)
            baseline.record_access(
                step.query_block_id,
                step.blocks_accessed,
                step.attention_scores,
                0,
            )

            interface.step()
            baseline.step()

        return (
            sum(pcam_coverages) / len(pcam_coverages),
            sum(pcam_masses) / len(pcam_masses),
            sum(base_coverages) / len(base_coverages),
            sum(base_masses) / len(base_masses),
        )

    def test_rapid_topic_drift(self, generator):
        """Test behavior under rapid topic drift."""
        steps = generator.generate_rapid_drift(num_topics=10, tokens_per_topic=50)

        pcam_cov, pcam_mass, base_cov, base_mass = self.run_evaluation(steps)

        print("\n" + "=" * 60)
        print("ADVERSARIAL: Rapid Topic Drift")
        print("=" * 60)
        print("Topics switch completely every 50 tokens.")
        print()
        print(f"{'Controller':<15} {'Coverage':>12} {'Mass Recall':>12}")
        print("-" * 40)
        print(f"{'PCAM':<15} {pcam_cov:>12.1%} {pcam_mass:>12.1%}")
        print(f"{'Baseline':<15} {base_cov:>12.1%} {base_mass:>12.1%}")

        # Check degradation is graceful (not catastrophic)
        assert pcam_mass > 0.2, f"Catastrophic failure: {pcam_mass}"

    def test_distractor_documents(self, generator):
        """Test RAG with misleading distractors."""
        steps = generator.generate_distractor_docs(
            num_docs=5,
            distractor_overlap=0.9,  # Very similar distractors
        )

        pcam_cov, pcam_mass, base_cov, base_mass = self.run_evaluation(steps)

        print("\n" + "=" * 60)
        print("ADVERSARIAL: Distractor Documents")
        print("=" * 60)
        print("5 docs, only 1 relevant, distractors 90% similar.")
        print()
        print(f"{'Controller':<15} {'Coverage':>12} {'Mass Recall':>12}")
        print("-" * 40)
        print(f"{'PCAM':<15} {pcam_cov:>12.1%} {pcam_mass:>12.1%}")
        print(f"{'Baseline':<15} {base_cov:>12.1%} {base_mass:>12.1%}")

    def test_template_repetition(self, generator):
        """Test repeated template prompts."""
        steps = generator.generate_template_repetition(num_repeats=20)

        pcam_cov, pcam_mass, base_cov, base_mass = self.run_evaluation(steps)

        print("\n" + "=" * 60)
        print("ADVERSARIAL: Template Repetition")
        print("=" * 60)
        print("Same 50-token pattern repeated 20 times.")
        print()
        print(f"{'Controller':<15} {'Coverage':>12} {'Mass Recall':>12}")
        print("-" * 40)
        print(f"{'PCAM':<15} {pcam_cov:>12.1%} {pcam_mass:>12.1%}")
        print(f"{'Baseline':<15} {base_cov:>12.1%} {base_mass:>12.1%}")

    def test_far_dependencies(self, generator):
        """Test code with far dependencies."""
        steps = generator.generate_far_dependencies(
            file_length=8192,
            dependency_distance=4000,
        )

        pcam_cov, pcam_mass, base_cov, base_mass = self.run_evaluation(steps)

        print("\n" + "=" * 60)
        print("ADVERSARIAL: Far Dependencies")
        print("=" * 60)
        print("8K file, imports at top, usage 4000 tokens later.")
        print()
        print(f"{'Controller':<15} {'Coverage':>12} {'Mass Recall':>12}")
        print("-" * 40)
        print(f"{'PCAM':<15} {pcam_cov:>12.1%} {pcam_mass:>12.1%}")
        print(f"{'Baseline':<15} {base_cov:>12.1%} {base_mass:>12.1%}")

        # Far dependencies are hard - check we don't completely fail
        assert pcam_mass > 0.15, f"Failed to maintain far dependencies: {pcam_mass}"

    def test_adversarial_summary(self, generator):
        """Run all adversarial scenarios and summarize."""
        scenarios = {
            "Rapid Drift": generator.generate_rapid_drift(),
            "Distractors": generator.generate_distractor_docs(),
            "Templates": generator.generate_template_repetition(),
            "Far Deps": generator.generate_far_dependencies(),
        }

        print("\n" + "=" * 70)
        print("ADVERSARIAL WORKLOAD SUMMARY")
        print("=" * 70)
        print()
        print(f"{'Scenario':<20} {'PCAM Mass':>12} {'Base Mass':>12} {'Δ':>10} {'Status':>12}")
        print("-" * 70)

        for name, steps in scenarios.items():
            pcam_cov, pcam_mass, base_cov, base_mass = self.run_evaluation(steps)
            delta = pcam_mass - base_mass

            if pcam_mass < 0.2:
                status = "CRITICAL"
            elif pcam_mass < base_mass * 0.8:
                status = "DEGRADED"
            else:
                status = "OK"

            print(
                f"{name:<20} "
                f"{pcam_mass:>12.1%} "
                f"{base_mass:>12.1%} "
                f"{delta:>+10.1%} "
                f"{status:>12}"
            )
