"""
Core Bridge
============

Bridge between mechanical layer and Symbol-U core.
Delegates all core computations to CoreInterface.
"""

from typing import Dict, Any, Optional, List
from agentic.core.interface import CoreInterface
from agentic.core.models import AnalysisResult


class CoreBridge:
    """
    Bridge providing mechanical layer access to core intelligence.
    
    All core operations are delegated to CoreInterface.
    """
    
    def __init__(self):
        self._core = CoreInterface()
    
    def analyze(
        self,
        text: str,
        context: Optional[List[str]] = None,
        **kwargs
    ) -> AnalysisResult:
        """
        Analyze text using core intelligence.
        
        Delegates to CoreInterface.analyze_complete()
        """
        return self._core.analyze_complete(text, context, **kwargs)
    
    def get_smi(self, text: str) -> List[Dict[str, Any]]:
        """
        Get SMI results for text.
        
        Delegates to CoreInterface.compute_smi()
        """
        results = self._core.compute_smi(text)
        return [
            {
                "word": r.word,
                "smi": r.smi_value,
                "level": r.level,
                "components": r.components
            }
            for r in results
        ]
