#!/usr/bin/env python3
"""Hidden relationship-reasoning corpus (AUDIT-ONLY).

Separate from the frozen visible development corpus. Executable content
(question + documents, opaque ids) is in `corpus.py`; private annotations (gold
graph, governance, expectation, difficulty, capability) are in `annotations.py`
and must never be given to a resolver. Not used for tuning. Reports no resolver
performance.
"""
from .corpus import executable_cases, evidence_for, case_ids
__all__ = ["executable_cases", "evidence_for", "case_ids"]
