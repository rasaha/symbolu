"""A deterministic, TEST-ONLY ``WriterAuthorizer`` for AP-3 matrix rows 14 to 16
(owner ruling AP3-D5, ``ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md`` §20.7).

    THIS IS NOT THE AX-5 AUTHORIZER. It lives under ``tests/``, is never importable
    from the worker package, flags itself ``is_reference_authorizer = True`` so the
    gate refuses it under ``production=True`` (RA-6 F-1), and exists only so the real
    adapter and the real write gate can be exercised end to end for the three
    write-gate integration rows. Production AX-5 (verified principal plus directory
    grant, with role, scope, window and delegation checks over the composed RA-6
    store) is sequenced after AP-3 and is not implemented here.

It conforms to the RA-6 seam ``WriterAuthorizer.authorize(*, principal, tenant_id,
operation, capability) -> (authorized, reasons)`` and answers from the real
``SqliteAuthorityDirectory`` the gate writes to: the principal must hold an active
grant of the role mapped to the capability, in the exact tenant, at the injected clock.
Declared capabilities on the principal are never evidence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping, Tuple

__all__ = ["ConformanceDirectoryGrantAuthorizer"]


class ConformanceDirectoryGrantAuthorizer:
    is_reference_authorizer = True
    label = "TEST_ONLY_CONFORMANCE_AUTHORIZER_NOT_AX5"

    def __init__(self, directory: Any, *, clock: Callable[[], datetime],
                 role_for_capability: Mapping[str, str], scope: str) -> None:
        self._directory = directory
        self._clock = clock
        self._roles = dict(role_for_capability)
        self._scope = scope
        self.calls: list[dict] = []

    def authorize(self, *, principal: Any, tenant_id: str, operation: str,
                  capability: str) -> Tuple[bool, Tuple[str, ...]]:
        self.calls.append({"principal_id": principal.principal_id, "tenant_id": tenant_id,
                           "operation": operation, "capability": capability})
        if getattr(principal, "capabilities", None):
            return False, ("declared capabilities are never evidence (section 20.2)",)
        if principal.tenant_id != tenant_id:
            return False, (f"principal tenant {principal.tenant_id!r} != target {tenant_id!r}",)
        role = self._roles.get(capability)
        if role is None:
            return False, (f"no directory role is mapped to capability {capability!r}",)
        grants = self._directory.grants_for(tenant_id=tenant_id, principal_id=principal.principal_id,
                                            as_of=self._clock())
        if any(g.role == role and g.scope == self._scope for g in grants):
            return True, ()
        return False, (f"no active directory grant of role {role!r} in scope {self._scope!r} "
                       f"for this principal in tenant {tenant_id!r}",)
