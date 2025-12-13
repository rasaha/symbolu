"""
SMI Engine - Semantic Mismatch Index Computation
================================================

PATENT NOTICE: Symbol-U formula to be added later.

ARCHITECTURAL NOTE:
    This module contains foundational stubs for future acoustic realization
    layers. It does NOT participate in live cognition. This component is:

    - Not implemented: All methods raise NotImplementedError
    - Deferred: Will be integrated in post-lexical phases (P10+)
    - Non-semantic: When implemented, will never influence intent or meaning

    PO phases and P6-P9 govern meaning and authority.
    Acoustic realization is strictly post-lexical and deferred.

    See: docs/ACOUSTIC_TOKENIZATION_STATUS.md
"""

from typing import Dict, Any
from symbolu.core.models import SMIResult


class SMIEngine:
    """
    Computes Semantic Mismatch Index between inner and outer layers.
    
    SMI = normalized geometric distance between:
    - Inner layer (acoustic/kosha)
    - Outer layer (semantic/ontology)
    """
    
    def __init__(self):
        pass
    
    def compute(self, text: str) -> SMIResult:
        """Compute SMI for text."""
        raise NotImplementedError("Symbol-U formula to be added later.")
    
    def compute_per_word(self, words: list) -> list:
        """Compute SMI for each word."""
        raise NotImplementedError("Symbol-U formula to be added later.")
    
    def get_components(self, text: str) -> Dict[str, float]:
        """Get SMI component breakdown."""
        raise NotImplementedError("Symbol-U formula to be added later.")
