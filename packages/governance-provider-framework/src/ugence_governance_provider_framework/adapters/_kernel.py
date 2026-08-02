"""Optional Decision Authority kernel loading for the kernel-bound adapters.

The three adapters in this sub-package translate governance providers onto the
Decision Authority kernel ports. That kernel dependency is **optional**: importing
the adapters — and therefore the aggregated public API
``ugence_governance_provider_framework.api`` — must succeed without Decision
Authority installed. Only *invoking* adapter functionality requires it.

This module centralizes the precise optional-dependency check so every adapter
raises the same actionable error, and so an unrelated import failure is never
mistaken for the optional dependency being absent.
"""

from __future__ import annotations

#: Roots that constitute the optional Decision Authority dependency (the canonical
#: capability and its legacy kernel-facade shim).
_DECISION_AUTHORITY_ROOTS = ("decision_governance", "ugence_decision_authority")

_EXTRA_HINT = (
    "The Governance Provider Framework kernel-bound adapters require the optional "
    "Decision Authority dependency, which is not installed. Install it with:\n"
    '    pip install "ugence-governance-provider-framework[adapters]"'
)


def require_decision_authority():
    """Import and return the optional ``decision_governance.api`` kernel facade.

    Raises :class:`ModuleNotFoundError` with a precise, actionable message **only**
    when the Decision Authority dependency itself is absent. Any other import error
    (a genuinely broken kernel install, an unrelated missing module) propagates
    unchanged — it is never swallowed or mistranslated.
    """
    try:
        import decision_governance.api as _api
    except ModuleNotFoundError as exc:
        if (exc.name or "").split(".")[0] in _DECISION_AUTHORITY_ROOTS:
            raise ModuleNotFoundError(_EXTRA_HINT) from exc
        raise
    return _api
