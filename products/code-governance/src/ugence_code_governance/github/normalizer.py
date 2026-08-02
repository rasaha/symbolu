"""Read-only GitHub event normalizer.

Accepts a supplied webhook payload or a fixture payload (a plain mapping) and
projects it to a product-owned :class:`GovernedChangeIdentity`. It makes **no**
write calls and **no** network calls — GitHub-shaped data enters only as data.

Responsibilities (design §9):

* validate required fields;
* normalize repository and PR identity;
* bind base and head SHAs;
* preserve delivery / correlation identity;
* reject tenant mismatch;
* reject malformed events (fail closed);
* identify unsupported actions deterministically;
* be idempotent for repeated delivery ids (the *identity* is content-derived,
  so the same event always yields the same fingerprint — the Workflow Service
  performs delivery-id de-duplication on top of that).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional

from ..errors import (
    MalformedEventError,
    SignatureVerificationError,
    TenantMismatchError,
    UnsupportedEventError,
)
from ..models.change_identity import GovernedChangeIdentity
from ..models.enums import MergeMethod
from .webhook import verify_signature

#: The smallest set of ``pull_request`` actions MVP 1A must handle. A change to
#: any of these re-enters the workflow; others are deterministically rejected.
SUPPORTED_PULL_REQUEST_ACTIONS = frozenset({
    "opened",
    "synchronize",
    "reopened",
    "ready_for_review",
})


def _require(payload: Mapping[str, Any], *path: str) -> Any:
    """Fetch a nested required field, raising ``MalformedEventError`` if absent."""
    node: Any = payload
    for key in path:
        if not isinstance(node, Mapping) or key not in node or node[key] in (None, ""):
            raise MalformedEventError(f"missing required field: {'.'.join(path)}")
        node = node[key]
    return node


def normalize_pull_request_event(
    payload: Mapping[str, Any],
    *,
    tenant_id: str,
    captured_at: datetime,
    delivery_id: str,
    event_source: str = "github",
    installation_tenant_map: Optional[Mapping[str, str]] = None,
    secret: Optional[str] = None,
    signature_header: Optional[str] = None,
    raw_body: Optional[bytes] = None,
    merge_method: Optional[MergeMethod] = None,
) -> GovernedChangeIdentity:
    """Normalize a ``pull_request`` event payload into a governed change identity.

    ``tenant_id`` is the tenant the ingestion is scoped to. When an
    ``installation_tenant_map`` is supplied and the event's installation id maps
    to a *different* tenant, the event is rejected (:class:`TenantMismatchError`).

    Signature verification is optional and only performed when ``secret``,
    ``signature_header`` and ``raw_body`` are all supplied. When enabled, a
    mismatch fails closed (:class:`SignatureVerificationError`).
    """
    if not isinstance(payload, Mapping):
        raise MalformedEventError("payload must be a mapping")

    # Optional HMAC verification (fail closed when enabled and mismatched).
    if secret is not None and signature_header is not None and raw_body is not None:
        if not verify_signature(secret, raw_body, signature_header):
            raise SignatureVerificationError("webhook signature verification failed")

    action = _require(payload, "action")
    if action not in SUPPORTED_PULL_REQUEST_ACTIONS:
        raise UnsupportedEventError(
            f"unsupported pull_request action: {action!r} "
            f"(supported: {sorted(SUPPORTED_PULL_REQUEST_ACTIONS)})"
        )

    repo = _require(payload, "repository")
    owner = _require(repo, "owner", "login")
    name = _require(repo, "name")

    pr = _require(payload, "pull_request")
    number = _require(payload, "pull_request", "number")
    if not isinstance(number, int):
        raise MalformedEventError("pull_request.number must be an integer")

    base = _require(pr, "base")
    head = _require(pr, "head")
    base_ref = _require(base, "ref")
    base_sha = _require(base, "sha")
    head_ref = _require(head, "ref")
    head_sha = _require(head, "sha")

    installation_id = None
    installation = payload.get("installation") if isinstance(payload, Mapping) else None
    if isinstance(installation, Mapping) and installation.get("id") is not None:
        installation_id = str(installation["id"])

    organization_id = None
    org = payload.get("organization") if isinstance(payload, Mapping) else None
    if isinstance(org, Mapping) and org.get("login"):
        organization_id = str(org["login"])

    # Tenant isolation: an event that resolves to another tenant is refused.
    if installation_tenant_map is not None and installation_id is not None:
        resolved = installation_tenant_map.get(installation_id)
        if resolved is not None and resolved != tenant_id:
            raise TenantMismatchError(
                f"installation {installation_id} maps to tenant {resolved!r}, "
                f"not the scoped tenant {tenant_id!r}"
            )

    return GovernedChangeIdentity(
        tenant_id=tenant_id,
        repository_owner=str(owner),
        repository_name=str(name),
        pull_request_number=number,
        base_ref=str(base_ref),
        head_ref=str(head_ref),
        base_sha=str(base_sha),
        head_sha=str(head_sha),
        captured_at=captured_at,
        event_source=event_source,
        event_delivery_id=str(delivery_id),
        merge_method=merge_method,
        installation_id=installation_id,
        organization_id=organization_id,
    )


__all__ = ["normalize_pull_request_event", "SUPPORTED_PULL_REQUEST_ACTIONS"]
