"""
Renderer Test Suite
====================

Comprehensive tests for SOULPI Renderer components:
- FusionRenderer (main deterministic renderer)
- RulesRenderer (rule-based renderer)
- LLMRenderer (LLM-enhanced renderer with mocks)

Test Coverage:
- Mode switching (minimal, standard, symbolic, regulated)
- Layer handling (symbolic, practical, mirror-truth)
- Determinism verification
- Regulated mode compliance
- LLM fallback behavior
- Safety guardrails
"""

__version__ = "1.0"
