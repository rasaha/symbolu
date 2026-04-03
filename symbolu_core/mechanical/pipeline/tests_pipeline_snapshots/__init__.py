"""
Pipeline End-to-End Snapshot Tests Package
============================================

Contains snapshot tests for the complete Symbol-U pipeline flow:
    UserRequest -> Persona -> MLCR -> Fusion -> DHA -> Renderer -> RenderedOutput

Test Modules:
    - test_pipeline_snapshots.py: Single-turn tests for all 4 render modes
    - test_pipeline_multiturn_snapshots.py: Multi-turn conversation snapshot test

These tests are LLM-free and fully deterministic.
"""
