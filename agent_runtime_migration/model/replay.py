"""Deterministic recorded-model replay adapter.

Maps a prompt to a RECORDED (authored) model response. Deterministic and
reproducible: identical prompt -> identical response. Fails closed on an unknown
prompt unless a default is provided. These fixtures are authored/recorded model
responses — NOT live-model inference; they never claim live-model evidence.
"""
from __future__ import annotations
from typing import Dict, List, Optional


class ReplayModel:
    def __init__(self, responses: Dict[str, str], *, match: str = "contains",
                 default: Optional[str] = None, name: str = "replay"):
        self._responses = dict(responses)
        self._match = match
        self._default = default
        self.name = name
        self.prompt_log: List[str] = []

    def generate(self, prompt: str) -> str:
        self.prompt_log.append(prompt)
        if self._match == "exact":
            if prompt in self._responses:
                return self._responses[prompt]
        else:  # "contains": first key that is a substring of the prompt
            for key, val in self._responses.items():
                if key in prompt:
                    return val
        if self._default is not None:
            return self._default
        raise KeyError(f"ReplayModel: no recorded response for prompt (len={len(prompt)})")

    call = generate  # legacy-compatible alias
