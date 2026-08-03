"""Uncertainty contracts — extracted to the DGM kernel in Phase 5A.

``UncertaintyLevel`` and ``UncertaintyRule`` are domain-neutral governance
vocabulary; they now live in ``ugence_decision_authority.vocabulary`` and are re-exported
here so the historical ``ugence_ai_hiring.rubrics.uncertainty`` import path is unchanged.
"""

from __future__ import annotations

from ugence_decision_authority.api.vocabulary import (  # noqa: F401
    UncertaintyLevel,
    UncertaintyRule,
)
