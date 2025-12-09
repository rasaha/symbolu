"""
Transformation Rules
=====================

Rules for transforming content.
"""

from typing import Dict, Any


class TransformationRules:
    """Rules for content transformation."""
    
    def apply(self, structured: Dict[str, Any]) -> Dict[str, Any]:
        """Apply transformation rules."""
        return {
            "header": structured["header"],
            "body": self._transform_body(structured["body"]),
            "recommendations": self._transform_recommendations(structured["recommendations"]),
            "metadata": structured["metadata"]
        }
    
    def _transform_body(self, body: list) -> list:
        return body
    
    def _transform_recommendations(self, recs: list) -> list:
        return [f"• {r}" for r in recs]
