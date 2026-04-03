"""
RLM-Phase-Quad Integration Module.

Combines Recursive Language Models (RLM) orchestration with Phase-Quad
efficient processing for unlimited context handling.

Key components:
- REPLEnvironment: Python REPL for context management
- BoundaryAwareChunker: HP-Quad based semantic chunking
- PhaseStateManager: Persistent state across recursive calls
- MemoryBankSynchronizer: REPL vars → Quad memory banks
- QualityAwareRecursionController: Reflective quality control
- RLMPhaseQuadSystem: Complete integrated system

Usage:
    from agentic.rlm_phase_quad import RLMPhaseQuadSystem, RLMPhaseQuadConfig

    config = RLMPhaseQuadConfig(d_model=512, enable_reflective=True)
    system = RLMPhaseQuadSystem(config)

    answer = system.query(context="...", question="...")

Reference:
- Zhang, Kraska, Khattab (2025): "Recursive Language Models"
- Phase-Quad Architecture: Internal design documents
"""

from typing import Dict, List, Tuple, Optional, Any, Callable, Union, Set
from dataclasses import dataclass, field
import hashlib
import time
import re

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

# Import Phase-Quad components
try:
    from .hp_quad import (
        HPQuadBlock,
        HPQuadConfig,
        HierarchicalPhaseIntegrator,
        BoundaryDetector,
    )
    HP_QUAD_AVAILABLE = True
except ImportError:
    HP_QUAD_AVAILABLE = False


@dataclass
class RLMPhaseQuadConfig:
    """
    Configuration for RLM-Phase-Quad integrated system.

    Attributes:
        d_model: Model dimension
        d_phase_levels: Phase dimensions per hierarchy level
        num_levels: Number of hierarchy levels
        chunk_sizes: Chunk sizes per level for Quad Proposal
        min_chunk_size: Minimum tokens per semantic chunk
        max_chunk_size: Maximum tokens per semantic chunk
        boundary_threshold: Threshold for boundary detection
        enable_reflective: Whether to enable quality control
        quality_threshold: Quality threshold for acceptance
        max_revisions: Maximum revisions per sub-query
        max_recursion_depth: Maximum recursion depth
        max_branches: Maximum concurrent branches
        max_memories_per_level: Memory bank size limits
        device: Torch device
    """
    # Model dimensions
    d_model: int = 512
    d_phase_levels: Tuple[int, ...] = (128, 256, 512)
    num_levels: int = 3
    chunk_sizes: Tuple[int, ...] = (1, 8, 64)

    # Chunking
    min_chunk_size: int = 100
    max_chunk_size: int = 4096
    boundary_threshold: float = 0.5

    # Quality control
    enable_reflective: bool = True
    quality_threshold: float = 0.7
    max_revisions: int = 3

    # Recursion
    max_recursion_depth: int = 5
    decomposition_strategies: List[str] = field(
        default_factory=lambda: ["semantic", "fixed", "overlap"]
    )

    # Memory
    max_memories_per_level: Tuple[int, ...] = (1000, 500, 100)
    max_branches: int = 100

    # Device
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


@dataclass
class REPLEnvironment:
    """
    Python REPL environment for RLM context management.

    Stores raw context, intermediate results, and accumulated knowledge.
    """
    # Primary storage
    context: str = ""
    chunks: List[str] = field(default_factory=list)
    chunk_boundaries: List[int] = field(default_factory=list)

    # Accumulated knowledge
    sub_results: Dict[str, Any] = field(default_factory=dict)
    key_facts: List[str] = field(default_factory=list)
    search_cache: Dict[str, List[str]] = field(default_factory=dict)

    # Execution metadata
    execution_tree: Dict = field(default_factory=dict)
    quality_scores: Dict[str, float] = field(default_factory=dict)

    def clear(self):
        """Clear all environment state."""
        self.context = ""
        self.chunks = []
        self.chunk_boundaries = []
        self.sub_results = {}
        self.key_facts = []
        self.search_cache = {}
        self.execution_tree = {}
        self.quality_scores = {}


