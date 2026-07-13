"""Thin adapter over the REAL deterministic ActionGate evaluation path.

This module does **not** reimplement canonicalization, hashing, policy, the gate
state machine, or the envelope schema. It locates the frozen reference harness
(``action_gate_ref``) and the runtime mapping layer (``action_gateway``) exactly
as the production ``_core``/``_ref`` shims do, and exposes two pure functions the
ablation experiment needs:

    F(request_spec)          -> canonical 24-field envelope         (context -> E)
    D(envelope, pol, ev, ap) -> full deterministic decision record  (E,P,S -> Y)

The experiment must be able to state, honestly, that every decision it observes
came from the *real* gate — never a stand-in. Nothing here changes ActionGate
decision semantics; it only calls them.
"""

from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any

# --- locate the real packages (mirror of action_gateway/_core.py + _ref.py) ---
_CYBER = pathlib.Path(__file__).resolve().parents[3] / "cyber_security"
_REF_DIR = _CYBER / "action_gate_reference"
_GW_DIR = _CYBER / "action_gateway"
for _d in (_REF_DIR, _GW_DIR):
    if not _d.exists():  # pragma: no cover - environment guard
        raise RuntimeError(f"ActionGate package not found at {_d}")
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

import action_gate_ref  # noqa: E402
from action_gate_ref import approval as ref_approval  # noqa: E402
from action_gate_ref import evidence as ref_evidence  # noqa: E402
from action_gate_ref import gate as ref_gate  # noqa: E402
from action_gate_ref import policy as ref_policy  # noqa: E402
from action_gateway.clock import FixedClock  # noqa: E402
from action_gateway.mapping import ToolRequest, build_envelope  # noqa: E402

REF_VERSION = action_gate_ref.__version__

# Fixed evaluation clock so every run is bit-for-bit reproducible.
EVAL_NOW = "2026-07-12T14:00:00.000Z"
_GEN_AT = "2026-07-12T13:55:00.000Z"      # evidence/approval issue time (past)
_VALID_UNTIL = "2026-07-12T14:15:00.000Z"  # future validity window
_APPROVAL_ISSUED = "2026-07-12T13:00:00.000Z"
DEFAULT_STATE_HASH = "sha256:" + "00" * 32

# Named approver identities (mirror of the reference harness fixtures).
APPROVERS = {
    "security-lead": {"id": "security-lead", "key_id": "approver:security-lead"},
    "sre-lead": {"id": "sre-lead", "key_id": "approver:sre-lead"},
    "budget-owner": {"id": "budget-owner", "key_id": "approver:budget-owner"},
    "comms-owner": {"id": "comms-owner", "key_id": "approver:comms-owner"},
}
_DUAL = [APPROVERS["security-lead"], APPROVERS["sre-lead"]]
_SINGLE = [APPROVERS["security-lead"]]


@dataclass(frozen=True)
class RequestSpec:
    """Transport-neutral request the extractor assembles from surviving units.

    Only fields the frozen gate actually consumes are exposed. ``args`` carries
    the operation facts (``gate.extract_facts`` reads these keys); ``evidence``
    and ``approvals`` are lists of builder-kwargs turned into real records here.
    """

    tool: str
    verb: str
    target: tuple = ()
    args: dict = field(default_factory=dict)
    reversibility: str | None = None
    principal: str = "agent://sre/1"
    grant: str = "*"
    permissions: tuple | None = None
    state_as_of: str | None = None
    state_hash: str = DEFAULT_STATE_HASH
    evidence: tuple = ()      # each item: dict of ref_evidence.build_evidence kwargs (minus bound_to/times)
    approvals: tuple = ()     # each item: dict describing an approval to mint


def default_signed_policy() -> dict:
    """The real signed, frozen reference policy bundle (P)."""
    bundle = ref_policy.build_bundle()
    return ref_policy.sign_policy(bundle)


def _clock() -> FixedClock:
    return FixedClock(EVAL_NOW)


def build_env(spec: RequestSpec, signed_policy: dict) -> dict:
    """F: assemble the canonical envelope from a request spec via the REAL builder."""
    clock = _clock()
    pv = ref_policy.policy_version(signed_policy["bundle"])
    req = ToolRequest(
        tool=spec.tool,
        verb=spec.verb,
        target=list(spec.target),
        args=dict(spec.args),
        principal=spec.principal,
        grant=spec.grant,
        permissions=list(spec.permissions) if spec.permissions else None,
        reversibility=spec.reversibility,
        state_as_of=spec.state_as_of,
        action_id="00000000-0000-4000-8000-000000000000",  # fixed valid UUIDv4
    )
    return build_envelope(req, clock=clock, policy_version=pv,
                          current_state_hash=spec.state_hash)


def _action_hash(envelope: dict) -> str:
    from action_gate_ref import projection
    return projection.action_hash(envelope)


_DEFAULT_CONTENT = {
    "signed_artifact": {"artifact": "sha256:abc", "signed": "yes"},
    "verified_restorable_backup": {"backup_id": "b1", "restore_tested": True},
    "simulation": {"coverage": "0.9", "predicted_changes": [], "affected_resources": []},
}


def _materialize_evidence(spec: RequestSpec, action_hash: str) -> list:
    out = []
    for e in spec.evidence:
        kw = dict(e)
        kind = kw.pop("kind")
        is_sim = kw.pop("is_simulation", kind == "simulation")
        out.append(ref_evidence.build_evidence(
            bound_to=action_hash, producer=kw.pop("producer", "producer"),
            generated_at=_GEN_AT, valid_until=kw.pop("valid_until", _VALID_UNTIL),
            evidence_version="1", kind=kind,
            fidelity_or_confidence=kw.pop("fidelity", "HIGH"),
            is_simulation=is_sim,
            content=kw.pop("content", _DEFAULT_CONTENT.get(kind, {}))))
    return out


def _resolve_approvers(names) -> list:
    if names == "dual":
        return list(_DUAL)
    if names == "single":
        return list(_SINGLE)
    return [APPROVERS[n] for n in names]


def _materialize_approvals(spec: RequestSpec, envelope: dict, signed_policy: dict,
                           action_hash: str) -> list:
    out = []
    for i, a in enumerate(spec.approvals):
        kw = dict(a)
        out.append(ref_approval.build_approval(
            action_hash=action_hash, policy_hash=signed_policy["policy_hash"],
            approver_policy=kw.pop("approver_policy", "dual_control"),
            approvers=_resolve_approvers(kw.pop("approvers", "dual")),
            approval_scope={"operation": envelope["operation"],
                            "target": envelope["target_resource"]},
            constraints=kw.pop("constraints", {}),
            issued_at=_APPROVAL_ISSUED, expiration=kw.pop("expiration", _VALID_UNTIL),
            nonce=kw.pop("nonce", f"ap-{i}")))
    return out


def evaluate(spec: RequestSpec, signed_policy: dict) -> dict:
    """D: full deterministic decision record Y for a request spec.

    Returns a dict with both the raw gate decision and the envelope, so callers
    can diff envelope fields *and* decision/assurance signatures.
    """
    envelope = build_env(spec, signed_policy)
    ah = _action_hash(envelope)
    evidence = _materialize_evidence(spec, ah)
    approvals = _materialize_approvals(spec, envelope, signed_policy, ah)
    decision = ref_gate.evaluate(envelope, signed_policy, evidence=evidence,
                                 approvals=approvals, now=EVAL_NOW)
    return {"envelope": envelope, "decision": decision,
            "action_hash": ah,
            "n_evidence": len(evidence), "n_approvals": len(approvals)}
