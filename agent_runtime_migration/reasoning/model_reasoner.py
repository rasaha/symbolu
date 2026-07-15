"""Model reasoner — advisory reflection TEXT only. The reflection DECISION stays
deterministic (from the governed outcome); the model may add rationale, never a
governance decision."""
from __future__ import annotations
from typing import Optional
from ..contracts.observation import Observation
from ..model.interface import LanguageModel
from .reflection import Reflection, Reflector

REFLECT_TEMPLATE = ("Summarize (one sentence) what to note about this outcome. "
                    "Do not decide authorization. Outcome: {outcome}. Governance: {gov}")


class ModelReasoner:
    def __init__(self, model: Optional[LanguageModel] = None, reflector: Optional[Reflector] = None):
        self._model = model
        self._reflector = reflector or Reflector()

    def reflect(self, observation: Observation) -> Reflection:
        base = self._reflector.reflect(observation)   # DETERMINISTIC decision
        if self._model is None:
            return base
        try:
            note = self._model.generate(REFLECT_TEMPLATE.format(
                outcome=observation.outcome, gov=observation.governance)).strip()
        except Exception:  # noqa: BLE001 - advisory text is best-effort, never gates
            note = ""
        # advisory rationale appended; decision unchanged
        return Reflection(decision=base.decision,
                          rationale=(base.rationale + (f" | model: {note[:120]}" if note else "")))
