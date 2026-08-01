"""Deterministic per-event fragment extractors for the shipped ontologies.

An extractor is a pure function ``(event, ExtractContext) -> [FragmentInstance]``.
It reads only the event's structured fields plus the resolved context (tenant,
entities, position, event time) — never wall-clock, randomness, or external
state — so replaying the same event always yields the same fragments.

Capability metadata over tool names
-----------------------------------
The digital extractor prefers an explicit ``capability`` tag (on the event or on
``tool.capability``) over the tool/operation name. Two differently-*named* tools
that declare the same capability therefore contribute the same fragment — a
renamed or newly-vendored tool cannot evade detection by relabeling.

Two extractors ship:

* :func:`extract_digital` — Action-Gate style events (the product target).
* :func:`extract_physical_firearm` — the synthetic firearm illustration from the
  original prompt, kept only to demonstrate the engine is domain-agnostic.
"""

from __future__ import annotations

from .model import PERSISTENT, TRANSIENT, ExtractContext, FragmentInstance

# ---------------------------------------------------------------------------
# Digital ontology fragment ids + decay classes
# ---------------------------------------------------------------------------
RECON_MAP = "RECON_MAP"
CREDENTIAL_MATERIAL = "CREDENTIAL_MATERIAL"
PRIVILEGE = "PRIVILEGE"
DATA_ACCESS = "DATA_ACCESS"
EGRESS_PATH = "EGRESS_PATH"
OBSERVABILITY_GAP = "OBSERVABILITY_GAP"
PERSISTENCE = "PERSISTENCE"
STAGING = "STAGING"

# Durable acquired capability persists in the ledger; discovery info decays.
DIGITAL_DECAY = {
    RECON_MAP: TRANSIENT,
    CREDENTIAL_MATERIAL: PERSISTENT,
    PRIVILEGE: PERSISTENT,
    DATA_ACCESS: PERSISTENT,
    EGRESS_PATH: PERSISTENT,
    OBSERVABILITY_GAP: PERSISTENT,
    PERSISTENCE: PERSISTENT,
    STAGING: PERSISTENT,
}

# Capability metadata tag -> fragment (independent of tool/operation NAME).
CAPABILITY_MAP = {
    "discovery.enumerate": RECON_MAP,
    "credential.read": CREDENTIAL_MATERIAL,
    "privilege.grant": PRIVILEGE,
    "data.read": DATA_ACCESS,
    "data.write": DATA_ACCESS,
    "data.delete": DATA_ACCESS,
    "network.egress": EGRESS_PATH,
    "comms.external": EGRESS_PATH,
    "monitoring.disable": OBSERVABILITY_GAP,
    "key.rotate": PERSISTENCE,
    "resource.provision": STAGING,
}

# Operation name -> (fragment, note). Fallback when no capability tag is present.
_OP_MAP = {
    "SECRET_READ": (CREDENTIAL_MATERIAL, "read a secret/credential into reach"),
    "IAM_GRANT_ADMIN": (PRIVILEGE, "acquired elevated privilege"),
    "DB_MUTATION": (DATA_ACCESS, "reached into stored data (DB_MUTATION)"),
    "DB_DELETE": (DATA_ACCESS, "reached into stored data (DB_DELETE)"),
    "NET_EXPOSE": (EGRESS_PATH, "opened a network path outward"),
    "EXTERNAL_COMMS": (EGRESS_PATH, "established an outbound channel"),
    "MONITORING_DISABLE": (OBSERVABILITY_GAP, "reduced monitoring/observability"),
    "KEY_ROTATE": (PERSISTENCE, "rotated keys (lock-in/lock-out)"),
    "CLOUD_SPEND_INCREASE": (STAGING, "provisioned additional resource (staging)"),
}

_CAP_NOTES = {
    RECON_MAP: "enumerated resources (discovery)",
    CREDENTIAL_MATERIAL: "obtained credential material",
    PRIVILEGE: "acquired elevated privilege",
    DATA_ACCESS: "reached into stored data",
    EGRESS_PATH: "opened an outbound path",
    OBSERVABILITY_GAP: "reduced monitoring/observability",
    PERSISTENCE: "established persistence/foothold",
    STAGING: "provisioned staging capacity",
}


