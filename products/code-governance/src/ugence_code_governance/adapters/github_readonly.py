"""Concrete GitHub **read-only** signal adapter.

Reads only the minimum information needed for shadow governance, over the strict
read-only transport (GET/HEAD only — the adapter has no write method and no write
client). It verifies that the returned repository, pull request, base SHA, and
head SHA match the governed change and **fails closed** on any mismatch. Source
facts are classified AUTHORITATIVE / EVENTUALLY_CONSISTENT / ADVISORY / UNAVAILABLE.

Required GitHub App permissions (documented, not configured here): read-only
``metadata``, ``pull_requests``, ``checks``, ``statuses``. No ``*:write``
permission is required or used.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Tuple

from ugence_action_clearance import SignalType  # type: ignore

from .errors import (
    AdapterError,
    AdapterFailureCode,
    NON_RETRYABLE_FAILURES,
    ReadOnlyBoundaryViolation,
)
from .models import (
    AdapterCapability,
    AdapterFetchStatus,
    AdapterIdentity,
    AdapterRequest,
    AdapterResult,
    AdapterSourceIdentity,
    CollectedSignalFact,
    FactConsistency,
    ProvenanceMetadata,
    source_response_fingerprint,
)
from .transport import ReadOnlyResponse, ReadOnlyTransport

ADAPTER_ID = "cg.github_readonly"
ADAPTER_VERSION = "1.0.0"

#: The minimum read-only GitHub App permissions this adapter requires.
REQUIRED_READ_PERMISSIONS = ("metadata:read", "pull_requests:read",
                             "checks:read", "statuses:read")
#: Permissions this adapter must NEVER require.
FORBIDDEN_WRITE_PERMISSIONS = ("contents:write", "pull_requests:write", "checks:write",
                               "statuses:write", "issues:write", "actions:write",
                               "administration:write")


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded retry for safe reads only (deterministic in tests)."""

    max_attempts: int = 1
    #: caller-supplied backoff seconds per attempt (tests pass () to avoid sleeping)
    backoff_schedule: Tuple[float, ...] = ()


