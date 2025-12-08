"""
Fusion Renderer
================

Combines rule-based and LLM rendering with intelligent routing.
Implements "stylist not thinker" principle.
"""

from typing import Dict, Any, Optional
from symbolu.mechanical.renderer.rules_renderer import RulesRenderer
from symbolu.mechanical.renderer.llm_renderer import LLMRenderer


class FusionRenderer:
    """
    Fusion renderer that intelligently routes between rule-based and LLM rendering.
    
    - Rule-based for deterministic, low-risk outputs
    - LLM for polishing when safety thresholds allow
    - Automatic fallback to rules when LLM fails safety checks
    """
    
    def __init__(self, safety_threshold: float = 0.7):
        self.rules_renderer = RulesRenderer()
        self.llm_renderer = LLMRenderer()
        self.safety_threshold = safety_threshold
    
    def render(
        self,
        analysis: Dict[str, Any],
        mode: str = "auto",
        **kwargs
    ) -> str:
        """
        Render analysis to human-readable output.
        
        Args:
            analysis: Core analysis result
            mode: "rules", "llm", or "auto"
            **kwargs: Additional rendering parameters
            
        Returns:
            Rendered output string
        """
        if mode == "rules":
            return self.rules_renderer.render(analysis, **kwargs)
        elif mode == "llm":
            return self._render_with_fallback(analysis, **kwargs)
        else:  # auto
            return self._auto_route(analysis, **kwargs)
    
    def _auto_route(self, analysis: Dict[str, Any], **kwargs) -> str:
        """Automatically route to appropriate renderer."""
        # Use rules for high-tension or regulated domains
        tension = analysis.get("average_smi", 0.5)
        domain = kwargs.get("domain", "general")
        
        if tension > self.safety_threshold or domain in ["medical", "legal", "financial"]:
            return self.rules_renderer.render(analysis, **kwargs)
        else:
            return self._render_with_fallback(analysis, **kwargs)
    
    def _render_with_fallback(self, analysis: Dict[str, Any], **kwargs) -> str:
        """Render with LLM, fallback to rules on failure."""
        try:
            result = self.llm_renderer.render(analysis, **kwargs)
            if self._passes_safety_check(result):
                return result
        except Exception:
            pass
        return self.rules_renderer.render(analysis, **kwargs)
    
    def _passes_safety_check(self, output: str) -> bool:
        """Check if LLM output passes safety requirements."""
        # Placeholder - implement actual safety checks
        return len(output) > 0 and len(output) < 10000
