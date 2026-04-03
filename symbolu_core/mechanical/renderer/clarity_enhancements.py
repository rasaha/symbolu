"""
Clarity Enhancements
=====================

Improves readability of output.
"""

from typing import Dict, Any


class ClarityEnhancer:
    """Enhances clarity of output."""
    
    def enhance(self, transformed: Dict[str, Any]) -> str:
        """Enhance clarity of transformed content."""
        parts = [
            transformed["header"],
            "",
            "\n".join(transformed["body"]),
            "",
            "Recommendations:",
            "\n".join(transformed["recommendations"])
        ]
        return "\n".join(parts)
