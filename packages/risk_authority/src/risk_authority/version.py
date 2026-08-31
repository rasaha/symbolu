"""Single source of truth for the package version."""

from __future__ import annotations

#: ``0.5.0`` is R-12b: ``RiskDecision`` gains ``evaluated_at``, so the evaluator's stamp
#: travels inside the digest-bound decision snapshot rather than only on an outer field no
#: digest covers. Additive and optional — an existing caller is unaffected — but every
#: decision snapshot minted from this version gains a key, which moves its digest.
__version__ = "0.5.0"
