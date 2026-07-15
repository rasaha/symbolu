"""Capture real-model responses to a sanitized replay fixture (for reproducibility).

Records (prompt -> response) pairs. Credentials never appear in prompts/responses, so
the fixture is safe to commit; a guard additionally refuses to write anything matching
a credential-like pattern. A captured fixture reloads as a deterministic ReplayModel.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List

from .interface import LanguageModel
from .replay import ReplayModel

_SECRET_RE = re.compile(r"(sk-[A-Za-z0-9]{16,})|(Bearer\s+[A-Za-z0-9._-]{16,})|(x-api-key)",
                        re.IGNORECASE)


class CaptureRecorder:
    """Wrap a model; record each call. ``model`` is the real adapter."""

    def __init__(self, model: LanguageModel):
        self._model = model
        self.records: List[Dict[str, str]] = []

    def generate(self, prompt: str) -> str:
        out = self._model.generate(prompt)
        if _SECRET_RE.search(prompt) or _SECRET_RE.search(out):
            raise ValueError("refusing to capture: credential-like material in prompt/response")
        self.records.append({"prompt": prompt, "response": out})
        return out

    call = generate

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"note": "sanitized captured real-model responses (no credentials)",
                       "records": self.records}, fh, indent=2)


def replay_from_capture(path: str) -> ReplayModel:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    responses = {r["prompt"]: r["response"] for r in data.get("records", [])}
    return ReplayModel(responses, match="exact", name="captured-replay")
