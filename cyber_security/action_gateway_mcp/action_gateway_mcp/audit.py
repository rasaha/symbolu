"""Protocol-level audit log + observational metrics + argument redaction.

The runtime gateway keeps the *enforcement* audit chain (decisions/executions).
This module adds a *protocol* audit chain covering the full MCP request lifecycle
(receipt, mapping, validation, evidence request, simulation, approval, token
issuance, credential issuance, attempted/completed execution). Both chains use the
frozen ``action_gate_ref.audit`` primitives and are independently verifiable.

Never logged: raw secrets, durable credentials, broker capabilities, or sensitive
argument values. Metrics are observational only and never affect authorization.
"""

from __future__ import annotations

from ._core import ref_audit

# argument keys whose values must never appear in the audit log
_SENSITIVE_KEYS = {"secret", "password", "passwd", "token", "credential",
                   "private_key", "api_key", "content"}


def redact(args: dict) -> dict:
    """Redact sensitive argument values; keep keys + shape for auditability."""
    out = {}
    for k, v in (args or {}).items():
        if k.lower() in _SENSITIVE_KEYS:
            out[k] = "[REDACTED]"
        else:
            out[k] = v
    return out


class ProtocolAudit:
    """Append-only, tamper-evident protocol lifecycle log."""

    def __init__(self, clock, chain_id: str = "mcp-protocol"):
        self.clock = clock
        self.chain = ref_audit.AuditChain(chain_id)

    def event(self, kind: str, *, action_hash: str = "", detail: dict | None = None) -> str:
        rec = ref_audit.build_audit_record(
            action_hash=action_hash or "", decision=f"MCP:{kind}",
            dispositive_rules=sorted((detail or {}).keys()),
            policy_hash="", evidence_hashes=[], approval_hashes=[],
            applied_constraints=redact(detail or {}),
            timestamps={"at": self.clock.now()})
        self.chain.append(rec)
        if not self.chain.verify():
            raise RuntimeError("protocol audit chain verification failed after append")
        return rec["audit_record_hash"]

    def verify(self) -> dict:
        return {"intact": self.chain.verify(), "length": len(self.chain.records),
                "tamper_index": self.chain.locate_tamper()}

    def dump(self) -> list:
        return [{"seq": i, "event": r["payload"]["decision"],
                 "action_hash": r["payload"]["action_hash"],
                 "record_hash": r["audit_record_hash"]}
                for i, r in enumerate(self.chain.records)]

    def snapshot(self) -> list:
        return self.chain.records

    def restore(self, records: list) -> None:
        self.chain = ref_audit.AuditChain(self.chain.chain_id)
        for rec in records:
            self.chain.append(rec)


class Metrics:
    """Observational counters. NEVER consulted for authorization decisions."""

    FIELDS = ("requests_total", "read_requests", "executed_actions",
              "rejected_bypass_attempts", "token_replays", "capability_replays",
              "stale_state_rejections", "identity_rejections",
              "unknown_tool_rejections", "audit_verification_failures")

    def __init__(self, by_outcome=None, **counts):
        self.by_outcome: dict = by_outcome or {}
        for f in self.FIELDS:
            setattr(self, f, counts.get(f, 0))

    def inc(self, field: str, n: int = 1) -> None:
        setattr(self, field, getattr(self, field) + n)

    def outcome(self, outcome: str) -> None:
        self.by_outcome[outcome] = self.by_outcome.get(outcome, 0) + 1

    def as_dict(self) -> dict:
        d = {f: getattr(self, f) for f in self.FIELDS}
        d["by_outcome"] = dict(self.by_outcome)
        return d

    def snapshot(self) -> dict:
        return self.as_dict()

    @classmethod
    def restore(cls, snap: dict) -> "Metrics":
        by = snap.get("by_outcome", {})
        counts = {f: snap.get(f, 0) for f in cls.FIELDS}
        return cls(by_outcome=dict(by), **counts)
