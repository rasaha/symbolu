"""Historical-replay adapter contract (§13).

Input contract + a tested *reference* normalizer for sanitized enterprise event
replay. This does **not** claim any vendor integration — only a generic,
deterministic reference adapter is implemented and tested. Named source systems
below are ``CONTRACT ONLY`` until an adapter is implemented and tested against
them.

Guarantees a conformant adapter MUST provide:
  * preserve source event IDs and source timestamps;
  * record every normalization decision and every dropped/unmapped field;
  * prevent cross-tenant mixing (a tenant is mandatory; unknown ⇒ rejected);
  * deterministic normalized output (no wall-clock, no randomness);
  * support redaction and synthetic substitution for sensitive values.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .canonical import digest

HISTORICAL_REPLAY_CONTRACT = {
    "version": "ctd.replay/1.0.0",
    "source_systems": {
        "actiongate": "CONTRACT ONLY — not implemented",
        "iam_events": "CONTRACT ONLY — not implemented",
        "kubernetes_audit": "CONTRACT ONLY — not implemented",
        "cloud_control_plane": "CONTRACT ONLY — not implemented",
        "data_access_logs": "CONTRACT ONLY — not implemented",
        "change_management": "CONTRACT ONLY — not implemented",
        "approval_records": "CONTRACT ONLY — not implemented",
        "network_egress": "CONTRACT ONLY — not implemented",
        "generic_normalized": "REFERENCE — implemented + tested (GenericReplayAdapter)",
    },
    "requirements": [
        "preserve source_event_id and source_timestamp",
        "record normalization decisions and dropped/unmapped fields",
        "reject events without a tenant (no cross-tenant mixing)",
        "deterministic output; no wall-clock/randomness",
        "support redaction and synthetic substitution",
    ],
}


@dataclass
class NormalizationResult:
    normalized: dict | None
    dropped_fields: list = field(default_factory=list)
    normalization_decisions: list = field(default_factory=list)
    rejected: bool = False
    reason: str = ""
    provenance_digest: str = ""


class ReplayAdapter:
    """Interface: map one raw source record to a normalized CTD event."""

    adapter_id = "abstract"
    version = "0.0.0"

    def normalize(self, raw: dict) -> NormalizationResult:
        raise NotImplementedError


class GenericReplayAdapter(ReplayAdapter):
    """Reference adapter over already-sanitized, generically-shaped records.

    Maps a small, explicit field set into the CTD event shape, preserving source
    identity and recording every decision. ``redact`` fields are replaced with a
    stable synthetic token (deterministic hash), never dropped silently.
    """

    adapter_id = "generic"
    version = "1.0.0"

    # source field -> CTD event field
    _MAP = {
        "source_event_id": "event_id",
        "source_timestamp": "timestamp",
        "tenant": "tenant_id",
        "principal": "actor",
        "workflow": "workflow_id",
        "correlation": "correlation_id",
        "op": "operation",
        "capability": "capability",
        "args": "arguments",
        "targets": "target_resource",
    }

    def __init__(self, redact: tuple[str, ...] = ()):
        self.redact = set(redact)

    def normalize(self, raw: dict) -> NormalizationResult:
        decisions: list = []
        dropped: list = []
        tenant = raw.get("tenant")
        if not tenant:
            return NormalizationResult(
                normalized=None, rejected=True,
                reason="missing tenant: rejected to prevent cross-tenant mixing")
        out: dict = {}
        for src, dst in self._MAP.items():
            if src not in raw:
                continue
            val = raw[src]
            if src in self.redact:
                val = "redacted:" + digest(val, domain="CTD-REDACT")[-16:]
                decisions.append(f"redacted {src} -> synthetic token")
            out[dst] = val
            decisions.append(f"mapped {src} -> {dst}")
        for k in raw:
            if k not in self._MAP:
                dropped.append(k)
        prov = digest({"raw_id": raw.get("source_event_id"),
                       "adapter": self.adapter_id, "version": self.version,
                       "normalized": out}, domain="CTD-REPLAY")
        out.setdefault("sequence_id", str(raw.get("source_event_id", "")))
        return NormalizationResult(
            normalized=out, dropped_fields=sorted(dropped),
            normalization_decisions=decisions, provenance_digest=prov)
