"""Ingest a governed/local result -> observation -> memory. The observation-return loop."""
from __future__ import annotations
from ..contracts.observation import Observation
from ..contracts.result import ExecutionResult
from ..memory.episodic_memory import EpisodicMemory
from .adapter import to_observation
from .memory_update import update_memory


def ingest(result: ExecutionResult, memory: EpisodicMemory) -> Observation:
    obs = to_observation(result)
    update_memory(memory, obs)
    return obs
