"""Actor type — who is acting in a governance operation."""

from __future__ import annotations

from enum import Enum


class ActorType(str, Enum):
    """Who is acting. The AI/human/system split is load-bearing across the kernel."""

    AI = "AI"
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"
