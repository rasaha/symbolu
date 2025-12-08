"""
Prompt Templates
=================

Templates for LLM enhancement prompts.
"""

from typing import Dict, Any, Optional


class PromptTemplates:
    """Templates for LLM prompts."""
    
    ENHANCEMENT_TEMPLATE = """
You are a writing stylist. Your job is to polish the presentation of 
analysis results WITHOUT changing any of the core findings.

CORE ANALYSIS (DO NOT MODIFY):
{analysis}

TONE: {tone}

Polish this for clear, warm communication. Preserve all SMI values,
Kosha distributions, and recommendations exactly as given.

OUTPUT:
"""
    
    def build_enhancement_prompt(
        self,
        analysis: Dict[str, Any],
        tone: Optional[str] = None
    ) -> str:
        """Build enhancement prompt from analysis."""
        return self.ENHANCEMENT_TEMPLATE.format(
            analysis=str(analysis),
            tone=tone or "SWEET_RESONANCE"
        )
