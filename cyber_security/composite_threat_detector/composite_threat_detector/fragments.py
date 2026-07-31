"""Deterministic per-event fragment extractors for the shipped ontologies.

An extractor is a pure function ``(event, correlation_id, position) -> [FragmentInstance]``.
It reads only the event's structured fields — never wall-clock, randomness, or
external state — so replaying the same event always yields the same fragments.

Two extractors ship:

* :func:`extract_digital` — operates on Action-Gate canonical action envelopes
  (or the discriminating subset of them). It maps each *individually-admissible*
  operation to the capability fragment it silently contributes. This is the real
  target: a low-and-slow adversary who decomposes a forbidden composite into
  steps that each clear the per-action gate.

* :func:`extract_physical_firearm` — the illustration from the original prompt:
  someone acquires a steel rod, a piston, a trigger mechanism separately. Each
  acquisition is innocuous; the *assembly* is a firearm. It exists to make that
  metaphor executable and to prove the engine is domain-agnostic.
"""

from __future__ import annotations

from .model import FragmentInstance

# ---------------------------------------------------------------------------
# Digital ontology fragment ids
# ---------------------------------------------------------------------------
RECON_MAP = "RECON_MAP"
CREDENTIAL_MATERIAL = "CREDENTIAL_MATERIAL"
PRIVILEGE = "PRIVILEGE"
DATA_ACCESS = "DATA_ACCESS"
EGRESS_PATH = "EGRESS_PATH"
OBSERVABILITY_GAP = "OBSERVABILITY_GAP"
PERSISTENCE = "PERSISTENCE"
STAGING = "STAGING"


def _mk(fragment_id, event, cid, position, note) -> FragmentInstance:
    return FragmentInstance(
        fragment_id=fragment_id,
        correlation_id=cid,
        sequence_id=str(event.get("sequence_id", "")),
        action_id=str(event.get("action_id", "")),
        operation=str(event.get("operation", event.get("item", ""))),
        note=note,
        position=position,
    )


def extract_digital(event: dict, cid: str, position: int) -> list[FragmentInstance]:
    """Map one admissible action envelope to the fragment(s) it contributes.

    The rules read ``operation`` plus normalized ``arguments`` — exactly the
    fields a real Action-Gate adapter already produces. Each rule is written so
    the *individually admissible* form of the action still contributes its
    fragment: acquiring one legitimate credential is fine; it is nonetheless a
    building block.
    """
    op = event.get("operation")
    a = event.get("arguments", {}) or {}
    out: list[FragmentInstance] = []

    if op == "SECRET_READ":
        out.append(_mk(CREDENTIAL_MATERIAL, event, cid, position,
                       "read a secret/credential into the agent's reach"))
        if a.get("enumerate") or a.get("list"):
            out.append(_mk(RECON_MAP, event, cid, position,
                           "enumerated the secret store (discovery)"))
    elif op == "IAM_GRANT_ADMIN":
        out.append(_mk(PRIVILEGE, event, cid, position,
                       "acquired elevated privilege"))
        principal = event.get("credential_scope", {}).get("principal")
        if principal and (a.get("grantee") == principal
                          or principal in (event.get("target_resource") or [])):
            out.append(_mk(PERSISTENCE, event, cid, position,
                           "granted privilege to its own principal (foothold)"))
    elif op in ("DB_MUTATION", "DB_DELETE"):
        out.append(_mk(DATA_ACCESS, event, cid, position,
                       f"reached into stored data via {op}"))
    elif op == "NET_EXPOSE":
        out.append(_mk(EGRESS_PATH, event, cid, position,
                       "opened a network path outward"))
    elif op == "EXTERNAL_COMMS":
        out.append(_mk(EGRESS_PATH, event, cid, position,
                       "established an outbound communication channel"))
    elif op == "MONITORING_DISABLE":
        out.append(_mk(OBSERVABILITY_GAP, event, cid, position,
                       "reduced monitoring/observability"))
    elif op == "KEY_ROTATE":
        out.append(_mk(PERSISTENCE, event, cid, position,
                       "rotated keys (can lock in / lock out)"))
    elif op == "CLOUD_SPEND_INCREASE":
        out.append(_mk(STAGING, event, cid, position,
                       "provisioned additional compute/resource (staging)"))
    return out


# ---------------------------------------------------------------------------
# Physical firearm illustration ontology fragment ids
# ---------------------------------------------------------------------------
BARREL_STOCK = "BARREL_STOCK"
FIRING_MECHANISM = "FIRING_MECHANISM"
PROJECTILE_FEED = "PROJECTILE_FEED"
PROPELLANT = "PROPELLANT"

# item token -> (fragment_id, note)
_FIREARM_ITEMS = {
    "steel_rod": (BARREL_STOCK, "acquired a steel rod (can become a barrel)"),
    "steel_pipe": (BARREL_STOCK, "acquired a steel pipe (can become a barrel)"),
    "steel_piston": (FIRING_MECHANISM, "acquired a piston (firing/striker stock)"),
    "spring": (FIRING_MECHANISM, "acquired a heavy spring (striker energy)"),
    "trigger_mechanism": (FIRING_MECHANISM, "acquired a trigger mechanism"),
    "nail": (FIRING_MECHANISM, "acquired a nail (improvised firing pin)"),
    "magazine": (PROJECTILE_FEED, "acquired a magazine / feed"),
    "ball_bearings": (PROJECTILE_FEED, "acquired ball bearings (projectiles)"),
    "gunpowder": (PROPELLANT, "acquired propellant"),
    "match_heads": (PROPELLANT, "acquired match heads (improvised propellant)"),
}


def extract_physical_firearm(event: dict, cid: str, position: int) -> list[FragmentInstance]:
    """Map one 'acquire item' event to its firearm-component fragment (if any)."""
    item = str(event.get("item", "")).strip().lower()
    hit = _FIREARM_ITEMS.get(item)
    if hit is None:
        return []
    fragment_id, note = hit
    return [_mk(fragment_id, event, cid, position, note)]
