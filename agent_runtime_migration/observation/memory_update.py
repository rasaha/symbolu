"""Fold an observation into episodic memory (the return path)."""
from __future__ import annotations
from ..contracts.observation import Observation
from ..memory.episodic_memory import EpisodicMemory


def update_memory(memory: EpisodicMemory, observation: Observation) -> None:
    memory.record(observation)
