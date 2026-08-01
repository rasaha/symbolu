"""Enterprise event-mapping schema + deterministic normalizer (§9).

Maps a customer source event to a canonical StoryGraph event
(``storygraph.ObservedEvent``-shaped dict). No vendor integration is claimed — a
mapping is a declarative field map validated here and applied deterministically.
Unmapped / rejected records are reported, never silently absent.
"""

from __future__ import annotations

from ..canonical import digest

EVENT_MAPPING_SCHEMA_VERSION = "ctd.event_mapping/1.0.0"

_REQUIRED = ("source_system", "source_event_type", "canonical_event_type",
             "fragment_id", "schema_version", "field_map")
# canonical entity slots the account-takeover graph reasons over
_ENTITY_SLOTS = ("account", "device", "beneficiary", "destination", "amount")


def validate_event_mapping(m: dict) -> list:
    errs = []
    for f in _REQUIRED:
        if f not in m:
            errs.append(f"event_mapping: missing '{f}'")
    if m.get("schema_version") not in (EVENT_MAPPING_SCHEMA_VERSION, None):
        errs.append("event_mapping: unversioned or wrong schema_version")
    fm = m.get("field_map", {})
    for canonical in ("event_id", "tenant_id", "actor"):
        if canonical not in fm:
            errs.append(f"event_mapping.field_map: missing required target '{canonical}'")
    return errs


def _dig(raw: dict, dotted: str):
    cur = raw
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def normalize_event(mapping: dict, raw: dict, *, redact=()) -> dict:
    """Apply a validated mapping to one raw source record. Returns a normalization
    result dict: normalized event (or None), decisions, dropped fields, rejection."""
    decisions, dropped = [], []
    fm = mapping["field_map"]
    tenant_src = fm.get("tenant_id")
    tenant = _dig(raw, tenant_src) if tenant_src else None
    if not tenant:
        return {"normalized": None, "rejected": True,
                "reason": "missing tenant: rejected (no cross-tenant mixing)",
                "decisions": decisions, "dropped_fields": dropped}
    out = {"fragment_id": mapping["fragment_id"],
           "canonical_event_type": mapping["canonical_event_type"], "entities": {}}
    for canonical, src in fm.items():
        val = _dig(raw, src)
        if val is None:
            continue
        if src in redact or canonical in redact:
            val = "redacted:" + digest(str(val), domain="CTD-REDACT")[-16:]
            decisions.append(f"redacted {src}")
        if canonical in _ENTITY_SLOTS:
            out["entities"][canonical] = str(val)
        else:
            out[canonical] = val
        decisions.append(f"mapped {src} -> {canonical}")
    mapped_srcs = set(fm.values())
    for k in raw:
        if k not in mapped_srcs and not any(s.startswith(k + ".") for s in mapped_srcs):
            dropped.append(k)
    out["dedup_identity"] = digest(
        [out.get("event_id"), out["fragment_id"],
         sorted(out["entities"].items()), out.get("actor")],
        domain="CTD-DEDUP")
    out["payload_digest"] = digest(sorted(out["entities"].items()),
                                   domain="CTD-EVENT-PAYLOAD")
    return {"normalized": out, "rejected": False, "reason": "",
            "decisions": decisions, "dropped_fields": sorted(dropped)}
