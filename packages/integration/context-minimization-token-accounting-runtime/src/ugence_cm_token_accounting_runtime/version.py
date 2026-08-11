"""Single source of truth for the integration package version."""

from __future__ import annotations

# 0.1.0 — CM-TA1 integration. First release: translate a neutral Agent Runtime
# ProviderAttempt into a Context Minimization ApiCallTokenRecord via an injected,
# provider-specific usage normalizer, and settle H22-D budgets from measured usage
# (conservative full-reservation settlement when usage is unavailable; BudgetEstimateExceeded
# surfaced, never clamped). No concrete provider SDK in the base install.
__version__ = "0.1.0"

VERSION = __version__
