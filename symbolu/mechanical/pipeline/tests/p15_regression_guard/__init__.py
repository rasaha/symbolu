"""
P15 Regression Guard Test Suite

Tests for the P15 → Phase 16 Regression Guard that enforces the rule:
No phase ≥ 16 may modify, reinterpret, escalate, or override any decision
produced by PO1–P15.

Test Categories:
1. Intent override blocked
2. Regime escalation blocked
3. Discourse act mutation blocked
4. Allowed-action expansion blocked
5. BLOCKED → unblocked forbidden
6. Prediction-based override forbidden
7. Persona-based override forbidden
8. Renderer metadata ignored
9. Determinism: same input → same violations
10. Phase number < 16 → guard inactive

All tests are deterministic with zero false positives.
"""
