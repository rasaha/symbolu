"""Real server-side dry-run -> frozen structured simulation evidence.

Uses the Kubernetes server-side dry-run (``?dryRun=All``) so the REAL apiserver
runs admission (including PodSecurity) and defaulting without persisting. The
result is a structured simulation-evidence envelope bound to the exact action
hash, manifest digest, and state hash — never a bare safe/unsafe boolean. If the
apiserver REJECTS the dry-run (e.g. PodSecurity forbids a privileged pod), no
simulation evidence is produced and the rejection is recorded, so the action is
not admissible.

The dry-run uses the broker's trusted admin identity (a non-mutating preview
before any capability exists); the actual mutation later uses only the scoped,
short-lived capability.
"""

from __future__ import annotations

import json

from . import cluster as cluster_mod
from ._core import ref_evidence, ref_hashing
from .adapter import _redact
from .kubeclient import GVR, K8sApiError

PRODUCER = "k8s-server-dry-run/1.0"


def _defaulting_changes(requested: dict, predicted: dict) -> dict:
    """Shallow record of fields the server defaulted/added (top-level + spec keys)."""
    added = {}
    for section in ("metadata", "spec"):
        req = requested.get(section, {}) or {}
        pred = predicted.get(section, {}) or {}
        if isinstance(req, dict) and isinstance(pred, dict):
            new_keys = sorted(set(pred) - set(req))
            if new_keys:
                added[section] = new_keys
    return added


def produce(admin_client, *, action_hash, env_args, manifest_json, state_hash, verb, clock):
    """Return (evidence_or_None, info). Evidence only when the real dry-run succeeds."""
    kind, ns, name = env_args["kind"], env_args["namespace"], env_args["name"]
    gvr = GVR[kind]
    requested = json.loads(manifest_json) if manifest_json else {}
    try:
        if verb == "apply":
            predicted = admin_client.apply(gvr, ns, name, requested, dry_run=True)
        elif verb == "delete":
            predicted = admin_client.delete(gvr, ns, name, dry_run=True)
        else:
            return None, {"ok": False, "reason": f"no dry-run for verb {verb!r}"}
    except K8sApiError as e:
        # the real apiserver rejected the operation (admission/PodSecurity/etc.)
        # status coerced to str so it is safe to embed in the audit record
        return None, {"ok": False, "reason": e.reason, "message": str(e), "status": str(e.status)}

    predicted = _redact(predicted)
    manifest_digest = ref_hashing.domain_digest(
        "SIMULATION", (manifest_json or "").encode("utf-8"))
    content = {
        "producer": PRODUCER,
        "manifest_digest": manifest_digest,
        "state_hash": state_hash,
        "affected_resources": [f"{kind}/{name}"],
        "predicted_object": {"apiVersion": predicted.get("apiVersion"),
                             "kind": predicted.get("kind"),
                             "metadata_name": predicted.get("metadata", {}).get("name"),
                             "resourceVersion": predicted.get("metadata", {}).get("resourceVersion", "")},
        "defaulting_changes": _defaulting_changes(requested, predicted),
        "warnings": [],
        "unknown_effects": ["scheduling not simulated (control-plane-only cluster)"],
        "verb": verb,
    }
    ev = ref_evidence.build_evidence(
        bound_to=action_hash, producer=PRODUCER, generated_at=clock.now(),
        valid_until=clock.plus(900), evidence_version="1", kind="simulation",
        fidelity_or_confidence="HIGH", is_simulation=True, content=content)
    return ev, {"ok": True, "predicted": content["predicted_object"]}
