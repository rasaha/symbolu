"""Single canonicalization + hashing implementation shared by gateway and broker.

Addresses N9 (one framed hashing implementation, no ad-hoc concatenation) and
underpins N5 (the broker recomputes these values independently) and N11 (gateway
and broker canonicalize identically — there is exactly one implementation here).

All hashing uses the frozen length-prefixed domain separation
(``action_gate_ref.hashing.domain_digest``) over the frozen JCS canonicalizer
(``action_gate_ref.jcs.canonicalize``). Manifests carry bare JSON numbers, which
JCS forbids, so a manifest is reduced to a digest of its deterministic JSON
serialization and only the digest (a string) enters the JCS-canonicalized core.
"""

from __future__ import annotations

import json

from action_gateway._ref import hashing, jcs


def manifest_json(manifest) -> str:
    """Deterministic manifest serialization (sorted keys, compact, ASCII-escaped).

    ``ensure_ascii=True`` fixes the escaping of non-ASCII code points; a Python
    ``dict`` has already collapsed duplicate keys, so this is injective for the
    inputs the gateway and broker both hold.
    """
    if manifest is None:
        return ""
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def manifest_digest(manifest) -> str:
    return hashing.domain_digest("SIMULATION", manifest_json(manifest).encode("utf-8"))


def state_hash(namespace, kind, name, present, resource_version) -> str:
    """Framed current-state hash (replaces ad-hoc ``f"{ns}/{kind}/{name}@{rv}"``)."""
    core = {"namespace": namespace, "kind": kind, "name": name,
            "present": bool(present), "resource_version": str(resource_version or "")}
    return hashing.domain_digest("ACTION", jcs.canonicalize(core))


def action_hash(*, cluster, namespace, api_group, api_version, kind, name, verb,
                manifest, policy_hash, state_present, state_rv) -> str:
    """The canonical action identity. Gateway and broker MUST compute this the same
    way from the same fields (N5). Every value is a string/bool, so JCS accepts it."""
    core = {
        "cluster": cluster, "namespace": namespace, "api_group": api_group,
        "api_version": api_version, "kind": kind, "name": name, "verb": verb,
        "manifest_digest": manifest_digest(manifest), "policy_hash": policy_hash,
        "state_present": bool(state_present), "state_rv": str(state_rv or ""),
    }
    return hashing.domain_digest("ACTION", jcs.canonicalize(core))
