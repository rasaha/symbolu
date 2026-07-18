"""Stage A — Structural testbed for Symbol-U (STRUCTURAL_V1).

Scope (binding, from the authorization checklist):
  Stage A tests whether a *feature-grounded operator product* produces
  inventory-specific, factorizable, order-dependent STRUCTURE that beats three
  nulls (bag, random-orthogonal, relabel). It is a structural / expressiveness
  result ONLY.

  A Stage A PASS does NOT establish:
    - meaning,
    - Sanskrit / varna privilege,
    - LLM or policy usefulness.

  Every artifact this package emits is labeled "structure, not validated meaning."

Hard boundaries enforced by tests/test_import_ban.py:
  - No import of llm, judge, policy, policy_v4, symbolu_state.
  - No network / API / HTTP client.
  - No LLM, policy translation, human-study, cross-modal, or Sanskrit-comparison code.

This package is self-contained: it embeds its own static phonological feature
chart (features.py) and depends only on numpy.
"""

STRUCTURE_LABEL = "structure, not validated meaning"