class PhaseStateManager:
    """
    Manages Phase State persistence across RLM recursive calls.

    Features:
    - Branch-aware state tracking
    - State inheritance (child inherits parent)
    - State merging (combine siblings)
    - Garbage collection
    """

    def __init__(
        self,
        d_phase_levels: Tuple[int, ...] = (128, 256, 512),
        max_branches: int = 100,
        device: str = "cuda",
    ):
        self.d_phase_levels = d_phase_levels
        self.max_branches = max_branches
        self.device = device

        # State storage
        self.states: Dict[str, List[Tensor]] = {}
        self.branch_tree: Dict[str, str] = {}  # child -> parent
        self.completed: Set[str] = set()

    def get_state(
        self,
        branch_id: str,
        inherit_from_parent: bool = True,
    ) -> Optional[List[Tensor]]:
        """
        Get Phase State for a branch.

        If branch doesn't exist and inherit_from_parent is True,
        clones parent's state as starting point.
        """
        if branch_id in self.states:
            return self.states[branch_id]

        if inherit_from_parent and branch_id in self.branch_tree:
            parent_id = self.branch_tree[branch_id]
            if parent_id in self.states:
                # Clone parent state
                parent_state = self.states[parent_id]
                self.states[branch_id] = [s.clone() for s in parent_state]
                return self.states[branch_id]

        # Initialize new state
        self.states[branch_id] = [
            torch.zeros(1, d_phase, device=self.device)
            for d_phase in self.d_phase_levels
        ]
        return self.states[branch_id]

    def update_state(self, branch_id: str, new_state: List[Tensor]):
        """Update Phase State for a branch."""
        self.states[branch_id] = new_state

    def create_child_branch(self, parent_id: str, child_id: str):
        """Register a child branch with its parent."""
        self.branch_tree[child_id] = parent_id

    def merge_sibling_states(
        self,
        branch_ids: List[str],
        merge_strategy: str = "mean",
    ) -> Optional[List[Tensor]]:
        """
        Merge states from sibling branches.

        Strategies: mean, max
        """
        sibling_states = [
            self.states[bid] for bid in branch_ids
            if bid in self.states
        ]

        if not sibling_states:
            return None

        if merge_strategy == "mean":
            merged = []
            for level in range(len(sibling_states[0])):
                level_states = torch.stack([s[level] for s in sibling_states])
                merged.append(level_states.mean(dim=0))
            return merged

        elif merge_strategy == "max":
            merged = []
            for level in range(len(sibling_states[0])):
                level_states = torch.stack([s[level] for s in sibling_states])
                merged.append(level_states.max(dim=0).values)
            return merged

        else:
            raise ValueError(f"Unknown merge strategy: {merge_strategy}")

    def mark_completed(self, branch_id: str):
        """Mark a branch as completed for garbage collection."""
        self.completed.add(branch_id)

    def garbage_collect(self):
        """Remove completed branches to free memory."""
        for branch_id in list(self.completed):
            if branch_id in self.states:
                del self.states[branch_id]
            self.completed.discard(branch_id)

    def clear(self):
        """Clear all state."""
        self.states.clear()
        self.branch_tree.clear()
        self.completed.clear()


