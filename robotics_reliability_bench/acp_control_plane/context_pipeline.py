"""Context Minimization + deterministic LLM-reader stage (V2.2 §2, §3).

Runs the **real** Context Minimization compressor
(`actiongate_context_ablation.compressor.compress`) on an enterprise Kubernetes
context, then a **deterministic offline reader** (the repo's existing offline
LLM mechanism — `MockReaderClient`-style: read only what survived) derives the
proposed `KubernetesOperation` from the reduced context. No compression is
simulated; no live LLM is called (a live LLM is unavailable AND non-deterministic,
which would break the required deterministic replay — see END_TO_END_SHADOW_METHOD).

The compressor is used **unchanged**. This module only builds contexts, declares a
combined `protect_fn` covering BOTH ActionGate-required and ACP-required spans, and
reads the surviving spans back into a structured operation.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Bootstrap the real Context Minimization package (offline, deterministic).
_CTX_PKG = Path(__file__).resolve().parents[2] / "experiments" / "actiongate_context_ablation"
if str(_CTX_PKG) not in sys.path:
    sys.path.insert(0, str(_CTX_PKG))

from actiongate_context_ablation import adapter as _ctx_adapter  # noqa: E402
from actiongate_context_ablation import compressor as _compressor  # noqa: E402
from actiongate_context_ablation.units import (  # noqa: E402
    Context,
    SemanticUnit,
    count_tokens,
)

# The operation fields the reader must recover, and which layer requires each.
_ACTIONGATE_CRITICAL_SPANS = frozenset({"action", "replicas", "approval", "evidence"})
_ACP_CRITICAL_SPANS = frozenset({"action", "replicas", "rver", "health", "rollback"})
# Spans that carry structured operation fragments (contrib["op"]).
_OP_SPANS = frozenset({"action", "replicas", "rver", "health", "rollback"})

# Full field set the reader must assemble for a complete proposal.
_REQUIRED_FIELDS = (
    "cluster", "namespace", "deployment", "k8s_verb", "current_replicas",
    "desired_replicas", "resource_version", "generation", "available_replicas",
    "readiness_plasticity", "seconds_since_last_action", "dependency_healthy",
    "freeze_active", "active_rollback_watches", "rollback_ref", "compliant_manifest",
)


def signed_policy():
    """The real signed ActionGate policy the compressor uses (offline)."""
    return _ctx_adapter.default_signed_policy()


# ---------------------------------------------------------------- context builder
def _op_fragment(**fields) -> dict:
    return {"op": dict(fields)}


def build_enterprise_context(
    op: dict,
    *,
    context_id: str,
    n_filler: int = 6,
    n_history: int = 3,
    n_redundant: int = 2,
    stale: bool = False,
    malformed_field: Optional[str] = None,
) -> Context:
    """Build a realistic enterprise K8s context (repeated/history/logs + critical).

    Critical spans (protected): action identity, replica state, resourceVersion,
    health, rollback, approval, evidence. Non-critical spans (removable): planning
    filler, deployment history, timestamped logs, redundant duplicates, stale
    runbook notes. `malformed_field` drops one required field from its span.
    """
    base = {
        "tool": "kubernetes", "verb": "apply",
        "target": [f"k8s://{op['namespace']}/Deployment/{op['deployment']}"],
        "args": {"namespace": op["namespace"], "deployment": op["deployment"]},
        "approvals": [{"approver_policy": "single", "approvers": "single"}],
    }
    units: List[SemanticUnit] = []

    # --- ActionGate + ACP critical spans (carry structured op fragments) ---
    action_frag = dict(cluster=op["cluster"], namespace=op["namespace"],
                       deployment=op["deployment"], k8s_verb=op["k8s_verb"],
                       compliant_manifest=op["compliant_manifest"])
    replicas_frag = dict(current_replicas=op["current_replicas"],
                         desired_replicas=op["desired_replicas"])
    rver_frag = dict(resource_version=op["resource_version"],
                     generation=op["generation"])
    health_frag = dict(available_replicas=op["available_replicas"],
                       readiness_plasticity=op["readiness_plasticity"],
                       seconds_since_last_action=op["seconds_since_last_action"],
                       dependency_healthy=op["dependency_healthy"],
                       freeze_active=op["freeze_active"],
                       active_rollback_watches=op["active_rollback_watches"])
    rollback_frag = dict(rollback_ref=op["rollback_ref"])
    for frag in (action_frag, replicas_frag, rver_frag, health_frag, rollback_frag):
        if malformed_field and malformed_field in frag:
            del frag[malformed_field]        # corrupt one critical span

    units.append(SemanticUnit(
        id="action", source_type="json_field",
        text=(f"Proposed operation: {op['k8s_verb']} deployment "
              f"{op['namespace']}/{op['deployment']} on cluster {op['cluster']}."),
        contrib=_op_fragment(**action_frag)))
    units.append(SemanticUnit(
        id="replicas", source_type="state_fact",
        text=(f"Replica state: current {op['current_replicas']}, "
              f"desired {op['desired_replicas']}."),
        contrib=_op_fragment(**replicas_frag)))
    units.append(SemanticUnit(
        id="rver", source_type="state_fact",
        text=(f"Cluster state: resourceVersion {op['resource_version']}, "
              f"generation {op['generation']}."),
        contrib=_op_fragment(**rver_frag)))
    units.append(SemanticUnit(
        id="health", source_type="state_fact",
        text=(f"Operational health: {op['available_replicas']} available, "
              f"plasticity {op['readiness_plasticity']}, last action "
              f"{op['seconds_since_last_action']}s ago, dependency "
              f"{'healthy' if op['dependency_healthy'] else 'UNHEALTHY'}, "
              f"freeze {'ACTIVE' if op['freeze_active'] else 'none'}."),
        contrib=_op_fragment(**health_frag)))
    units.append(SemanticUnit(
        id="rollback", source_type="state_fact",
        text=(f"Rollback reference: {op['rollback_ref'] or 'none'}."),
        contrib=_op_fragment(**rollback_frag)))
    units.append(SemanticUnit(
        id="approval", source_type="approval_record",
        text="Change approved by SRE lead and security lead (dual control).",
        contrib={"approvals": [{"approver_policy": "single", "approvers": "single"}]}))
    units.append(SemanticUnit(
        id="evidence", source_type="evidence_record",
        text="Signed build artifact verified; rollout dry-run simulation HIGH fidelity."))

    # --- non-critical spans (removable) ---
    for i in range(n_filler):
        units.append(SemanticUnit(
            id=f"filler{i}", source_type="sentence",
            text=f"Planning note {i}: the team reviewed the sprint backlog and roadmap."))
    for i in range(n_history):
        units.append(SemanticUnit(
            id=f"hist{i}", source_type="retrieved_passage",
            text=(f"History {i}: a previous rollout two weeks ago completed in "
                  f"eleven minutes with no regressions.")))
    for i in range(n_redundant):
        units.append(SemanticUnit(
            id=f"dup{i}", source_type="sentence",
            text="Reconfirmed: the team reviewed the sprint backlog and roadmap.",
            redundancy_set="dup_set"))
    if stale:
        units.append(SemanticUnit(
            id="stale0", source_type="retrieved_passage",
            text="Outdated runbook: owner left; this note is no longer accurate."))
    units.append(SemanticUnit(
        id="log0", source_type="log_event",
        text="12:00:01 scheduler healthcheck ok; 12:00:02 config reload ok."))

    return Context(id=context_id, base=base, units=tuple(units),
                   data_origin="AUTHORED")


def combined_protect_fn(ctx: Context) -> set:
    """Protect every span BOTH layers require (ActionGate-critical + ACP-critical).

    Directly implements §10: compressed context must never remove authorization-
    critical or operational-safety-critical information.
    """
    protected = set()
    for u in ctx.units:
        if u.id in _ACTIONGATE_CRITICAL_SPANS or u.id in _ACP_CRITICAL_SPANS:
            protected.add(u.id)
    return protected


# ---------------------------------------------------------------- minimization
@dataclass(frozen=True)
class MinimizationResult:
    context_id: str
    original_tokens: int
    reduced_tokens: int
    compression_ratio: float
    surviving_ids: Tuple[str, ...]
    protected_ids: Tuple[str, ...]
    protected_preserved: bool
    actiongate_spans_preserved: bool
    acp_spans_preserved: bool
    fell_back: bool
    decision_invariant: bool
    surviving_spans: Tuple[tuple, ...]   # (id, source_type, text) in source order


def run_minimization(ctx: Context, target_reduction: float) -> MinimizationResult:
    """Run the REAL compressor; report preservation of both layers' spans."""
    sp = signed_policy()
    r = _compressor.compress(ctx, combined_protect_fn, sp, target_reduction)
    surviving = set(r.surviving_ids)
    surviving_spans = tuple(
        (u.id, u.source_type, u.text) for u in ctx.units if u.id in surviving)
    reduced_tokens = sum(count_tokens(t) for _, _, t in surviving_spans)
    ag_ok = _ACTIONGATE_CRITICAL_SPANS.issubset(surviving | _absent(ctx))
    acp_ok = _ACP_CRITICAL_SPANS.issubset(surviving | _absent(ctx))
    return MinimizationResult(
        context_id=ctx.id,
        original_tokens=ctx.total_tokens,
        reduced_tokens=reduced_tokens,
        compression_ratio=round(r.token_reduction, 4),
        surviving_ids=tuple(sorted(surviving)),
        protected_ids=tuple(sorted(r.protected_ids)),
        protected_preserved=set(r.protected_ids).issubset(surviving),
        actiongate_spans_preserved=ag_ok,
        acp_spans_preserved=acp_ok,
        fell_back=r.fell_back,
        decision_invariant=r.invariant,
        surviving_spans=surviving_spans)


