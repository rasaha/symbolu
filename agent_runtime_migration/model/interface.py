"""LanguageModel interface. Compatible with the legacy adapter contract (.call).

The runtime calls ``generate(prompt) -> str``; ``call`` is provided as an alias so
the same adapter can drive the legacy runtime (which calls ``.call(prompt)``).
"""
from __future__ import annotations
from typing import Protocol


class LanguageModel(Protocol):
    def generate(self, prompt: str) -> str: ...
    def call(self, prompt: str) -> str: ...    # legacy-compatible alias
