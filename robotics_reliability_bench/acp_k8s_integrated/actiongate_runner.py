"""Real ActionGate runner for one Kubernetes Deployment operation (V2.1 §2).

Runs the **actual frozen ActionGate engine** (`action_gate_ref.gate.evaluate`)
with the **real Kubernetes policy + admission checks**
(`action_gateway_k8s.policy`) — never a synthetic verdict. Given one canonical
Kubernetes action it constructs the real:

  * canonical 24-field action envelope (`action_gate_ref.schema` validated),
  * signed Kubernetes policy bundle (`action_gateway_k8s.policy.build_bundle`
    → `action_gate_ref.policy.sign_policy`),
  * evidence (`kubernetes_admission` from the real deterministic admission
    checks, `simulation` dry-run evidence, `rollback_attestation` for deletes),
  * approvals (real `action_gate_ref.approval`),
  * current-state hash (byte-compatible with `K8sStateOracle.state_hash`),
  * action hash (`action_gate_ref.projection.action_hash`),

and evaluates them to a finalized outcome. ActionGate remains the **sole
authorization authority**; this module only *invokes* it.

Deterministic + offline: `action_gate_ref` and `action_gateway_k8s.policy` are
stdlib-only pure Python (HMAC stand-in signing, no network, no k8s client). A
fixed clock makes every run byte-reproducible.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --- bootstrap the real ActionGate packages onto sys.path (offline, no cluster) --
_CS = pathlib.Path(__file__).resolve().parents[2] / "cyber_security"
for _p in (_CS / "action_gate_reference", _CS / "action_gateway_k8s"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from action_gate_ref import evidence as ref_evidence  # noqa: E402
from action_gate_ref import gate as ref_gate  # noqa: E402
from action_gate_ref import hashing as ref_hashing  # noqa: E402
from action_gate_ref import policy as ref_policy  # noqa: E402
from action_gate_ref import projection as ref_projection  # noqa: E402
from action_gate_ref import schema as ref_schema  # noqa: E402
from action_gate_ref import approval as ref_approval  # noqa: E402
import action_gateway_k8s.policy as k8s_policy  # noqa: E402

# Fixed, deterministic time base (RFC-3339 UTC, ms precision).
NOW = "2026-07-12T14:05:00.000Z"
_EVIDENCE_UNTIL = "2026-07-12T14:20:00.000Z"
_APPROVAL_ISSUED = "2026-07-12T13:00:00.000Z"
_APPROVAL_EXP = "2026-07-12T15:00:00.000Z"

# ActionGate operation for each Kubernetes verb.
AG_OPERATION = {"SCALE": "DEPLOY", "ROLLOUT": "DEPLOY", "DELETE": "DB_DELETE"}

_APPROVERS = {
    "security-lead": {"id": "security-lead", "key_id": "approver:security-lead"},
    "sre-lead": {"id": "sre-lead", "key_id": "approver:sre-lead"},
}


class _Clock:
    """Deterministic clock for the k8s evidence builders (.now/.plus)."""

    def now(self) -> str:
        return NOW

    def plus(self, seconds: float) -> str:
        return _EVIDENCE_UNTIL


@dataclass(frozen=True)
class ActionGateResult:
    """Normalized, real ActionGate decision for one Kubernetes action."""
    outcome: str                      # ALLOW / ALLOW_WITH_CONSTRAINTS / DENY / ...
    dispositive_rules: Tuple[str, ...]
    applied_constraints: Tuple[str, ...]
    action_hash: str
    policy_hash: str
    policy_version: str
    current_state_hash: str
    manifest_digest: str
    namespace: str
    name: str
    ag_operation: str
    terminal: str
    reason: str
    state_trace: Tuple[str, ...]
    admission_violations: Tuple[str, ...]
    is_authorized: bool               # outcome in {ALLOW, ALLOW_WITH_CONSTRAINTS}
    is_denied: bool                   # outcome == DENY
    is_pending: bool                  # non-final gate state


def current_state_hash(namespace: str, name: str, resource_version: str,
                       kind: str = "Deployment") -> str:
    """Reproduce `K8sStateOracle.state_hash` exactly (server.py:75-85)."""
    token = f"{namespace}/{kind}/{name}@{resource_version}"
    return "sha256:" + ref_hashing.domain_digest("ACTION", token.encode("utf-8"))


def build_manifest(namespace: str, name: str, replicas: int, *,
                   compliant: bool = True, image_tag: str = "1.0.0") -> dict:
    """Build a canonical Deployment manifest (compliant unless asked otherwise)."""
    container = {
        "name": "app",
        "image": f"registry.example.com/{name}:{image_tag}",
    }
    if compliant:
        container["resources"] = {"limits": {"cpu": "200m", "memory": "64Mi"}}
        container["securityContext"] = {"privileged": False,
                                        "allowPrivilegeEscalation": False}
    else:
        # non-compliant: privileged + no resource limits -> admission withholds
        container["securityContext"] = {"privileged": True}
    return {
        "apiVersion": "apps/v1", "kind": "Deployment",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {"replicas": replicas,
                 "template": {"spec": {"containers": [container]}}},
    }


def manifest_digest(manifest: dict) -> str:
    """Reproduce `mapping.py:121` — domain_digest('SIMULATION', manifest_json)."""
    manifest_json = json.dumps(manifest, sort_keys=True)
    return ref_hashing.domain_digest("SIMULATION", manifest_json.encode("utf-8"))


def _signed_k8s_policy(allowed_namespaces=("protected",)) -> dict:
    return ref_policy.sign_policy(k8s_policy.build_bundle(
        allowed_namespaces=tuple(allowed_namespaces)))


def _build_envelope(*, namespace, name, k8s_verb, manifest, resource_version,
                    policy_version, rollback_plan=None) -> dict:
    """Assemble a real 24-field DEPLOY/DB_DELETE envelope (schema-validated)."""
    ag_op = AG_OPERATION[k8s_verb]
    mj = json.dumps(manifest, sort_keys=True)
    md = manifest_digest(manifest)
    arguments = {"namespace": namespace, "kind": "Deployment", "name": name,
                 "manifest_json": mj, "manifest_digest": md}
    reversibility = "REVERSIBLE" if ag_op == "DEPLOY" else "REVERSIBLE_WITH_COST"
    envelope = {
        "action_id": "8b2f2c9e-1a44-4c0e-9b1a-2f6c9d0e5a71",
        "timestamp": NOW,
        "agent_identity": {"id": "agent://sre/1", "key_id": "k7", "sig": "deadbeef"},
        "runtime": "acp-shadow/2.1",
        "model_provider": {"model": "n/a", "provider": "n/a"},
        "delegator": {"id": "user://alice", "type": "HUMAN"},
        "delegation_chain": [{"from": "user://alice", "to": "agent://sre/1",
                              "grant": "*", "exp": "2026-07-12T18:00:00.000Z"}],
        "objective": f"kubernetes {k8s_verb.lower()} {namespace}/{name}",
        "tool": {"server_id": "kubernetes", "tool_name": "apply"},
        "operation": ag_op,
        "target_resource": [f"k8s://{namespace}/Deployment/{name}"],
        "arguments": arguments,
        "credential_scope": {"principal": "agent://sre/1",
                             "permissions": ["op:do"], "ttl": "PT10M"},
        "current_state_hash": current_state_hash(namespace, name, resource_version),
        "state_freshness": {"as_of": NOW, "source": "k8s-fixture"},
        "policy_version": policy_version,
        "reversibility": reversibility,
        "correlation_id": "acp21-run",
        "sequence_id": "acp21-run:0001",
    }
    if rollback_plan is not None:
        envelope["rollback_plan"] = rollback_plan
    return envelope


def run_actiongate(
    *,
    namespace: str,
    name: str,
    k8s_verb: str,                       # SCALE / ROLLOUT / DELETE
    replicas: int,
    resource_version: str,
    allowed_namespaces=("protected",),
    manifest: Optional[dict] = None,
    compliant_manifest: bool = True,
    include_simulation: bool = True,
    simulation_fidelity: str = "HIGH",
    include_approval: bool = False,
    rollback_plan: Optional[dict] = None,
    now: str = NOW,
) -> ActionGateResult:
    """Construct + evaluate the REAL ActionGate path; return the normalized result.

    Different real outcomes are produced by real inputs — an out-of-scope
    namespace or non-compliant manifest makes the deterministic admission check
    withhold `kubernetes_admission` evidence (hard MUST_HAVE unmet ⇒ real DENY);
    a missing/low simulation ⇒ real SIMULATE_AND_RETRY; a delete lacking approval
    ⇒ real ESCALATE_TO_HUMAN.
    """
    clock = _Clock()
    ag_op = AG_OPERATION[k8s_verb]
    if manifest is None:
        manifest = build_manifest(namespace, name, replicas,
                                  compliant=compliant_manifest)
    signed = _signed_k8s_policy(allowed_namespaces)
    policy_version = ref_policy.policy_version(signed["bundle"])
    envelope = _build_envelope(
        namespace=namespace, name=name, k8s_verb=k8s_verb, manifest=manifest,
        resource_version=resource_version, policy_version=policy_version,
        rollback_plan=rollback_plan)
    ref_schema.validate_envelope(envelope)
    action_hash = ref_projection.action_hash(envelope)

    evidence: List[dict] = []
    # real deterministic admission check -> evidence only when compliant
    adm_ev, violations = k8s_policy.admission_evidence(
        action_hash, envelope["arguments"], manifest,
        allowed_namespaces=tuple(allowed_namespaces), clock=clock)
    if adm_ev is not None:
        evidence.append(adm_ev)
    if include_simulation:
        evidence.append(ref_evidence.build_evidence(
            bound_to=action_hash, producer="k8s-dryrun/1.0", generated_at=now,
            valid_until=_EVIDENCE_UNTIL, evidence_version="1", kind="simulation",
            fidelity_or_confidence=simulation_fidelity, is_simulation=True,
            content={"manifest_digest": envelope["arguments"]["manifest_digest"],
                     "predicted_changes": [], "affected_resources": []}))
    if ag_op == "DB_DELETE" and rollback_plan is not None:
        rb_ev = k8s_policy.rollback_evidence(action_hash, rollback_plan, clock=clock)
        if rb_ev is not None:
            evidence.append(rb_ev)

    approvals: List[dict] = []
    if include_approval:
        approvals.append(ref_approval.build_approval(
            action_hash=action_hash, policy_hash=signed["policy_hash"],
            approver_policy="dual_control",
            approvers=[_APPROVERS["security-lead"], _APPROVERS["sre-lead"]],
            approval_scope={"operation": ag_op,
                            "target": envelope["target_resource"]},
            constraints={}, issued_at=_APPROVAL_ISSUED, expiration=_APPROVAL_EXP,
            nonce="ap-1"))

    decision = ref_gate.evaluate(envelope, signed, evidence=evidence,
                                 approvals=approvals, now=now)

    outcome = decision["outcome"]
    return ActionGateResult(
        outcome=outcome,
        dispositive_rules=tuple(decision.get("dispositive_rules", ()) or ()),
        applied_constraints=tuple(decision.get("applied_constraints", ()) or ()),
        action_hash=decision["action_hash"],
        policy_hash=decision["policy_hash"],
        policy_version=policy_version,
        current_state_hash=envelope["current_state_hash"],
        manifest_digest=envelope["arguments"]["manifest_digest"],
        namespace=namespace, name=name, ag_operation=ag_op,
        terminal=decision.get("terminal", ""),
        reason=decision.get("reason", ""),
        state_trace=tuple(decision.get("state_trace", ()) or ()),
        admission_violations=tuple(v["check"] for v in violations),
        is_authorized=outcome in (ref_gate.ALLOW, ref_gate.ALLOW_WITH_CONSTRAINTS),
        is_denied=outcome == ref_gate.DENY,
        is_pending=outcome in (ref_gate.REQUEST_MORE_EVIDENCE,
                               ref_gate.SIMULATE_AND_RETRY,
                               ref_gate.ESCALATE_TO_HUMAN),
    )
