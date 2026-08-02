"""Public API — the typed governance error taxonomy.

Re-exports every typed error class from the kernel: the ``GovernanceError`` base,
``DomainValidationError``, and the neutral repository + governance-chain families.
Errors deliberately do **not** subclass ``ValueError`` so a domain error raised
inside a validator propagates as-is.

Identity is preserved: ``decision_governance.api.errors.X is
decision_governance.errors.X`` for every family.
"""

from __future__ import annotations

from .. import errors as _errors

# Re-export every public exception class defined by the kernel error module.
_names = sorted(
    name for name in dir(_errors)
    if not name.startswith("_")
    and isinstance(getattr(_errors, name), type)
    and issubclass(getattr(_errors, name), BaseException)
)
globals().update({name: getattr(_errors, name) for name in _names})

__all__ = list(_names)