class BoundaryAwareChunker:
    """
    Uses HP-Quad boundary detection for semantic chunking.

    Instead of arbitrary fixed-size chunks, splits at learned
    semantic boundaries (sentence, paragraph, section, topic).
    """

    def __init__(
        self,
        hp_quad: Optional[HPQuadBlock] = None,
        min_chunk_size: int = 100,
        max_chunk_size: int = 4096,
        boundary_threshold: float = 0.5,
    ):
        self.hp_quad = hp_quad
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.boundary_threshold = boundary_threshold

    def chunk(self, context: str) -> Tuple[List[str], List[int]]:
        """
        Split context at semantic boundaries.

        If HP-Quad not available, falls back to sentence/paragraph splitting.
        """
        if self.hp_quad is None or not HP_QUAD_AVAILABLE:
            return self._fallback_chunk(context)

        # Tokenize (simplified - in practice use proper tokenizer)
        tokens = context.split()
        if len(tokens) < self.min_chunk_size:
            return [context], []

        # Detect boundaries using HP-Quad
        all_boundaries = self._detect_boundaries(tokens)

        # Split at boundaries
        chunks, boundaries = self._split_at_boundaries(context, tokens, all_boundaries)

        return chunks, boundaries

    def _detect_boundaries(self, tokens: List[str]) -> List[int]:
        """Detect boundaries using HP-Quad boundary detector."""
        all_boundaries = []
        window_size = 512  # Process in windows

        for start in range(0, len(tokens), window_size // 2):
            end = min(start + window_size, len(tokens))
            window_text = " ".join(tokens[start:end])

            # Simple encoding (in practice, use proper tokenizer)
            x = torch.randn(1, end - start, self.hp_quad.d_model)
            x = x.to(next(self.hp_quad.parameters()).device)

            with torch.no_grad():
                _, _, aux = self.hp_quad(x)

            if "boundary_positions" in aux:
                boundaries = aux["boundary_positions"].squeeze()
                if boundaries.dim() == 0:
                    boundaries = boundaries.unsqueeze(0)

                boundary_indices = (boundaries > self.boundary_threshold).nonzero()

                for idx in boundary_indices:
                    global_idx = start + idx.item()
                    if global_idx not in all_boundaries:
                        all_boundaries.append(global_idx)

        return sorted(all_boundaries)

    def _split_at_boundaries(
        self,
        context: str,
        tokens: List[str],
        boundaries: List[int],
    ) -> Tuple[List[str], List[int]]:
        """Split text at boundary positions."""
        # Filter boundaries by min/max chunk size
        filtered = self._filter_boundaries(boundaries, len(tokens))

        chunks = []
        prev = 0

        for boundary in filtered:
            chunk_tokens = tokens[prev:boundary]
            chunks.append(" ".join(chunk_tokens))
            prev = boundary

        # Add final chunk
        if prev < len(tokens):
            chunks.append(" ".join(tokens[prev:]))

        return chunks, filtered

    def _filter_boundaries(
        self,
        boundaries: List[int],
        total_len: int,
    ) -> List[int]:
        """Filter boundaries to respect min/max chunk size."""
        filtered = []
        prev = 0

        for boundary in boundaries:
            chunk_size = boundary - prev

            if chunk_size < self.min_chunk_size:
                continue

            if chunk_size > self.max_chunk_size:
                # Force splits at max intervals
                while prev + self.max_chunk_size < boundary:
                    filtered.append(prev + self.max_chunk_size)
                    prev = prev + self.max_chunk_size

            filtered.append(boundary)
            prev = boundary

        return filtered

    def _fallback_chunk(self, context: str) -> Tuple[List[str], List[int]]:
        """Fallback chunking when HP-Quad not available."""
        # Split by paragraphs first
        paragraphs = context.split("\n\n")

        chunks = []
        boundaries = []
        current_chunk = ""
        current_pos = 0

        for para in paragraphs:
            if len(current_chunk) + len(para) > self.max_chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    boundaries.append(current_pos)
                current_chunk = para
                current_pos += len(para) + 2
            else:
                current_chunk += "\n\n" + para if current_chunk else para
                current_pos += len(para) + 2

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks, boundaries


class MemoryBankSynchronizer:
    """
    Synchronizes REPL variables with Quad Proposal memory banks.
    """

    def __init__(
        self,
        d_model: int = 512,
        num_levels: int = 3,
        max_memories_per_level: Tuple[int, ...] = (1000, 500, 100),
        device: str = "cuda",
    ):
        self.d_model = d_model
        self.num_levels = num_levels
        self.max_memories = max_memories_per_level
        self.device = device

        # Memory banks
        self.memory_banks: List[List[Tensor]] = [[] for _ in range(num_levels)]
        self.memory_texts: List[List[str]] = [[] for _ in range(num_levels)]

    def sync_from_repl(self, repl_env: REPLEnvironment):
        """Export REPL variables to memory banks."""
        # Level 0: Key facts (fine-grained)
        for fact in repl_env.key_facts:
            self._add_memory(0, fact)

        # Level 1: Sub-query results (medium-grained)
        for chunk_id, result in repl_env.sub_results.items():
            if isinstance(result, str):
                self._add_memory(1, result)

        # Level 2: Search summaries (coarse-grained)
        for query, results in repl_env.search_cache.items():
            summary = f"Search '{query}': {len(results)} matches"
            self._add_memory(2, summary)

    def _add_memory(self, level: int, text: str):
        """Add a memory to the specified level."""
        if level >= self.num_levels:
            return

        if len(self.memory_banks[level]) >= self.max_memories[level]:
            # FIFO eviction
            self.memory_banks[level].pop(0)
            self.memory_texts[level].pop(0)

        # Simple encoding (in practice, use proper encoder)
        embedding = torch.randn(1, self.d_model, device=self.device)

        self.memory_banks[level].append(embedding)
        self.memory_texts[level].append(text)

    def get_memory_banks(self) -> List[Optional[Tensor]]:
        """Get memory banks formatted for Quad Proposal."""
        banks = []
        for level in range(self.num_levels):
            if self.memory_banks[level]:
                stacked = torch.cat(self.memory_banks[level], dim=0)
                banks.append(stacked.unsqueeze(0))
            else:
                banks.append(None)
        return banks

    def clear(self):
        """Clear all memory banks."""
        self.memory_banks = [[] for _ in range(self.num_levels)]
        self.memory_texts = [[] for _ in range(self.num_levels)]


class QualityAwareRecursionController:
    """
    Controls RLM recursion based on Reflective quality scores.
    """

    def __init__(
        self,
        quality_threshold: float = 0.7,
        max_recursion_depth: int = 5,
        decomposition_strategies: List[str] = None,
    ):
        self.quality_threshold = quality_threshold
        self.max_depth = max_recursion_depth
        self.strategies = decomposition_strategies or ["semantic", "fixed", "overlap"]

    def should_recurse_deeper(
        self,
        quality_score: float,
        current_depth: int,
        current_strategy_idx: int,
    ) -> Tuple[bool, Optional[str]]:
        """
        Decide whether to recurse deeper or try alternative strategy.

        Returns:
            should_recurse: Whether to continue
            next_action: "deeper" | "alternative" | "human_review" | None
        """
        if quality_score >= self.quality_threshold:
            return False, None

        if current_depth >= self.max_depth:
            if current_strategy_idx + 1 < len(self.strategies):
                return True, "alternative"
            else:
                return True, "human_review"

        return True, "deeper"

    def get_decomposition_fn(
        self,
        strategy_name: str,
        chunk_size: int = 1000,
    ) -> Callable[[str], List[str]]:
        """Get a decomposition function by name."""
        if strategy_name == "semantic":
            return self._semantic_split
        elif strategy_name == "fixed":
            return lambda ctx: self._fixed_split(ctx, chunk_size)
        elif strategy_name == "overlap":
            return lambda ctx: self._overlap_split(ctx, chunk_size)
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")

    def _semantic_split(self, context: str) -> List[str]:
        """Split by paragraphs/sentences."""
        paragraphs = context.split("\n\n")
        return [p.strip() for p in paragraphs if p.strip()]

    def _fixed_split(self, context: str, size: int) -> List[str]:
        """Fixed-size splitting."""
        words = context.split()
        return [
            " ".join(words[i:i+size])
            for i in range(0, len(words), size)
        ]

    def _overlap_split(self, context: str, size: int) -> List[str]:
        """Overlapping splits (50% overlap)."""
        words = context.split()
        step = size // 2
        return [
            " ".join(words[i:i+size])
            for i in range(0, len(words), step)
            if i + size // 2 <= len(words)
        ]


class RLMPhaseQuadSystem:
    """
    Complete integrated system combining RLM orchestration with Phase-Quad processing.

    Usage:
        system = RLMPhaseQuadSystem(config)
        answer = system.query(context, question)
    """

    def __init__(self, config: RLMPhaseQuadConfig):
        self.config = config

        # Initialize HP-Quad
        if HP_QUAD_AVAILABLE:
            self.hp_quad = HPQuadBlock(
                d_model=config.d_model,
                d_phase_levels=config.d_phase_levels,
                num_levels=config.num_levels,
                chunk_sizes=config.chunk_sizes,
                boundary_threshold=config.boundary_threshold,
            ).to(config.device)
        else:
            self.hp_quad = None

        # Initialize components
        self.chunker = BoundaryAwareChunker(
            hp_quad=self.hp_quad,
            min_chunk_size=config.min_chunk_size,
            max_chunk_size=config.max_chunk_size,
            boundary_threshold=config.boundary_threshold,
        )

        self.state_manager = PhaseStateManager(
            d_phase_levels=config.d_phase_levels,
            max_branches=config.max_branches,
            device=config.device,
        )

        self.memory_sync = MemoryBankSynchronizer(
            d_model=config.d_model,
            num_levels=config.num_levels,
            max_memories_per_level=config.max_memories_per_level,
            device=config.device,
        )

        self.recursion_controller = QualityAwareRecursionController(
            quality_threshold=config.quality_threshold,
            max_recursion_depth=config.max_recursion_depth,
            decomposition_strategies=config.decomposition_strategies,
        )

        # REPL environment
        self.env = REPLEnvironment()

    def query(
        self,
        context: str,
        question: str,
        return_trace: bool = False,
    ) -> Union[str, Tuple[str, Dict]]:
        """
        Process a query over potentially unlimited context.

        Args:
            context: Input context (can be 10M+ tokens)
            question: User's question
            return_trace: Whether to return execution trace

        Returns:
            answer: Final answer string
            trace: (optional) Execution trace for debugging
        """
        trace = {
            "chunks": [],
            "sub_queries": [],
            "quality_scores": {},
            "recursion_depth": 0,
            "total_time": 0,
        }

        start_time = time.perf_counter()

        # Step 1: Load context
        self.env.clear()
        self.state_manager.clear()
        self.memory_sync.clear()
        self.env.context = context

        # Step 2: Smart chunking
        chunks, boundaries = self.chunker.chunk(context)
        self.env.chunks = chunks
        self.env.chunk_boundaries = boundaries
        trace["chunks"] = [c[:100] + "..." if len(c) > 100 else c for c in chunks]

        # Step 3: Process each chunk
        for i, chunk in enumerate(chunks):
            chunk_id = f"chunk_{i}"

            result, quality = self._process_sub_query(
                chunk=chunk,
                question=question,
                branch_id=chunk_id,
                depth=0,
            )

            self.env.sub_results[chunk_id] = result
            self.env.quality_scores[chunk_id] = quality
            trace["sub_queries"].append(chunk_id)

        # Step 4: Sync to memory banks
        self.memory_sync.sync_from_repl(self.env)

        # Step 5: Synthesize answer
        answer = self._synthesize(question)

        trace["quality_scores"] = dict(self.env.quality_scores)
        trace["total_time"] = time.perf_counter() - start_time

        if return_trace:
            return answer, trace
        return answer

    def _process_sub_query(
        self,
        chunk: str,
        question: str,
        branch_id: str,
        depth: int,
    ) -> Tuple[str, float]:
        """
        Process a single sub-query with Phase-Quad.

        Returns:
            result: Sub-query result
            quality: Quality score
        """
        # Get phase state
        phase_state = self.state_manager.get_state(branch_id)

        # Process with Phase-Quad (or fallback)
        if self.hp_quad is not None:
            result, new_state, quality = self._phase_quad_process(
                chunk, question, phase_state
            )
            self.state_manager.update_state(branch_id, new_state)
        else:
            # Fallback: simple extraction
            result = self._fallback_process(chunk, question)
            quality = 0.5  # Unknown quality

        # Check if we need to recurse deeper
        should_recurse, action = self.recursion_controller.should_recurse_deeper(
            quality, depth, 0
        )

        if should_recurse and action == "deeper" and depth < self.config.max_recursion_depth:
            # Split chunk further and recurse
            sub_chunks = self.recursion_controller.get_decomposition_fn("fixed", 500)(chunk)

            sub_results = []
            for j, sub_chunk in enumerate(sub_chunks):
                sub_id = f"{branch_id}_sub_{j}"
                self.state_manager.create_child_branch(branch_id, sub_id)

                sub_result, sub_quality = self._process_sub_query(
                    sub_chunk, question, sub_id, depth + 1
                )
                sub_results.append(sub_result)

            # Combine sub-results
            result = " ".join(sub_results)
            quality = sum(self.env.quality_scores.get(f"{branch_id}_sub_{j}", 0.5)
                         for j in range(len(sub_chunks))) / len(sub_chunks)

        return result, quality

    def _phase_quad_process(
        self,
        chunk: str,
        question: str,
        phase_state: Optional[List[Tensor]],
    ) -> Tuple[str, List[Tensor], float]:
        """Process with Phase-Quad model."""
        # Simple encoding (in practice, use proper tokenizer)
        seq_len = min(len(chunk.split()), 512)
        x = torch.randn(1, seq_len, self.config.d_model, device=self.config.device)

        with torch.no_grad():
            output, new_state, aux = self.hp_quad(
                x,
                phase_states=phase_state,
                memory_banks=self.memory_sync.get_memory_banks(),
            )

        # Simulate quality score (in practice, use Reflective critic)
        quality = 0.7 + 0.2 * torch.rand(1).item()

        # Simple result generation (placeholder)
        result = f"[Processed chunk with {seq_len} tokens for query: {question[:50]}...]"

        return result, new_state, quality

    def _fallback_process(self, chunk: str, question: str) -> str:
        """Fallback processing when Phase-Quad not available."""
        # Simple keyword extraction
        keywords = question.lower().split()
        relevant = []

        for sentence in chunk.split("."):
            if any(kw in sentence.lower() for kw in keywords):
                relevant.append(sentence.strip())

        if relevant:
            return ". ".join(relevant[:3])
        return f"[No relevant content found for: {question[:30]}...]"

    def _synthesize(self, question: str) -> str:
        """Synthesize final answer from sub-results."""
        results = self.env.sub_results

        if not results:
            return "No results found."

        # Combine all results
        all_results = "\n".join([
            f"[{k}]: {v}" for k, v in results.items()
        ])

        # In practice, would use the model for synthesis
        # Here we just concatenate
        synthesis = f"Based on {len(results)} analyzed chunks:\n\n{all_results}"

        return synthesis

    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics."""
        return {
            "num_chunks": len(self.env.chunks),
            "num_sub_results": len(self.env.sub_results),
            "avg_quality": sum(self.env.quality_scores.values()) / max(len(self.env.quality_scores), 1),
            "num_phase_states": len(self.state_manager.states),
            "memory_bank_sizes": [len(bank) for bank in self.memory_sync.memory_banks],
        }


class RLMPhaseQuadBenchmark:
    """
    Benchmark suite for RLM-Phase-Quad integration.
    """

    def __init__(self, config: RLMPhaseQuadConfig):
        self.config = config
        self.system = RLMPhaseQuadSystem(config)

    def run_all(self) -> Dict[str, Any]:
        """Run all benchmarks."""
        results = {}

        results["throughput"] = self.benchmark_throughput()
        results["chunking"] = self.benchmark_chunking()
        results["state_persistence"] = self.benchmark_state_persistence()
        results["scalability"] = self.benchmark_scalability()

        return results

    def benchmark_throughput(self) -> Dict[str, float]:
        """Measure tokens processed per second."""
        results = {}

        for context_size in [1000, 10000, 100000]:
            context = "word " * context_size
            question = "Summarize the content"

            start = time.perf_counter()
            _, trace = self.system.query(context, question, return_trace=True)
            elapsed = time.perf_counter() - start

            results[f"size_{context_size}"] = {
                "tokens": context_size,
                "time_sec": elapsed,
                "tokens_per_sec": context_size / elapsed,
                "num_chunks": len(trace["chunks"]),
            }

        return results

    def benchmark_chunking(self) -> Dict[str, Any]:
        """Measure chunking quality."""
        # Test with structured content
        context = "\n\n".join([
            f"Section {i}: " + "content " * 100
            for i in range(10)
        ])

        chunks, boundaries = self.system.chunker.chunk(context)

        return {
            "num_chunks": len(chunks),
            "num_boundaries": len(boundaries),
            "avg_chunk_size": sum(len(c.split()) for c in chunks) / max(len(chunks), 1),
            "min_chunk_size": min(len(c.split()) for c in chunks) if chunks else 0,
            "max_chunk_size": max(len(c.split()) for c in chunks) if chunks else 0,
        }

    def benchmark_state_persistence(self) -> Dict[str, Any]:
        """Measure Phase State persistence effectiveness."""
        self.system.state_manager.clear()

        # Create multiple branches
        for i in range(10):
            _ = self.system.state_manager.get_state(f"branch_{i}")

        # Create child branches
        for i in range(5):
            self.system.state_manager.create_child_branch(f"branch_{i}", f"branch_{i}_child")
            _ = self.system.state_manager.get_state(f"branch_{i}_child")

        # Merge siblings
        merged = self.system.state_manager.merge_sibling_states(
            [f"branch_{i}" for i in range(5)]
        )

        return {
            "total_states": len(self.system.state_manager.states),
            "branch_tree_size": len(self.system.state_manager.branch_tree),
            "merge_successful": merged is not None,
        }

    def benchmark_scalability(self) -> Dict[str, Any]:
        """Measure scalability with increasing context."""
        results = {}

        for multiplier in [1, 2, 5, 10]:
            context_size = 10000 * multiplier
            context = "test content " * context_size

            start = time.perf_counter()
            answer, trace = self.system.query(context, "Summarize", return_trace=True)
            elapsed = time.perf_counter() - start

            results[f"multiplier_{multiplier}"] = {
                "context_size": context_size,
                "time_sec": elapsed,
                "num_chunks": len(trace["chunks"]),
                "num_sub_queries": len(trace["sub_queries"]),
            }

        return results


def create_rlm_phase_quad(
    config: Optional[RLMPhaseQuadConfig] = None,
) -> RLMPhaseQuadSystem:
    """Factory function to create RLM-Phase-Quad system."""
    if config is None:
        config = RLMPhaseQuadConfig()
    return RLMPhaseQuadSystem(config)