def _mk(fragment_id, decay, event, ctx: ExtractContext, note) -> FragmentInstance:
    return FragmentInstance(
        fragment_id=fragment_id,
        decay_class=decay,
        tenant_id=ctx.tenant_id,
        correlation_id=ctx.correlation_id,
        sequence_id=ctx.sequence_id,
        event_id=ctx.event_id,
        idempotency_key=ctx.idempotency_key,
        operation=str(event.get("operation", event.get("item", ""))),
        actor=ctx.entities.get("actor", ""),
        entities=dict(ctx.entities),
        note=note,
        position=ctx.position,
        at_epoch=ctx.at_epoch,
    )


def _capability_of(event: dict) -> str:
    tool = event.get("tool", {})
    cap = event.get("capability")
    if not cap and isinstance(tool, dict):
        cap = tool.get("capability")
    return str(cap).strip().lower() if cap else ""


def extract_digital(event: dict, ctx: ExtractContext) -> list[FragmentInstance]:
    out: list[FragmentInstance] = []

    cap = _capability_of(event)
    if cap:
        frag = CAPABILITY_MAP.get(cap)
        if frag is not None:
            out.append(_mk(frag, DIGITAL_DECAY[frag], event, ctx, _CAP_NOTES[frag]))
            return out
        # capability tag present but unmapped: no fragment, caller records a miss.
        return out

    op = event.get("operation")
    a = event.get("arguments", {}) or {}

    # Outbound paths are exfil-grade only when the destination is untrusted/
    # external. An export to an approved/internal sink does NOT form EGRESS_PATH,
    # so a benign migration cannot assemble the exfiltration recipe on nouns alone.
    if op in ("NET_EXPOSE", "EXTERNAL_COMMS"):
        approved = bool(a.get("sink_approved") or a.get("approved_destination")
                        or a.get("internal"))
        if approved:
            return out
        note = _OP_MAP[op][1]
        out.append(_mk(EGRESS_PATH, DIGITAL_DECAY[EGRESS_PATH], event, ctx, note))
        return out

    mapped = _OP_MAP.get(op)
    if mapped is not None:
        frag, note = mapped
        out.append(_mk(frag, DIGITAL_DECAY[frag], event, ctx, note))
        if op == "SECRET_READ" and (a.get("enumerate") or a.get("list")):
            out.append(_mk(RECON_MAP, DIGITAL_DECAY[RECON_MAP], event, ctx,
                           "enumerated the secret store (discovery)"))
        if op == "IAM_GRANT_ADMIN":
            principal = ctx.entities.get("actor", "")
            if principal and (a.get("grantee") == principal
                              or principal in (event.get("target_resource") or [])):
                out.append(_mk(PERSISTENCE, DIGITAL_DECAY[PERSISTENCE], event, ctx,
                               "granted privilege to its own principal (foothold)"))
    return out


# ---------------------------------------------------------------------------
# Physical firearm illustration ontology (synthetic; domain-agnostic proof)
# ---------------------------------------------------------------------------
BARREL_STOCK = "BARREL_STOCK"
FIRING_MECHANISM = "FIRING_MECHANISM"
PROJECTILE_FEED = "PROJECTILE_FEED"
PROPELLANT = "PROPELLANT"

FIREARM_DECAY = {  # you keep the parts you acquire
    BARREL_STOCK: PERSISTENT, FIRING_MECHANISM: PERSISTENT,
    PROJECTILE_FEED: PERSISTENT, PROPELLANT: PERSISTENT,
}

_FIREARM_ITEMS = {
    "steel_rod": (BARREL_STOCK, "acquired a steel rod (barrel stock)"),
    "steel_pipe": (BARREL_STOCK, "acquired a steel pipe (barrel stock)"),
    "steel_piston": (FIRING_MECHANISM, "acquired a piston (firing/striker stock)"),
    "spring": (FIRING_MECHANISM, "acquired a heavy spring (striker energy)"),
    "trigger_mechanism": (FIRING_MECHANISM, "acquired a trigger mechanism"),
    "nail": (FIRING_MECHANISM, "acquired a nail (improvised firing pin)"),
    "magazine": (PROJECTILE_FEED, "acquired a magazine / feed"),
    "ball_bearings": (PROJECTILE_FEED, "acquired ball bearings (projectiles)"),
    "gunpowder": (PROPELLANT, "acquired propellant"),
    "match_heads": (PROPELLANT, "acquired match heads (improvised propellant)"),
}


def extract_physical_firearm(event: dict, ctx: ExtractContext) -> list[FragmentInstance]:
    item = str(event.get("item", "")).strip().lower()
    hit = _FIREARM_ITEMS.get(item)
    if hit is None:
        return []
    fragment_id, note = hit
    return [_mk(fragment_id, FIREARM_DECAY[fragment_id], event, ctx, note)]
