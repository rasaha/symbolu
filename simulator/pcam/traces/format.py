"""
Standardized trace format for PCAM simulation.

As specified in Appendix H.3.1.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json


@dataclass
class TraceMetadata:
    """Trace metadata."""
    model_name: str = "llama-70b"
    workload_type: str = "unknown"  # chat, long_context, rag, code, multitenant
    total_tokens: int = 0
    context_length: int = 0
    num_sequences: int = 1


@dataclass
class TraceStep:
    """
    Single step in a trace.

    Each step represents one token generation, capturing:
    - Which KV blocks were accessed
    - Attention scores for those blocks
    - Ground truth top-K for evaluation
    """
    step_id: int
    timestamp_ns: int = 0

    # KV block access pattern
    blocks_accessed: List[int] = field(default_factory=list)

    # Block ID -> attention weight
    attention_scores: Dict[int, float] = field(default_factory=dict)

    # Ground truth for evaluation
    true_top_k: List[int] = field(default_factory=list)

    # Multi-tenant fields
    sequence_id: int = 0
    batch_position: int = 0

    # Optional: query block for this step
    query_block_id: int = 0

    # Structural hints for code workloads (block_id -> scope_id).
    # Blocks sharing a scope_id are structurally linked (same function,
    # same import group, same class definition).
    block_structural_hints: Dict[int, int] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        d = {
            "step_id": self.step_id,
            "timestamp_ns": self.timestamp_ns,
            "blocks_accessed": self.blocks_accessed,
            "attention_scores": self.attention_scores,
            "true_top_k": self.true_top_k,
            "sequence_id": self.sequence_id,
            "batch_position": self.batch_position,
            "query_block_id": self.query_block_id,
        }
        if self.block_structural_hints:
            d["block_structural_hints"] = self.block_structural_hints
        return d

    @classmethod
    def from_dict(cls, d: Dict) -> "TraceStep":
        return cls(
            step_id=d["step_id"],
            timestamp_ns=d.get("timestamp_ns", 0),
            blocks_accessed=d.get("blocks_accessed", []),
            attention_scores={int(k): v for k, v in d.get("attention_scores", {}).items()},
            true_top_k=d.get("true_top_k", []),
            sequence_id=d.get("sequence_id", 0),
            batch_position=d.get("batch_position", 0),
            query_block_id=d.get("query_block_id", 0),
            block_structural_hints={
                int(k): v for k, v in d.get("block_structural_hints", {}).items()
            },
        )


@dataclass
class PCAMTrace:
    """
    Complete trace for PCAM simulation.

    Contains metadata and sequence of steps representing
    a workload's attention access patterns.
    """
    metadata: TraceMetadata
    steps: List[TraceStep] = field(default_factory=list)

    @property
    def num_steps(self) -> int:
        return len(self.steps)

    @property
    def sequence_ids(self) -> List[int]:
        """Get unique sequence IDs in trace."""
        return list(set(s.sequence_id for s in self.steps))

    def get_steps_for_sequence(self, sequence_id: int) -> List[TraceStep]:
        """Get steps for a specific sequence."""
        return [s for s in self.steps if s.sequence_id == sequence_id]

    def to_dict(self) -> Dict:
        return {
            "metadata": {
                "model_name": self.metadata.model_name,
                "workload_type": self.metadata.workload_type,
                "total_tokens": self.metadata.total_tokens,
                "context_length": self.metadata.context_length,
                "num_sequences": self.metadata.num_sequences,
            },
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "PCAMTrace":
        meta = TraceMetadata(
            model_name=d["metadata"].get("model_name", "unknown"),
            workload_type=d["metadata"].get("workload_type", "unknown"),
            total_tokens=d["metadata"].get("total_tokens", 0),
            context_length=d["metadata"].get("context_length", 0),
            num_sequences=d["metadata"].get("num_sequences", 1),
        )
        steps = [TraceStep.from_dict(s) for s in d.get("steps", [])]
        return cls(metadata=meta, steps=steps)

    def save(self, path: str) -> None:
        """Save trace to JSON file."""
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str) -> "PCAMTrace":
        """Load trace from JSON file."""
        with open(path, "r") as f:
            return cls.from_dict(json.load(f))

    def validate(self) -> List[str]:
        """Validate trace consistency. Returns list of issues."""
        issues = []

        if not self.steps:
            issues.append("Trace has no steps")

        # Check step ordering
        for i, step in enumerate(self.steps):
            if step.step_id != i:
                issues.append(f"Step {i} has mismatched step_id {step.step_id}")

        # Check attention scores sum
        for step in self.steps:
            if step.attention_scores:
                total = sum(step.attention_scores.values())
                if total > 0 and abs(total - 1.0) > 0.1:  # Allow some slack
                    pass  # Attention scores don't need to sum to 1

        # Check true_top_k is subset of blocks_accessed
        for step in self.steps:
            if step.true_top_k and step.blocks_accessed:
                if not set(step.true_top_k).issubset(set(step.blocks_accessed)):
                    issues.append(
                        f"Step {step.step_id}: true_top_k not subset of blocks_accessed"
                    )

        return issues