def _absent(ctx: Context) -> set:
    """Critical span ids that were never in this context (so 'preserved' is vacuous
    for them) — used so a deliberately-malformed context still reports honestly."""
    present = {u.id for u in ctx.units}
    return (_ACTIONGATE_CRITICAL_SPANS | _ACP_CRITICAL_SPANS) - present


# ---------------------------------------------------------------- deterministic reader
@dataclass(frozen=True)
class ReaderResult:
    ok: bool
    op_facts: Optional[dict]
    reason: str
    missing_fields: Tuple[str, ...] = ()


class DeterministicReader:
    """Offline, deterministic LLM stand-in (repo's MockReader mechanism).

    Reads the proposed operation ONLY from what survived compression: it merges
    the structured `contrib["op"]` fragments of the surviving spans. If a required
    field's carrying span was removed (or malformed), the reader fails closed with
    `INSUFFICIENT_CONTEXT` — exactly the behaviour that proves compression must
    preserve authorization- and operational-critical information.
    """

    def read(self, min_result: MinimizationResult, ctx: Context) -> ReaderResult:
        merged: Dict[str, object] = {}
        surviving = set(min_result.surviving_ids)
        for u in ctx.units:
            if u.id in surviving and u.id in _OP_SPANS:
                frag = (u.contrib or {}).get("op", {})
                merged.update(frag)
        missing = tuple(f for f in _REQUIRED_FIELDS if f not in merged)
        if missing:
            return ReaderResult(False, None, "INSUFFICIENT_CONTEXT", missing)
        op_facts = {k: merged[k] for k in _REQUIRED_FIELDS}
        return ReaderResult(True, op_facts, "READ_OK")
