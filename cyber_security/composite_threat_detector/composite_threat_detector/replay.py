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
    "version": "ctd.replay/1.1.0",
    "narrow_target": "Kubernetes / infrastructure-agent high-consequence actions",
    "source_systems": {
        "actiongate": "CONTRACT ONLY — not implemented",
        "iam_events": "CONTRACT ONLY — not implemented",
        "kubernetes_audit": "REFERENCE — implemented + tested (K8sAuditReplayAdapter)",
        "cloud_control_plane": "CONTRACT ONLY — not implemented",
        "data_access_logs": "CONTRACT ONLY — not implemented",
        "change_management": "CONTRACT ONLY — not implemented",
        "approval_records": "CONTRACT ONLY — not implemented",
        "network_egress": "CONTRACT ONLY — not implemented",
        "resource_state_changes": "CONTRACT ONLY — not implemented",
        "execution_receipts": "CONTRACT ONLY — not implemented",
        "generic_normalized": "REFERENCE — implemented + tested (GenericReplayAdapter)",
    },
    "requirements": [
        "preserve source_event_id and source_timestamp",
        "record normalization decisions and dropped/unmapped fields",
        "reject events without a tenant (no cross-tenant mixing)",
        "deterministic output; no wall-clock/randomness",
        "support redaction and synthetic substitution",
        "report missing-context events rather than inventing context",
    ],
}

# K8s audit source-field mapping specification (§13.1-§13.2)
K8S_FIELD_MAP = {
    "auditID": ("event_id", "required"),
    "requestReceivedTimestamp": ("timestamp", "required"),
    "objectRef.namespace": ("tenant_id", "required (tenant = namespace)"),
    "user.username": ("actor", "required (redacted)"),
    "verb": ("_verb", "required"),
    "objectRef.resource": ("_resource", "required"),
    "objectRef.name": ("workflow_id", "optional"),
    "annotations.ctd/workflow": ("workflow_id", "optional (overrides objectRef.name)"),
    "sourceIPs": ("destination", "optional (redacted)"),
    "stage": ("_stage", "optional"),
}

# (verb, resource-substring) -> CTD capability tag. Focused on high-consequence.
_K8S_CAPABILITY = [
    (("get", "list", "watch"), "secret", "credential.read"),
    (("create", "update", "patch"), "secret", "data.write"),
    (("delete", "deletecollection"), "", "data.delete"),
    (("create", "update", "patch"), "rolebinding", "privilege.grant"),
    (("create", "update", "patch"), "clusterrolebinding", "privilege.grant"),
    (("delete", "patch"), "networkpolic", "network.egress"),  # matches networkpolicies
    (("create", "patch"), "service", "network.egress"),
    (("delete", "patch"), "flowschema", "monitoring.disable"),
]


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


def _dig(raw: dict, dotted: str):
    cur = raw
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


class K8sAuditReplayAdapter(ReplayAdapter):
    """Reference adapter for sanitized Kubernetes audit events (narrow target).

    Tenant = namespace (rejected if absent → no cross-tenant mixing). ``user`` and
    ``sourceIPs`` are redacted to stable synthetic tokens. High-consequence verbs
    map to CTD capability tags; other events are reported as unmapped, not
    silently coerced into a threat sequence. Missing required context is reported.
    """

    adapter_id = "kubernetes_audit"
    version = "1.0.0"

    def _capability(self, verb: str, resource: str) -> str:
        verb, resource = verb.lower(), resource.lower()
        for verbs, sub, cap in _K8S_CAPABILITY:
            if verb in verbs and (sub == "" or sub in resource):
                return cap
        return ""

    def normalize(self, raw: dict) -> NormalizationResult:
        decisions: list = []
        namespace = _dig(raw, "objectRef.namespace")
        if not namespace:
            return NormalizationResult(
                normalized=None, rejected=True,
                reason="missing objectRef.namespace: rejected (tenant isolation)")
        audit_id = raw.get("auditID")
        verb = raw.get("verb", "")
        resource = _dig(raw, "objectRef.resource") or ""
        cap = self._capability(verb, resource)
        out: dict = {
            "event_id": str(audit_id or ""),
            "timestamp": raw.get("requestReceivedTimestamp", ""),
            "tenant_id": str(namespace),
            "actor": "redacted:" + digest(_dig(raw, "user.username") or "",
                                          domain="CTD-REDACT")[-12:],
            "workflow_id": str(raw.get("annotations", {}).get("ctd/workflow")
                               or _dig(raw, "objectRef.name") or ""),
            "correlation_id": str(_dig(raw, "objectRef.name") or namespace),
            "operation": f"K8S_{verb.upper()}_{resource.upper()}",
        }
        if cap:
            out["capability"] = cap
            decisions.append(f"mapped ({verb},{resource}) -> capability {cap}")
        else:
            decisions.append(f"unmapped k8s action ({verb},{resource}); no capability")
        src = _dig(raw, "sourceIPs")
        if src:
            out["destination"] = "redacted:" + digest(src, domain="CTD-REDACT")[-12:]
            decisions.append("redacted sourceIPs -> synthetic token")
        out["sequence_id"] = f"{out['correlation_id']}:{audit_id}"
        mapped_srcs = {"auditID", "requestReceivedTimestamp", "objectRef", "user",
                       "verb", "sourceIPs", "annotations", "stage"}
        dropped = sorted(k for k in raw if k not in mapped_srcs)
        missing_context = not out["workflow_id"]
        prov = digest({"raw_id": audit_id, "adapter": self.adapter_id,
                       "version": self.version, "normalized": out},
                      domain="CTD-REPLAY")
        res = NormalizationResult(
            normalized=out, dropped_fields=dropped,
            normalization_decisions=decisions, provenance_digest=prov)
        res.missing_context = missing_context   # attribute for the data-quality report
        res.unmapped_capability = not cap
        return res


def data_quality_report(adapter: ReplayAdapter, raw_events: list[dict]) -> dict:
    """Deterministic data-quality summary over a batch of raw events (§13.10)."""
    total = len(raw_events)
    rejected = normalized = unmapped = missing_ctx = 0
    dropped_field_counts: dict = {}
    tenants: set = set()
    for raw in raw_events:
        res = adapter.normalize(raw)
        if res.rejected:
            rejected += 1
            continue
        normalized += 1
        tenants.add(res.normalized.get("tenant_id"))
        if getattr(res, "unmapped_capability", False):
            unmapped += 1
        if getattr(res, "missing_context", False):
            missing_ctx += 1
        for f in res.dropped_fields:
            dropped_field_counts[f] = dropped_field_counts.get(f, 0) + 1
    return {
        "evidence_label": "Measured — synthetic behavioral corpus",
        "adapter": adapter.adapter_id, "adapter_version": adapter.version,
        "total_raw_events": total, "normalized": normalized, "rejected": rejected,
        "unmapped_capability": unmapped, "missing_context": missing_ctx,
        "distinct_tenants": len(tenants),
        "dropped_field_counts": dict(sorted(dropped_field_counts.items())),
    }
