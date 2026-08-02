"""Base class for supplied-snapshot enterprise adapters.

Each concrete adapter holds an already-captured snapshot dict, validates it, and
extracts governance-relevant facts. No live network call is made. A validation
failure yields a FAILED, fact-free result (fail closed) — never a positive signal.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Tuple

from .errors import AdapterFailureCode
from .models import AdapterCapability, AdapterRequest, AdapterResult, CollectedSignalFact
from .snapshot_schemas import (
    build_result,
    failed_result,
    validate_supplied_snapshot,
    ValidatedSnapshot,
)


class SuppliedSnapshotAdapter:
    """A read-only adapter over an already-captured, supplied snapshot."""

    kind: str = ""
    adapter_id: str = ""
    signal_type: str = ""

    def __init__(
        self,
        snapshot: Mapping[str, Any],
        *,
        registry_version: str = "",
        require_action_binding: bool = False,
    ) -> None:
        self._snapshot = snapshot
        self._registry_version = registry_version
        self._require_action_binding = require_action_binding

    def capability(self) -> AdapterCapability:
        return AdapterCapability(
            adapter_id=self.adapter_id, source_kind=self.kind,
            produced_signal_types=(self.signal_type,), read_only=True)

    def collect_snapshot(self, request: AdapterRequest) -> AdapterResult:
        validated, code = validate_supplied_snapshot(
            self._snapshot, kind=self.kind, request=request,
            require_action_binding=self._require_action_binding)
        if code is not None:
            return failed_result(
                adapter_id=self.adapter_id,
                adapter_version=str(self._snapshot.get("adapter_version", "unknown")),
                source_kind=self.kind, request=request, code=code)
        facts, extract_code = self._extract_facts(validated)
        if extract_code is not None:
            return failed_result(
                adapter_id=self.adapter_id, adapter_version=validated.adapter_version,
                source_kind=self.kind, request=request, code=extract_code)
        return build_result(
            validated=validated, adapter_id=self.adapter_id, request=request,
            facts=facts, registry_version=self._registry_version)

    def _extract_facts(
        self, validated: ValidatedSnapshot,
    ) -> Tuple[Tuple[CollectedSignalFact, ...], Optional[AdapterFailureCode]]:
        raise NotImplementedError


__all__ = ["SuppliedSnapshotAdapter"]
