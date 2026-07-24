"""Authentication / authorization boundary + tenant isolation (M4). NON-ENFORCING, shadow-only: these
guards gate the shadow pilot API surface and scope traces/artifacts to a tenant. They never protect
real resources and never enforce a real action. Deterministic, stdlib-only. Fail closed on missing/
invalid credentials or cross-tenant reference.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

# a fixed pilot HMAC key stand-in (NOT a real secret; see data_controls.secrets for the interface).
_PILOT_KEY = b"customer-shadow-pilot-demo-key-not-a-secret"

# demo principal registry (a pilot would source this from an IdP; here it is a fixture).
PRINCIPALS = {
    "tok-acme-analyst": {"principal": "analyst@acme", "tenant": "acme", "scopes": {"shadow:read", "shadow:submit"}},
    "tok-acme-reviewer": {"principal": "reviewer@acme", "tenant": "acme", "scopes": {"shadow:read", "shadow:review"}},
    "tok-globex-analyst": {"principal": "analyst@globex", "tenant": "globex", "scopes": {"shadow:read", "shadow:submit"}},
    "tok-admin": {"principal": "pilot-admin", "tenant": "*", "scopes": {"shadow:read", "shadow:admin"}},
}


@dataclass
class Principal:
    principal: str
    tenant: str
    scopes: Set[str]
    authenticated: bool
    reason: str = ""


def issue_token(token_id: str) -> str:
    """Deterministic signed token (HMAC over the token id) - a stand-in for a real bearer token."""
    sig = hmac.new(_PILOT_KEY, token_id.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{token_id}.{sig}"


def authenticate(token: Optional[str]) -> Principal:
    """Fail closed: no/invalid/tampered token -> unauthenticated principal with empty scopes."""
    if not token or "." not in token:
        return Principal("", "", set(), False, "missing_or_malformed_token")
    token_id, _, sig = token.rpartition(".")
    expect = hmac.new(_PILOT_KEY, token_id.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expect):
        return Principal("", "", set(), False, "bad_signature")
    rec = PRINCIPALS.get(token_id)
    if not rec:
        return Principal("", "", set(), False, "unknown_principal")
    return Principal(rec["principal"], rec["tenant"], set(rec["scopes"]), True)


def authorize(principal: Principal, required_scope: str) -> bool:
    return principal.authenticated and (required_scope in principal.scopes
                                        or "shadow:admin" in principal.scopes)


def tenant_permitted(principal: Principal, resource_tenant: str) -> bool:
    """A principal may only touch its own tenant's resources (admin = any). Cross-tenant -> False."""
    if not principal.authenticated:
        return False
    return principal.tenant == "*" or principal.tenant == resource_tenant


@dataclass
class AccessDecision:
    allowed: bool
    reason_codes: List[str] = field(default_factory=list)


def check_access(token: Optional[str], required_scope: str, resource_tenant: str) -> AccessDecision:
    """Single shadow-API access check: authenticate -> authorize scope -> tenant isolation. Fail closed."""
    p = authenticate(token)
    codes = []
    if not p.authenticated:
        return AccessDecision(False, [f"SEC.UNAUTHENTICATED:{p.reason}"])
    if not authorize(p, required_scope):
        codes.append(f"SEC.MISSING_SCOPE:{required_scope}")
    if not tenant_permitted(p, resource_tenant):
        codes.append(f"SEC.CROSS_TENANT_DENIED:{p.tenant}->{resource_tenant}")
    return AccessDecision(not codes, codes)
