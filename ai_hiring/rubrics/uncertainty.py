"""Uncertainty contracts — extracted to the DGM kernel in Phase 5A.

``UncertaintyLevel`` and ``UncertaintyRule`` are domain-neutral governance
vocabulary; they now live in ``decision_governance.vocabulary`` and are re-exported
here so the historical ``ai_hiring.rubrics.uncertainty`` import path is unchanged.
"""

from __future__ import annotations

from decision_governance.vocabulary import (  # noqa: F401
    UncertaintyLevel,
    UncertaintyRule,
)