class GitHubReadOnlyAdapter:
    """A GET-only GitHub adapter that never mutates and never writes."""

    def __init__(
        self,
        transport: ReadOnlyTransport,
        *,
        base_url: str = "https://api.github.com",
        source_id: str = "github",
        registry_version: str = "",
        retry: Optional[RetryPolicy] = None,
        sleep=None,
    ) -> None:
        self._transport = transport
        self._base_url = base_url.rstrip("/")
        self._source_id = source_id
        self._registry_version = registry_version
        self._retry = retry or RetryPolicy()
        self._sleep = sleep  # optional injected sleeper; unused when backoff empty

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            adapter_id=ADAPTER_ID, source_kind="github",
            produced_signal_types=(SignalType.ARTIFACT_IDENTITY.value,
                                   SignalType.TARGET_AVAILABILITY.value,
                                   SignalType.REQUIRED_CONTROL.value),
            read_only=True)

    # --- read helpers ---------------------------------------------------
    def _get_json(self, path: str) -> Tuple[Optional[Mapping[str, Any]], Optional[AdapterFailureCode]]:
        url = f"{self._base_url}{path}"
        last_code: Optional[AdapterFailureCode] = None
        attempts = max(1, self._retry.max_attempts)
        for attempt in range(attempts):
            try:
                resp = self._transport.get(url, source_id=self._source_id)
            except ReadOnlyBoundaryViolation:
                raise  # a boundary violation is a defect, never retried or swallowed
            except AdapterError as exc:
                last_code = _classify_transport_error(exc)
                if last_code in NON_RETRYABLE_FAILURES:
                    return None, last_code
                if attempt + 1 < attempts and self._sleep and attempt < len(self._retry.backoff_schedule):
                    self._sleep(self._retry.backoff_schedule[attempt])
                continue
            code = _status_to_failure(resp.status)
            if code is not None:
                last_code = code
                if code in NON_RETRYABLE_FAILURES:
                    return None, code
                if attempt + 1 < attempts and self._sleep and attempt < len(self._retry.backoff_schedule):
                    self._sleep(self._retry.backoff_schedule[attempt])
                continue
            try:
                return json.loads(resp.body.decode("utf-8")), None
            except (ValueError, UnicodeDecodeError):
                return None, AdapterFailureCode.SOURCE_SCHEMA_INVALID
        return None, last_code or AdapterFailureCode.SOURCE_UNAVAILABLE

    def collect_snapshot(self, request: AdapterRequest) -> AdapterResult:
        owner_repo = request.repository
        pr_path = f"/repos/{owner_repo}/pulls/{request.pull_request_number}"
        pr, code = self._get_json(pr_path)
        if code is not None:
            return self._failed(request, code)

        # Identity verification — fail closed on any mismatch.
        got_repo = str(((pr.get("base") or {}).get("repo") or {}).get("full_name")
                       or pr.get("repository") or owner_repo)
        got_number = pr.get("number")
        got_base = str((pr.get("base") or {}).get("sha") or "")
        got_head = str((pr.get("head") or {}).get("sha") or "")
        if got_repo != owner_repo or got_number != request.pull_request_number \
                or got_base != request.base_sha:
            return self._failed(request, AdapterFailureCode.SOURCE_IDENTITY_MISMATCH)
        if got_head != request.head_sha:
            # The governed head SHA has been superseded — the prepared action is stale.
            return self._failed(request, AdapterFailureCode.ARTIFACT_IDENTITY_MISMATCH)

        facts: List[CollectedSignalFact] = []
        # ARTIFACT_IDENTITY: the exact artifact still matches the governed change.
        facts.append(CollectedSignalFact(
            signal_type=SignalType.ARTIFACT_IDENTITY.value,
            value={"action_fingerprint": request.prepared_action_fingerprint,
                   "target_ref": owner_repo},
            consistency=FactConsistency.AUTHORITATIVE, observed_at=request.collection_time))
        # TARGET_AVAILABILITY: PR still open and not a draft (advisory mergeability aside).
        state = str(pr.get("state") or "").lower()
        draft = bool(pr.get("draft") or False)
        facts.append(CollectedSignalFact(
            signal_type=SignalType.TARGET_AVAILABILITY.value,
            value={"available": state == "open" and not draft},
            consistency=FactConsistency.EVENTUALLY_CONSISTENT,
            observed_at=request.collection_time))

        # REQUIRED_CONTROL: required check runs current + successful (best-effort).
        response_facts: dict = {"pr_state": state, "draft": draft, "head": got_head}
        checks_path = f"/repos/{owner_repo}/commits/{request.head_sha}/check-runs"
        checks, checks_code = self._get_json(checks_path)
        if checks_code is None and isinstance(checks, Mapping):
            runs = checks.get("check_runs") or []
            if isinstance(runs, list) and runs:
                completed = all(str(r.get("status")) == "completed" for r in runs)
                success = all(str(r.get("conclusion")) == "success" for r in runs)
                facts.append(CollectedSignalFact(
                    signal_type=SignalType.REQUIRED_CONTROL.value,
                    value={"satisfied": completed and success},
                    consistency=FactConsistency.EVENTUALLY_CONSISTENT,
                    observed_at=request.collection_time))
                response_facts["checks_total"] = len(runs)
                response_facts["checks_success"] = success

        response_fp = source_response_fingerprint(
            {"repo": owner_repo, "number": request.pull_request_number,
             "facts": {k: str(v) for k, v in sorted(response_facts.items())}})
        return AdapterResult(
            adapter=AdapterIdentity(ADAPTER_ID, ADAPTER_VERSION, "github"),
            source=AdapterSourceIdentity(self._source_id, "github", "github-rest"),
            requested_signal_types=request.requested_signal_types,
            collected_facts=tuple(facts),
            captured_at=request.collection_time, valid_until=request.collection_time,
            fetch_status=AdapterFetchStatus.OK, failure_codes=(),
            provenance=ProvenanceMetadata(
                adapter_id=ADAPTER_ID, adapter_version=ADAPTER_VERSION,
                source_id=self._source_id, source_kind="github",
                endpoint_class="github-rest", registry_projection_version=self._registry_version,
                source_response_fingerprint=response_fp))

    def _failed(self, request: AdapterRequest, code: AdapterFailureCode) -> AdapterResult:
        return AdapterResult(
            adapter=AdapterIdentity(ADAPTER_ID, ADAPTER_VERSION, "github"),
            source=AdapterSourceIdentity(self._source_id, "github", "github-rest"),
            requested_signal_types=request.requested_signal_types,
            collected_facts=(),
            captured_at=request.collection_time, valid_until=request.collection_time,
            fetch_status=AdapterFetchStatus.FAILED, failure_codes=(code,),
            provenance=ProvenanceMetadata(
                adapter_id=ADAPTER_ID, adapter_version=ADAPTER_VERSION,
                source_id=self._source_id, source_kind="github",
                endpoint_class="github-rest", registry_projection_version=self._registry_version,
                source_response_fingerprint=""))


def _status_to_failure(status: int) -> Optional[AdapterFailureCode]:
    if 200 <= status < 300:
        return None
    if status == 401:
        return AdapterFailureCode.SOURCE_UNAUTHORIZED
    if status == 403:
        return AdapterFailureCode.SOURCE_FORBIDDEN
    if status == 404:
        return AdapterFailureCode.SOURCE_UNAVAILABLE
    if status == 429:
        return AdapterFailureCode.SOURCE_RATE_LIMITED
    if status in (502, 503, 504):
        return AdapterFailureCode.SOURCE_UNAVAILABLE
    return AdapterFailureCode.SOURCE_UNAVAILABLE


def _classify_transport_error(exc: AdapterError) -> AdapterFailureCode:
    from .errors import AdapterResponseError
    if isinstance(exc, AdapterResponseError):
        msg = str(exc).lower()
        if "content type" in msg:
            return AdapterFailureCode.UNEXPECTED_CONTENT_TYPE
        if "exceeds" in msg or "bytes" in msg:
            return AdapterFailureCode.SOURCE_RESPONSE_TOO_LARGE
        return AdapterFailureCode.SOURCE_SCHEMA_INVALID
    return AdapterFailureCode.SOURCE_UNAVAILABLE


__all__ = [
    "GitHubReadOnlyAdapter", "RetryPolicy", "ADAPTER_ID", "ADAPTER_VERSION",
    "REQUIRED_READ_PERMISSIONS", "FORBIDDEN_WRITE_PERMISSIONS",
]
