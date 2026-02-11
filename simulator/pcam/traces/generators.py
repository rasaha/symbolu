"""
Synthetic trace generators for PCAM validation.

Generates realistic attention patterns for various workloads
as specified in Appendix H.3.3.
"""

import random
import math
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

from .format import PCAMTrace, TraceStep, TraceMetadata


@dataclass
class AttentionPattern:
    """Configurable attention pattern."""
    # Recency bias: fraction of attention to recent tokens
    recency_weight: float = 0.5

    # Sink weight: fraction to first few tokens
    sink_weight: float = 0.2

    # Sparse weight: fraction to random important tokens
    sparse_weight: float = 0.3

    # Number of sink tokens
    num_sinks: int = 4

    # Recent window size
    recent_window: int = 256


class SyntheticTraceGenerator:
    """
    Generate realistic traces without proprietary data.

    Implements the generators from Appendix H.3.3.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def _generate_attention_scores(
        self,
        current_pos: int,
        context_length: int,
        pattern: AttentionPattern,
        block_size: int = 16,
    ) -> Dict[int, float]:
        """
        Generate realistic attention score distribution.

        Returns block_id -> attention_weight mapping.
        """
        scores: Dict[int, float] = {}

        current_block = current_pos // block_size
        num_blocks = (context_length + block_size - 1) // block_size

        if num_blocks == 0:
            return scores

        # Sink attention (first few blocks)
        num_sink_blocks = max(1, pattern.num_sinks // block_size)
        for i in range(min(num_sink_blocks, num_blocks)):
            scores[i] = pattern.sink_weight / num_sink_blocks

        # Recent window attention
        recent_blocks = pattern.recent_window // block_size
        for i in range(max(0, current_block - recent_blocks), current_block + 1):
            if i < num_blocks:
                # Decay with distance from current
                distance = current_block - i
                weight = pattern.recency_weight * math.exp(-distance / recent_blocks)
                scores[i] = scores.get(i, 0) + weight

        # Sparse attention (random important blocks)
        num_sparse = max(1, int(num_blocks * 0.1))  # 10% of blocks
        sparse_blocks = self.rng.sample(
            range(num_blocks),
            min(num_sparse, num_blocks)
        )
        for block_id in sparse_blocks:
            scores[block_id] = scores.get(block_id, 0) + (
                pattern.sparse_weight / num_sparse
            )

        # Normalize
        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}

        return scores

    def _get_top_k_blocks(
        self,
        scores: Dict[int, float],
        k: int,
    ) -> List[int]:
        """Get top-K blocks by score."""
        sorted_blocks = sorted(scores.items(), key=lambda x: -x[1])
        return [block_id for block_id, _ in sorted_blocks[:k]]

    def generate_chat_trace(
        self,
        num_turns: int = 10,
        tokens_per_turn: Tuple[int, int] = (50, 200),
        revisit_probability: float = 0.3,
        block_size: int = 16,
        top_k: int = 64,
    ) -> PCAMTrace:
        """
        Multi-turn chat with context revisitation.

        Args:
            num_turns: Number of conversation turns
            tokens_per_turn: (min, max) tokens per turn
            revisit_probability: Probability of referencing earlier turn
            block_size: Tokens per KV block
            top_k: Number of top-K blocks for ground truth
        """
        steps: List[TraceStep] = []
        turn_boundaries: List[int] = [0]  # Token positions where turns start

        total_tokens = 0

        for turn in range(num_turns):
            turn_length = self.rng.randint(*tokens_per_turn)
            turn_start = total_tokens

            for pos_in_turn in range(turn_length):
                current_pos = total_tokens

                # Create attention pattern
                pattern = AttentionPattern(
                    recency_weight=0.5,
                    sink_weight=0.2,
                    sparse_weight=0.3,
                )

                # Maybe reference earlier turn
                if turn > 0 and self.rng.random() < revisit_probability:
                    # Pick a random earlier turn
                    ref_turn = self.rng.randint(0, turn - 1)
                    ref_start = turn_boundaries[ref_turn]
                    ref_block = ref_start // block_size

                    scores = self._generate_attention_scores(
                        current_pos, current_pos + 1, pattern, block_size
                    )
                    # Boost the referenced turn's block
                    scores[ref_block] = scores.get(ref_block, 0) + 0.3
                else:
                    scores = self._generate_attention_scores(
                        current_pos, current_pos + 1, pattern, block_size
                    )

                blocks_accessed = list(scores.keys())
                true_top_k = self._get_top_k_blocks(scores, top_k)

                steps.append(TraceStep(
                    step_id=len(steps),
                    blocks_accessed=blocks_accessed,
                    attention_scores=scores,
                    true_top_k=true_top_k,
                    query_block_id=current_pos // block_size,
                ))

                total_tokens += 1

            turn_boundaries.append(total_tokens)

        metadata = TraceMetadata(
            workload_type="chat",
            total_tokens=total_tokens,
            context_length=total_tokens,
            num_sequences=1,
        )

        return PCAMTrace(metadata=metadata, steps=steps)

    def generate_long_context_trace(
        self,
        context_length: int = 65536,
        num_queries: int = 100,
        attention_locality: float = 0.7,
        block_size: int = 16,
        top_k: int = 64,
    ) -> PCAMTrace:
        """
        Long document with distributed attention.

        Args:
            context_length: Total context length in tokens
            num_queries: Number of query positions to generate
            attention_locality: Fraction of attention that's local
            block_size: Tokens per KV block
            top_k: Number of top-K blocks for ground truth
        """
        steps: List[TraceStep] = []

        # Query positions spread through the document
        query_positions = sorted(
            self.rng.sample(range(context_length // 2, context_length), num_queries)
        )

        for query_pos in query_positions:
            pattern = AttentionPattern(
                recency_weight=attention_locality * 0.7,
                sink_weight=0.1,
                sparse_weight=1 - attention_locality,
                recent_window=512,  # Larger window for long context
            )

            scores = self._generate_attention_scores(
                query_pos, query_pos + 1, pattern, block_size
            )

            # Add some long-range dependencies
            num_long_range = int((1 - attention_locality) * 20)
            for _ in range(num_long_range):
                far_block = self.rng.randint(0, query_pos // block_size)
                scores[far_block] = scores.get(far_block, 0) + 0.02

            blocks_accessed = list(scores.keys())
            true_top_k = self._get_top_k_blocks(scores, top_k)

            steps.append(TraceStep(
                step_id=len(steps),
                blocks_accessed=blocks_accessed,
                attention_scores=scores,
                true_top_k=true_top_k,
                query_block_id=query_pos // block_size,
            ))

        metadata = TraceMetadata(
            workload_type="long_context",
            total_tokens=num_queries,
            context_length=context_length,
            num_sequences=1,
        )

        return PCAMTrace(metadata=metadata, steps=steps)

    def generate_rag_trace(
        self,
        num_docs: int = 5,
        doc_length: int = 2048,
        relevant_docs: int = 2,
        query_length: int = 100,
        block_size: int = 16,
        top_k: int = 64,
    ) -> PCAMTrace:
        """
        RAG with sparse relevant spans.

        Args:
            num_docs: Number of retrieved documents
            doc_length: Tokens per document
            relevant_docs: Number of actually relevant documents
            query_length: Length of the query/answer generation
            block_size: Tokens per KV block
            top_k: Number of top-K blocks for ground truth
        """
        steps: List[TraceStep] = []

        total_context = num_docs * doc_length
        context_start = 0  # Documents come first

        # Pick which docs are relevant
        relevant_doc_ids = self.rng.sample(range(num_docs), relevant_docs)

        for query_pos in range(query_length):
            current_pos = total_context + query_pos
            scores: Dict[int, float] = {}

            # Strong attention to relevant document blocks
            for doc_id in relevant_doc_ids:
                doc_start = doc_id * doc_length
                doc_blocks_start = doc_start // block_size
                doc_blocks_end = (doc_start + doc_length) // block_size

                # Pick a few blocks from each relevant doc
                num_relevant_blocks = max(5, doc_length // block_size // 10)
                relevant_blocks = self.rng.sample(
                    range(doc_blocks_start, doc_blocks_end),
                    min(num_relevant_blocks, doc_blocks_end - doc_blocks_start)
                )
                for block_id in relevant_blocks:
                    scores[block_id] = self.rng.uniform(0.05, 0.15)

            # Weak attention to other docs
            for doc_id in range(num_docs):
                if doc_id not in relevant_doc_ids:
                    doc_start = doc_id * doc_length
                    doc_blocks_start = doc_start // block_size
                    doc_blocks_end = (doc_start + doc_length) // block_size

                    # Just a couple blocks
                    if doc_blocks_end > doc_blocks_start:
                        weak_blocks = self.rng.sample(
                            range(doc_blocks_start, doc_blocks_end),
                            min(2, doc_blocks_end - doc_blocks_start)
                        )
                        for block_id in weak_blocks:
                            scores[block_id] = self.rng.uniform(0.001, 0.01)

            # Recent query tokens
            query_block = current_pos // block_size
            for i in range(max(0, query_block - 4), query_block + 1):
                scores[i] = scores.get(i, 0) + 0.1

            # Normalize
            total = sum(scores.values())
            if total > 0:
                scores = {k: v / total for k, v in scores.items()}

            blocks_accessed = list(scores.keys())
            true_top_k = self._get_top_k_blocks(scores, top_k)

            steps.append(TraceStep(
                step_id=len(steps),
                blocks_accessed=blocks_accessed,
                attention_scores=scores,
                true_top_k=true_top_k,
                query_block_id=query_block,
            ))

        metadata = TraceMetadata(
            workload_type="rag",
            total_tokens=query_length,
            context_length=total_context + query_length,
            num_sequences=1,
        )

        return PCAMTrace(metadata=metadata, steps=steps)

    def generate_code_trace(
        self,
        file_length: int = 4096,
        import_distance: int = 1000,
        num_queries: int = 200,
        block_size: int = 16,
        top_k: int = 64,
    ) -> PCAMTrace:
        """
        Code with structured dependencies.

        Simulates code completion where imports/definitions at the
        top of file are referenced when completing code at the bottom.

        Structural metadata: each block gets a scope_id indicating its
        structural group (import group, function/class definition, or
        code body section). Queries reference specific definition groups,
        creating symbolic linkage that PCAM can exploit.

        Args:
            file_length: Total file length in tokens
            import_distance: Distance to import/definition section
            num_queries: Number of completion positions
            block_size: Tokens per KV block
            top_k: Number of top-K blocks for ground truth
        """
        steps: List[TraceStep] = []

        # Define structure: imports at top, definitions in middle, current code at bottom
        import_section_end = file_length // 10  # First 10%
        definition_section_end = file_length // 2  # 10-50%

        import_blocks = import_section_end // block_size
        def_blocks_start = import_section_end // block_size
        def_blocks_end = definition_section_end // block_size
        total_def_blocks = def_blocks_end - def_blocks_start
        code_blocks_start = definition_section_end // block_size
        total_blocks = file_length // block_size

        # --- Build structural scope map ---
        # Scope 0: imports (all import blocks share scope 0)
        SCOPE_IMPORTS = 0

        # Scopes 1..N: definition groups (simulating functions/classes)
        # Each group is a cluster of 2-5 adjacent definition blocks
        def_groups: List[List[int]] = []  # list of [block_ids] per group
        def_block_to_scope: Dict[int, int] = {}
        scope_id = 1
        pos = def_blocks_start
        while pos < def_blocks_end:
            group_size = self.rng.randint(2, 5)
            group_blocks = list(range(pos, min(pos + group_size, def_blocks_end)))
            def_groups.append(group_blocks)
            for b in group_blocks:
                def_block_to_scope[b] = scope_id
            scope_id += 1
            pos += group_size

        num_def_groups = len(def_groups)

        # Scopes for code body: divide into sections of ~20 blocks each
        # Each code section depends on 2-4 specific definition groups
        code_section_size = 20
        code_sections: List[Dict] = []
        for sec_start in range(code_blocks_start, total_blocks, code_section_size):
            sec_end = min(sec_start + code_section_size, total_blocks)
            # This code section depends on 2-4 definition groups
            num_deps = self.rng.randint(2, min(4, num_def_groups))
            dep_groups = self.rng.sample(range(num_def_groups), num_deps)
            code_sections.append({
                "start": sec_start,
                "end": sec_end,
                "scope_id": scope_id,
                "dep_groups": dep_groups,
            })
            scope_id += 1

        query_positions = sorted(
            self.rng.sample(range(definition_section_end, file_length), num_queries)
        )

        for query_pos in query_positions:
            scores: Dict[int, float] = {}
            structural_hints: Dict[int, int] = {}

            current_block = query_pos // block_size

            # Find which code section this query belongs to
            query_section = None
            for sec in code_sections:
                if sec["start"] <= current_block < sec["end"]:
                    query_section = sec
                    break
            if query_section is None:
                # Default to last section
                query_section = code_sections[-1] if code_sections else {
                    "scope_id": scope_id,
                    "dep_groups": list(range(min(3, num_def_groups))),
                }

            # Assign query block's scope
            structural_hints[current_block] = query_section["scope_id"]

            # Strong attention to imports (all share SCOPE_IMPORTS)
            for i in range(import_blocks):
                scores[i] = self.rng.uniform(0.02, 0.05)
                structural_hints[i] = SCOPE_IMPORTS

            # Medium attention to definitions FROM THIS SECTION'S DEPENDENCIES
            # This is the key structural link: not random definitions,
            # but the specific groups this code section depends on.
            #
            # Within each group, the first block is the "signature" (function
            # def, class header) — always referenced with high attention.
            # Remaining blocks are "body" — referenced with lower probability
            # and lower attention.  This creates intra-scope variance.
            def_refs = []
            for gi in query_section["dep_groups"]:
                group = def_groups[gi]
                # Signature block: always included, high attention
                def_refs.append((group[0], self.rng.uniform(0.06, 0.12)))
                # Body blocks: included with 40% probability, lower attention
                for b in group[1:]:
                    if self.rng.random() < 0.4:
                        def_refs.append((b, self.rng.uniform(0.01, 0.04)))

            for block_id, attn in def_refs:
                scores[block_id] = attn
                structural_hints[block_id] = def_block_to_scope[block_id]

            # Also annotate all blocks in the dependent groups
            # (even ones not sampled for this query — they're still structurally linked)
            for gi in query_section["dep_groups"]:
                for b in def_groups[gi]:
                    if b not in structural_hints:
                        structural_hints[b] = def_block_to_scope[b]

            # Strong attention to recent context (shares query's scope)
            for i in range(max(0, current_block - 8), current_block + 1):
                distance = current_block - i
                scores[i] = scores.get(i, 0) + 0.1 * math.exp(-distance / 4)
                structural_hints[i] = query_section["scope_id"]

            # Normalize
            total = sum(scores.values())
            if total > 0:
                scores = {k: v / total for k, v in scores.items()}

            blocks_accessed = list(scores.keys())
            true_top_k = self._get_top_k_blocks(scores, top_k)

            steps.append(TraceStep(
                step_id=len(steps),
                blocks_accessed=blocks_accessed,
                attention_scores=scores,
                true_top_k=true_top_k,
                query_block_id=current_block,
                block_structural_hints=structural_hints,
            ))

        metadata = TraceMetadata(
            workload_type="code",
            total_tokens=num_queries,
            context_length=file_length,
            num_sequences=1,
        )

        return PCAMTrace(metadata=metadata, steps=steps)

    def generate_multitenant_trace(
        self,
        num_sequences: int = 32,
        length_distribution: str = "mixed",
        total_steps: int = 1000,
        block_size: int = 16,
        top_k: int = 64,
    ) -> PCAMTrace:
        """
        Concurrent sequences for batched inference.

        Args:
            num_sequences: Number of concurrent sequences
            length_distribution: "uniform", "mixed", or "heavy_tail"
            total_steps: Total steps across all sequences
            block_size: Tokens per KV block
            top_k: Number of top-K blocks for ground truth
        """
        steps: List[TraceStep] = []

        # Generate sequence lengths based on distribution
        if length_distribution == "uniform":
            seq_lengths = [total_steps // num_sequences] * num_sequences
        elif length_distribution == "heavy_tail":
            # Power law distribution
            seq_lengths = [
                int((i + 1) ** -0.5 * total_steps / sum((j + 1) ** -0.5 for j in range(num_sequences)))
                for i in range(num_sequences)
            ]
        else:  # mixed
            seq_lengths = [
                self.rng.randint(total_steps // (num_sequences * 2), total_steps // num_sequences * 2)
                for _ in range(num_sequences)
            ]

        # Track current position in each sequence
        seq_positions = [0] * num_sequences

        step_id = 0
        for _ in range(total_steps):
            # Pick a sequence that still has work
            active_seqs = [
                i for i in range(num_sequences)
                if seq_positions[i] < seq_lengths[i]
            ]
            if not active_seqs:
                break

            seq_id = self.rng.choice(active_seqs)
            current_pos = seq_positions[seq_id]

            # Generate attention for this sequence
            pattern = AttentionPattern(
                recency_weight=0.6,
                sink_weight=0.15,
                sparse_weight=0.25,
            )

            scores = self._generate_attention_scores(
                current_pos, current_pos + 1, pattern, block_size
            )

            blocks_accessed = list(scores.keys())
            true_top_k = self._get_top_k_blocks(scores, top_k)

            steps.append(TraceStep(
                step_id=step_id,
                blocks_accessed=blocks_accessed,
                attention_scores=scores,
                true_top_k=true_top_k,
                sequence_id=seq_id,
                batch_position=active_seqs.index(seq_id),
                query_block_id=current_pos // block_size,
            ))

            seq_positions[seq_id] += 1
            step_id += 1

        metadata = TraceMetadata(
            workload_type="multitenant",
            total_tokens=step_id,
            context_length=max(seq_lengths),
            num_sequences=num_sequences,
        )

        return PCAMTrace(metadata=metadata, steps=steps)


# Convenience functions
def generate_chat_trace(**kwargs) -> PCAMTrace:
    """Generate a chat workload trace."""
    return SyntheticTraceGenerator().generate_chat_trace(**kwargs)


def generate_long_context_trace(**kwargs) -> PCAMTrace:
    """Generate a long-context workload trace."""
    return SyntheticTraceGenerator().generate_long_context_trace(**kwargs)


def generate_rag_trace(**kwargs) -> PCAMTrace:
    """Generate a RAG workload trace."""
    return SyntheticTraceGenerator().generate_rag_trace(**kwargs)


def generate_code_trace(**kwargs) -> PCAMTrace:
    """Generate a code completion workload trace."""
    return SyntheticTraceGenerator().generate_code_trace(**kwargs)


def generate_multitenant_trace(**kwargs) -> PCAMTrace:
    """Generate a multi-tenant workload trace."""
    return SyntheticTraceGenerator().generate_multitenant_trace(**kwargs)
