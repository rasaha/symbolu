"""
Tests for PCAM trace format and generators.
"""

import pytest
from simulator.pcam.traces.format import PCAMTrace, TraceStep, TraceMetadata
from simulator.pcam.traces.generators import (
    SyntheticTraceGenerator,
    generate_chat_trace,
    generate_long_context_trace,
    generate_rag_trace,
    generate_code_trace,
    generate_multitenant_trace,
)


class TestTraceFormat:
    """Tests for trace format classes."""

    def test_trace_step_creation(self):
        """Test TraceStep can be created."""
        step = TraceStep(
            step_id=0,
            blocks_accessed=[0, 1, 2],
            attention_scores={0: 0.5, 1: 0.3, 2: 0.2},
            true_top_k=[0, 1],
        )
        assert step.step_id == 0
        assert len(step.blocks_accessed) == 3
        assert step.attention_scores[0] == 0.5
        assert step.true_top_k == [0, 1]

    def test_trace_step_serialization(self):
        """Test TraceStep can be serialized and deserialized."""
        step = TraceStep(
            step_id=5,
            blocks_accessed=[10, 20, 30],
            attention_scores={10: 0.6, 20: 0.3, 30: 0.1},
            true_top_k=[10, 20],
            sequence_id=1,
        )

        d = step.to_dict()
        restored = TraceStep.from_dict(d)

        assert restored.step_id == step.step_id
        assert restored.blocks_accessed == step.blocks_accessed
        assert restored.attention_scores == step.attention_scores
        assert restored.true_top_k == step.true_top_k
        assert restored.sequence_id == step.sequence_id

    def test_trace_creation(self):
        """Test PCAMTrace can be created."""
        metadata = TraceMetadata(
            workload_type="test",
            total_tokens=100,
            context_length=1000,
        )
        steps = [
            TraceStep(step_id=i, blocks_accessed=[i], attention_scores={i: 1.0})
            for i in range(10)
        ]
        trace = PCAMTrace(metadata=metadata, steps=steps)

        assert trace.num_steps == 10
        assert trace.metadata.workload_type == "test"

    def test_trace_serialization(self):
        """Test PCAMTrace can be serialized and deserialized."""
        metadata = TraceMetadata(
            model_name="test-model",
            workload_type="chat",
            total_tokens=50,
            context_length=500,
            num_sequences=2,
        )
        steps = [
            TraceStep(
                step_id=i,
                blocks_accessed=[i, i + 1],
                attention_scores={i: 0.7, i + 1: 0.3},
                true_top_k=[i],
                sequence_id=i % 2,
            )
            for i in range(5)
        ]
        trace = PCAMTrace(metadata=metadata, steps=steps)

        d = trace.to_dict()
        restored = PCAMTrace.from_dict(d)

        assert restored.num_steps == trace.num_steps
        assert restored.metadata.model_name == trace.metadata.model_name
        assert restored.metadata.num_sequences == trace.metadata.num_sequences
        assert restored.sequence_ids == trace.sequence_ids

    def test_trace_validation(self):
        """Test trace validation."""
        # Valid trace
        metadata = TraceMetadata(workload_type="test", total_tokens=5)
        steps = [TraceStep(step_id=i) for i in range(5)]
        trace = PCAMTrace(metadata=metadata, steps=steps)
        issues = trace.validate()
        assert len(issues) == 0

        # Invalid trace (wrong step_id)
        bad_steps = [TraceStep(step_id=99)]
        bad_trace = PCAMTrace(metadata=metadata, steps=bad_steps)
        issues = bad_trace.validate()
        assert len(issues) > 0


class TestTraceGenerators:
    """Tests for synthetic trace generators."""

    def test_generator_reproducibility(self):
        """Test that generators are reproducible with same seed."""
        gen1 = SyntheticTraceGenerator(seed=42)
        gen2 = SyntheticTraceGenerator(seed=42)

        trace1 = gen1.generate_chat_trace(num_turns=3)
        trace2 = gen2.generate_chat_trace(num_turns=3)

        assert trace1.num_steps == trace2.num_steps
        for s1, s2 in zip(trace1.steps, trace2.steps):
            assert s1.attention_scores == s2.attention_scores

    def test_chat_trace_generation(self):
        """Test chat trace generation."""
        trace = generate_chat_trace(
            num_turns=5,
            tokens_per_turn=(10, 20),
        )

        assert trace.metadata.workload_type == "chat"
        assert trace.num_steps > 0
        assert trace.num_steps >= 5 * 10  # At least min tokens per turn

        # Check that steps have valid structure
        for step in trace.steps:
            assert len(step.attention_scores) > 0
            assert len(step.true_top_k) > 0

    def test_long_context_trace_generation(self):
        """Test long context trace generation."""
        trace = generate_long_context_trace(
            context_length=8192,
            num_queries=20,
        )

        assert trace.metadata.workload_type == "long_context"
        assert trace.num_steps == 20
        assert trace.metadata.context_length == 8192

    def test_rag_trace_generation(self):
        """Test RAG trace generation."""
        trace = generate_rag_trace(
            num_docs=4,
            doc_length=512,
            relevant_docs=2,
            query_length=50,
        )

        assert trace.metadata.workload_type == "rag"
        assert trace.num_steps == 50

        # RAG traces should have sparse attention to documents
        for step in trace.steps:
            assert len(step.attention_scores) > 0

    def test_code_trace_generation(self):
        """Test code trace generation."""
        trace = generate_code_trace(
            file_length=2048,
            num_queries=30,
        )

        assert trace.metadata.workload_type == "code"
        assert trace.num_steps == 30

        # Code traces should have attention to imports at the beginning
        for step in trace.steps:
            # Should have some attention to early blocks (imports)
            early_blocks = [b for b in step.attention_scores.keys() if b < 10]
            assert len(early_blocks) > 0 or step.query_block_id < 10

    def test_multitenant_trace_generation(self):
        """Test multi-tenant trace generation."""
        trace = generate_multitenant_trace(
            num_sequences=8,
            total_steps=100,
            length_distribution="mixed",
        )

        assert trace.metadata.workload_type == "multitenant"
        assert trace.metadata.num_sequences == 8
        assert trace.num_steps <= 100

        # Check that multiple sequences are represented
        seq_ids = trace.sequence_ids
        assert len(seq_ids) > 1

    def test_trace_has_ground_truth(self):
        """Test that generated traces have ground truth top-K."""
        trace = generate_chat_trace(num_turns=3, top_k=16)

        for step in trace.steps:
            assert len(step.true_top_k) <= 16
            # true_top_k should be subset of blocks with attention
            for block_id in step.true_top_k:
                assert block_id in step.attention_scores
