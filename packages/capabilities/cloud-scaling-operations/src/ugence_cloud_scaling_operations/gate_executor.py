"""ArgoCD / admission gate executor (authority-gated).

Requires an explicit authorization, an allowlisted base URL, TLS verification by
default (insecure TLS refused in LIVE), an explicit timeout and bounded retries. Never
logs bearer tokens and never puts secrets in receipts or exceptions. The HTTP caller is
injected (duck-typed) so tests use a deterministic fake; no SDK/import-time network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional
from urllib.parse import urlparse

from .audit import AuditSink, InMemoryAuditSink, redact
from .authority import AuthorityVerifier, ReferenceAuthorityVerifier, verify_authorization
from .config import OperationsConfig
from .contracts import (
    ExecutionAuthorization,
    ExecutionDenied,
    ExecutionMode,
    ExecutionRequest,
)


@dataclass(frozen=True)
class GateOutcome:
    action: str            # "allow" | "hold" | "sync"
    applied: bool
    detail: str
    status_code: Optional[int] = None
    retry_count: int = 0


# Injected HTTP caller: (method, url, headers, timeout) -> (status_code, body_text)
HttpCaller = Callable[[str, str, dict, float], "tuple[int, str]"]


class GateExecutor:
    """ArgoCD sync / admission gate with fail-closed authorization."""

    def __init__(
        self,
        config: Optional[OperationsConfig] = None,
        *,
        http: Optional[HttpCaller] = None,
        verifier: Optional[AuthorityVerifier] = None,
        audit_sink: Optional[AuditSink] = None,
    ):
        self.config = config or OperationsConfig()
        self._http = http
        self.verifier = verifier or ReferenceAuthorityVerifier(require_signature=False)
        self.audit = audit_sink or InMemoryAuditSink()

    def _url_allowed(self, base_url: str) -> bool:
        if not base_url:
            return False
        try:
            parsed = urlparse(base_url)
        except Exception:
            return False
        if parsed.scheme not in ("http", "https"):
            return False
        return base_url.rstrip("/") in tuple(u.rstrip("/") for u in self.config.argocd_allowed_base_urls)

    def sync(
        self,
        request: ExecutionRequest,
        authorization: Optional[ExecutionAuthorization],
        *,
        base_url: str,
        token: str = "",
        tenant_id: str = "",
        trigger: bool = True,
    ) -> GateOutcome:
        """Trigger (or hold) an ArgoCD sync. Active sync is a mutation and needs authority."""
        import time as _t
        now = _t.time()

        # HOLD / non-mutating: allowed without mutation authority.
        if not trigger:
            return GateOutcome("hold", False, "hold: sync deferred")

        # Active sync is a mutation → require authorization (fail closed).
        try:
            verify_authorization(authorization, request, self.config, self.verifier,
                                 now=now, tenant_id=tenant_id)
        except ExecutionDenied as denied:
            return GateOutcome("hold", False, f"denied: {denied.code}")

        if self.config.allow_insecure_tls and self.config.is_live():
            return GateOutcome("hold", False, "denied: insecure TLS forbidden in LIVE")
        if not self._url_allowed(base_url):
            return GateOutcome("hold", False, "denied: base URL not allowlisted")
        if self.config.mode == ExecutionMode.DRY_RUN:
            return GateOutcome("sync", False, "dry-run: would trigger ArgoCD sync")

        if self._http is None:
            return GateOutcome("hold", False, "no HTTP caller configured")

        # Never log or embed the token; headers are redacted in any audit extra.
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        url = base_url.rstrip("/") + f"/api/v1/applications/{request.target_resource}/sync"
        attempts = 0
        last_detail = ""
        for attempt in range(max(1, self.config.max_retries + 1)):
            attempts = attempt + 1
            try:
                status, _body = self._http("POST", url, headers,
                                           self.config.request_timeout_seconds)
                if 200 <= status < 300:
                    applied = self.config.is_live()
                    return GateOutcome("sync", applied, "argocd sync triggered",
                                       status_code=status, retry_count=attempts - 1)
                last_detail = f"argocd returned status {status}"
            except Exception as exc:  # bounded retry; never leak token
                last_detail = f"argocd request error: {type(exc).__name__}"
        return GateOutcome("hold", False, f"retry exhausted: {last_detail}",
                           retry_count=attempts - 1)


__all__ = ["GateExecutor", "GateOutcome", "HttpCaller"]
