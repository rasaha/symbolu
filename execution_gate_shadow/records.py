"""Append-only shadow records + redaction (Phases 8, 12).

Prediction and observation records are written to SEPARATE append-only JSONL logs and
joined only at analysis time. Redaction strips credentials and account/project IDs before
persistence; raw content is never persisted unless explicitly permitted.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from execution_gate_shadow.config import SafetyError

_SECRET_KEYS = re.compile(r"(api[_-]?key|authorization|token|secret|password|bearer)", re.I)
_PROJECT_ID = re.compile(r"\b(projects?/)?\d{6,}\b")


def redact(obj: Any) -> Any:
    """Recursively strip secrets and reduce long numeric project/account IDs to a stable tail."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if _SECRET_KEYS.search(str(k)):
                out[k] = "<redacted>"
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, str):
        if _SECRET_KEYS.search(obj):
            return "<redacted>"
        return _PROJECT_ID.sub(lambda m: "****" + m.group(0)[-4:], obj)
    return obj


@dataclass
class PredictionRecord:
    kind: str = "prediction"
    request_id: str = ""
    provider: str = ""
    model_id: str = ""
    predicted_state: str = ""
    reason_codes: List[str] = field(default_factory=list)
    evidence_sources: List[str] = field(default_factory=list)
    evidence_ages_s: List[float] = field(default_factory=list)
    evidence_timestamps: List[float] = field(default_factory=list)
    policy_version: str = ""
    registry_version: str = ""
    predicted_at: float = 0.0


@dataclass
class ObservationRecord:
    kind: str = "observation"
    request_id: str = ""
    provider: str = ""
    model_id: str = ""
    outcome: str = "NOT_ATTEMPTED"
    attempted: bool = False
    latency_ms: float = 0.0
    est_cost_usd: float = 0.0
    observed_at: float = 0.0
    source: str = "mock"     # 'mock' | 'live' | 'normal_routing'


class AppendOnlyLog:
    """A JSONL log that only ever appends. Aborts the run if a write fails (Phase 13)."""

    def __init__(self, path: str, persist_raw: bool = False):
        self.path = path
        self.persist_raw = persist_raw
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def append(self, record: Any) -> None:
        payload = redact(asdict(record) if hasattr(record, "__dataclass_fields__") else record)
        try:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, sort_keys=True) + "\n")
        except OSError as e:
            raise SafetyError(f"audit-write failure ({e}); aborting run to preserve integrity")

    def read_all(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        with open(self.path, "r", encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]
