"""
Stitch Ranker
==============

Ranks results based on stitching scores.
DELEGATES scoring to core.stitching.
"""

from typing import List, Dict, Any
from symbolu.core.stitching.stitching_engine import StitchingEngine


class StitchRanker:
    """
    Ranks results by stitch compatibility.
    
    DELEGATES all scoring to StitchingEngine.
    """
    
    def __init__(self):
        self._engine = StitchingEngine()
    
    def rank(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Rank results by stitch score.
        
        Lower stitch score (gap) = better match.
        """
        # Would compute scores via core engine
        # For now, return as-is since core raises NotImplementedError
        return sorted(
            results,
            key=lambda x: x.get("stitch_score", float("inf"))
        )
