"""
Structure Rules
================

Rules for structuring analysis output.
"""

from typing import Dict, Any, List


class StructureRules:
    """Rules for organizing content structure."""
    
    def apply(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Apply structure rules to analysis."""
        return {
            "header": self._create_header(analysis),
            "body": self._create_body(analysis),
            "recommendations": analysis.get("recommendations", []),
            "metadata": self._extract_metadata(analysis)
        }
    
    def _create_header(self, analysis: Dict[str, Any]) -> str:
        return f"Analysis of: {analysis.get('text', 'Unknown')}"
    
    def _create_body(self, analysis: Dict[str, Any]) -> List[str]:
        return [
            f"Average SMI: {analysis.get('average_smi', 0):.2f}",
            f"Calling: {analysis.get('calling_type', 'Unknown')}",
            f"DHA Tone: {analysis.get('dha_tone', 'SWEET_RESONANCE')}"
        ]
    
    def _extract_metadata(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        return {"words": len(analysis.get("words", []))}
