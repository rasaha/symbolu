"""Ugence CM-TA1 integration — Context Minimization × Token Accounting × Agent Runtime.

A narrowly-scoped, one-way composition layer. It imports BOTH independent cores
(`ugence-context-minimization` and `ugence-agent-runtime`); neither imports this
package, and both remain stdlib-only leaves.

Responsibilities:

* Translate a neutral Agent Runtime :class:`ProviderAttempt` into a Context
  Minimization :class:`ApiCallTokenRecord` via an **injected**, provider-specific
  usage normalizer (this package ships only a mechanical `MappingUsageNormalizer`; a
  real vendor SDK normalizer lives outside).
* Record every attempt — including retries and failures — through the CM
  `TokenAccountingSink`, preserving unknown-is-not-zero and the deterministic
  idempotent-replay contract.
* Feed authoritative provider-reported usage into the existing H22-D budget
  settlement seam, preserving conservative full-reservation settlement when usage is
  unavailable and surfacing `BudgetEstimateExceeded` rather than clamping an overrun.

The base install carries NO concrete OpenAI/Anthropic/Google SDK.
"""

from __future__ import annotations

from .bridge import (
    DEFAULT_TOKEN_DIMENSION,
    BudgetEstimateExceeded,
    RuntimeTokenAccountingBridge,
    settle_budget_from_summary,
    settle_budget_from_usage,
    token_units_from_usage,
)
from .translation import (
    MappingUsageNormalizer,
    UsageNormalizer,
    derive_attempt_id,
    translate_attempt,
)
from .version import VERSION, __version__

__all__ = [
    "__version__",
    "VERSION",
    # translation
    "UsageNormalizer",
    "MappingUsageNormalizer",
    "translate_attempt",
    "derive_attempt_id",
    # runtime bridge + budget settlement
    "RuntimeTokenAccountingBridge",
    "settle_budget_from_usage",
    "settle_budget_from_summary",
    "token_units_from_usage",
    "BudgetEstimateExceeded",
    "DEFAULT_TOKEN_DIMENSION",
]
