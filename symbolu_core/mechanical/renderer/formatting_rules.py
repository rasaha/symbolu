"""
Formatting Rules
=================

Final formatting rules.
"""

from typing import Any


class FormattingRules:
    """Final formatting rules."""
    
    def format(self, content: str, **kwargs) -> str:
        """Apply final formatting."""
        # Add borders if requested
        if kwargs.get("borders", False):
            border = "=" * 60
            content = f"{border}\n{content}\n{border}"
        return content
