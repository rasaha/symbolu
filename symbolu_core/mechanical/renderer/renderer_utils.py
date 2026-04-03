"""
Renderer Utilities
===================

Utility functions for renderers.
"""

from typing import Dict, Any, List


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to maximum length."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def format_smi_level(smi: float) -> str:
    """Format SMI value with level indicator."""
    if smi < 0.3:
        return f"{smi:.2f} (LOW)"
    elif smi < 0.6:
        return f"{smi:.2f} (MODERATE)"
    else:
        return f"{smi:.2f} (HIGH)"


def merge_recommendations(recs: List[str]) -> List[str]:
    """Merge and deduplicate recommendations."""
    seen = set()
    unique = []
    for r in recs:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique
