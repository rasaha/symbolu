"""
Core Bridge — DEPRECATED
=========================

Phase 0 Cleanup: CoreInterface facade has been removed (all methods were
NotImplementedError stubs). This bridge previously delegated to that dead
facade.

CoreBridge is retained as a deprecation shim so that existing try/except
imports in mechanical/__init__.py do not break. All methods now raise
NotImplementedError with a clear migration message.

Migration path:
- For SMI computation: use symbolu.core.smi.SMIEngine directly
- For analysis: compose from active engines (smi, stitching, coherence, etc.)
"""

import warnings
from typing import Dict, Any, Optional, List

from symbolu.core.models import AnalysisResult


class CoreBridge:
    """
    DEPRECATED: CoreInterface facade has been removed.

    This shim exists only for import compatibility. All methods raise
    NotImplementedError with migration guidance.
    """

    def __init__(self):
        warnings.warn(
            "CoreBridge is deprecated. CoreInterface facade was removed in Phase 0. "
            "Use symbolu.core.smi.SMIEngine or other active engines directly.",
            DeprecationWarning,
            stacklevel=2,
        )

    def analyze(
        self,
        text: str,
        context: Optional[List[str]] = None,
        **kwargs,
    ) -> AnalysisResult:
        """DEPRECATED: Use active engines directly."""
        raise NotImplementedError(
            "CoreBridge.analyze() is deprecated. "
            "Compose from active engines (smi, stitching, coherence, etc.) directly."
        )

    def get_smi(self, text: str) -> List[Dict[str, Any]]:
        """DEPRECATED: Use symbolu.core.smi.SMIEngine.compute() directly."""
        raise NotImplementedError(
            "CoreBridge.get_smi() is deprecated. "
            "Use symbolu.core.smi.SMIEngine directly."
        )
