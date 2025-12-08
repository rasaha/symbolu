"""
Text Cleaning
==============

Utilities for cleaning text.
"""

import re


def clean_text(text: str) -> str:
    """
    Clean text for processing.
    
    - Normalize whitespace
    - Remove excessive newlines
    - Strip leading/trailing whitespace
    """
    # Normalize whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Normalize newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Strip
    text = text.strip()
    
    return text
