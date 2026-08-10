#!/usr/bin/env python3
"""Structural guard: exactly ONE physical implementation of the Model Selection
product core.

Fails (exit non-zero) if a copied product-core module (``gate``/``policy``/``states``/
``model``/``registry``/``reason_codes`` carrying real logic) reappears in the legacy
``execution_gate`` namespace, or if the canonical package is missing them. The legacy
namespace must remain a logic-free compatibility surface (its ``__init__`` aliases the
canonical modules; its remaining files are the local *research* harness only).

This does NOT police the intentionally-separate research engines under
``model_selection_experiment/`` / ``model_selection_pilot/`` / ``model_selection_reconciliation/``
— those are classified research algorithms with a distinct I/O contract, not copies of
the canonical core (see Project_documentation/repository/docs/migrations/model_selection/RESEARCH_SEPARATION.md).

Run: python scripts/check_model_selection_single_impl.py
"""
from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
CORE = ("gate", "policy", "states", "model", "registry", "reason_codes")
CANON = REPO / "packages" / "capabilities" / "model-selection" / "src" / "ugence_model_selection"
LEGACY = REPO / "execution_gate"
# Real product-core symbols that must live in exactly one place.
CORE_MARKERS = ("class ExecutionGate", "class ExecutableRegistry", "def select(",
                "class EligibilityDecision", "class ReasonCode")


def main() -> int:
    problems: list[str] = []

    # 1) canonical package must contain the core modules with real logic.
    for name in CORE:
        p = CANON / f"{name}.py"
        if not p.exists():
            problems.append(f"canonical core module missing: {p.relative_to(REPO)}")

    # 2) legacy namespace must NOT contain top-level product-core module files.
    for name in CORE:
        p = LEGACY / f"{name}.py"
        if p.exists():
            problems.append(f"copied product-core module reintroduced in legacy namespace: "
                            f"{p.relative_to(REPO)} (must be aliased from the canonical package)")

    # 3) legacy __init__ must be a logic-free compatibility surface (no core class/def).
    init = (LEGACY / "__init__.py").read_text(encoding="utf-8")
    for marker in CORE_MARKERS:
        if marker in init:
            problems.append(f"legacy execution_gate/__init__.py contains product-core logic: {marker!r}")

    if problems:
        print("MODEL SELECTION SINGLE-IMPLEMENTATION CHECK FAILED:")
        for p in problems:
            print("  -", p)
        return 1
    print("Model Selection single-implementation check: PASS "
          "(canonical core present; legacy namespace is a logic-free compatibility surface)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
