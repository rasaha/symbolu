"""
Ontology Runtime Safety Validators (O2)
========================================

Portable, runtime-safe validation functions extracted from the ontological
projection engine's validator layer.

These functions enforce structural safety invariants without depending on
projection-specific types. They are suitable for use in governance,
framework adapters, CI pipelines, and any runtime context that needs to
verify deterministic safety constraints.

Canonical source: agentic.ontology.safety
Origin: agentic.ontology.projection.validators (projection-specific
        functions remain there; only the portable subset is here)

Hard Constraints:
    - Pure functions (no side effects)
    - Deterministic (same input => identical output)
    - No external dependencies beyond sys
    - Fail-closed semantics (violations are explicit, never silent)
"""

from __future__ import annotations

import sys
from typing import List, Tuple


# =========================================================================
# Forbidden Module Registry
# =========================================================================

FORBIDDEN_MODULES: Tuple[str, ...] = (
    "nltk",
    "spacy",
    "transformers",
    "openai",
    "anthropic",
    "langchain",
    "gensim",
    "textblob",
)
"""
NLP and LLM client libraries that must never be imported in
deterministic ontology paths. These introduce non-determinism,
semantic processing, or external network dependencies.
"""

TIMESTAMP_WORDS: Tuple[str, ...] = (
    "timestamp",
    "time.time",
    "datetime.now",
    "uuid",
)
"""
Words that indicate non-deterministic time/identity injection.
Their presence in a repr() signals potential replay instability.
"""


# =========================================================================
# Runtime Safety Checks
# =========================================================================

def check_no_forbidden_modules() -> Tuple[bool, List[str]]:
    """
    Check that no forbidden NLP/LLM modules are currently imported.

    Scans ``sys.modules`` for any module whose name matches or is a
    subpackage of a forbidden module. This is a runtime invariant check,
    not a static analysis — it detects modules that have actually been
    loaded into the current process.

    Returns:
        Tuple of (passed, violations) where:
        - passed: True if no forbidden modules are imported
        - violations: List of forbidden module names found in sys.modules

    Example:
        >>> passed, violations = check_no_forbidden_modules()
        >>> if not passed:
        ...     raise RuntimeError(f"Forbidden modules loaded: {violations}")
    """
    violations = []
    for module_name in sys.modules:
        for forbidden in FORBIDDEN_MODULES:
            if module_name == forbidden or module_name.startswith(forbidden + "."):
                violations.append(module_name)
    return (len(violations) == 0, violations)


def check_no_timestamp_words(obj: object) -> Tuple[bool, List[str]]:
    """
    Check that no timestamp-related words appear in an object's repr.

    This detects accidental injection of non-deterministic time/identity
    values into data structures that should be replay-stable.

    Args:
        obj: Any object whose repr() will be scanned.

    Returns:
        Tuple of (passed, violations) where:
        - passed: True if no timestamp words are found
        - violations: List of timestamp words found in repr(obj)

    Example:
        >>> from dataclasses import dataclass
        >>> @dataclass
        ... class Record:
        ...     value: str
        >>> check_no_timestamp_words(Record(value="clean"))
        (True, [])
    """
    violations = []
    obj_repr = repr(obj).lower()
    for word in TIMESTAMP_WORDS:
        if word.lower() in obj_repr:
            violations.append(word)
    return (len(violations) == 0, violations)
