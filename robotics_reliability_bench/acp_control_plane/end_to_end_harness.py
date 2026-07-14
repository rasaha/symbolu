"""End-to-end AI Control Plane shadow harness (V2.2 §7).

Chains the three frozen, independent layers on ONE enterprise Kubernetes
operation, in shadow mode:

    Context -> Context Minimization (real) -> reduced context
            -> deterministic reader (real, offline) -> proposed KubernetesOperation
            -> ActionGate (real) + ACP (real) via the V2.1 IntegratedShadowHarness
            -> full-chain identity binding -> hypothetical execution eligibility

No layer bypasses or duplicates another; none is authoritative; nothing mutates a
cluster; the whole chain is deterministic. OFF by default, bounded logging,
contained exceptions, kill switch.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque, Optional, Tuple

from robotics_reliability_bench.acp_control_plane.context_pipeline import (
    DeterministicReader,
    MinimizationResult,
    build_enterprise_context,
    run_minimization,
)
from robotics_reliability_bench.acp_control_plane.identity_chain import (
    context_digest,
    verify_chain,
)
from robotics_reliability_bench.acp_k8s_integrated.composition import CompositionClass
from robotics_reliability_bench.acp_k8s_integrated.harness import (
    CommitDrift,
    IntegratedShadowHarness,
)
from robotics_reliability_bench.acp_k8s_integrated.identity_binding import (
    KubernetesOperation,
)


class EndToEndClass(str, Enum):
    """Whole-pipeline outcome: front-end statuses + the 8 composition classes."""
    # front-end (context / reader / chain)
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"            # reader fail-closed
    CONTEXT_IDENTITY_MISMATCH = "CONTEXT_IDENTITY_MISMATCH"  # chain broken
    # carried through from the V2.1 composition (§5)
    AUTHORIZED_AND_OPERATIONALLY_SAFE = "AUTHORIZED_AND_OPERATIONALLY_SAFE"
    BLOCKED_BY_AUTHORIZATION = "BLOCKED_BY_AUTHORIZATION"
    HELD_BY_OPERATIONAL_SAFETY = "HELD_BY_OPERATIONAL_SAFETY"
    BLOCKED_BY_BOTH = "BLOCKED_BY_BOTH"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    REQUEST_FRESH_OPERATIONAL_STATE = "REQUEST_FRESH_OPERATIONAL_STATE"
    COMPOSITION_IDENTITY_MISMATCH = "COMPOSITION_IDENTITY_MISMATCH"
    SHADOW_ERROR = "SHADOW_ERROR"


@dataclass(frozen=True)
class ControlPlaneRecord:
    scenario_id: str
    end_to_end_class: str
    # context layer
    compression_ratio: float
    original_tokens: int
    reduced_tokens: int
    protected_preserved: bool
    actiongate_spans_preserved: bool
    acp_spans_preserved: bool
    decision_invariant: bool
    fell_back: bool
    # reader
    reader_ok: bool
    reader_reason: str
    # action / composition
    authorization_outcome: Optional[str]
    acp_recommendation: Optional[str]
    composition_class: Optional[str]
    hypothetically_eligible: bool
    # identity chain
    context_digest: Optional[str]
    actiongate_action_hash: Optional[str]
    acp_candidate_identity: Optional[str]
    execution_identity: Optional[str]
    chain_bound: bool
    chain_reason: str
    # commit revalidation (passthrough from V2.1)
    commit_revalidation: Optional[dict]
    shadow_only: bool = True
    shadow_error: bool = False
    cluster_mutated: bool = False

    def content_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass(frozen=True)
class ControlPlaneResult:
    scenario_id: str
    end_to_end_class: EndToEndClass
    minimization: MinimizationResult
    record: ControlPlaneRecord


class BoundedControlPlaneSink:
    def __init__(self, maxlen: int = 10000):
        self._buf: Deque[ControlPlaneRecord] = deque(maxlen=maxlen)
        self._dropped = 0
        self._seen = 0

    def append(self, record: ControlPlaneRecord) -> None:
        self._seen += 1
        if self._buf.maxlen is not None and len(self._buf) == self._buf.maxlen:
            self._dropped += 1
        self._buf.append(record)

    @property
    def records(self):
        return tuple(self._buf)

    @property
    def dropped(self):
        return self._dropped

    @property
    def seen(self):
        return self._seen


class ControlPlaneHarness:
    """Full Context->LLM->ActionGate->ACP shadow pipeline. OFF by default."""

    def __init__(self, *, enabled: bool = False,
                 sink: Optional[BoundedControlPlaneSink] = None,
                 allowed_namespaces=("protected",)) -> None:
        self.enabled = enabled
        self.sink = sink or BoundedControlPlaneSink()
        self._reader = DeterministicReader()
        self._integrated = IntegratedShadowHarness(
            enabled=True, allowed_namespaces=allowed_namespaces)

    def evaluate(
        self,
        op: dict,
        *,
        scenario_id: str,
        target_reduction: float = 0.6,
        n_filler: int = 8,
        n_history: int = 4,
        n_redundant: int = 3,
        stale: bool = False,
        malformed_field: Optional[str] = None,
        freshness_s: float = 1.0,
        ag_overrides: Optional[dict] = None,
        acp_manifest_digest_override: Optional[str] = None,
        commit_drift: Optional[CommitDrift] = None,
        stack_op_override: Optional[dict] = None,
    ) -> Optional[ControlPlaneResult]:
        """Run the whole pipeline for one operation. ``None`` when disabled."""
        if not self.enabled:
            return None
        try:
            return self._evaluate(
                op, scenario_id=scenario_id, target_reduction=target_reduction,
                n_filler=n_filler, n_history=n_history, n_redundant=n_redundant,
                stale=stale, malformed_field=malformed_field,
                freshness_s=freshness_s, ag_overrides=ag_overrides,
                acp_manifest_digest_override=acp_manifest_digest_override,
                commit_drift=commit_drift, stack_op_override=stack_op_override)
        except Exception as exc:  # contained: shadow must never break a caller
            rec = self._error_record(scenario_id, type(exc).__name__)
            self.sink.append(rec)
            return ControlPlaneResult(
                scenario_id, EndToEndClass.SHADOW_ERROR,
                _empty_min(scenario_id), rec)

    def _evaluate(self, op, *, scenario_id, target_reduction, n_filler, n_history,
                  n_redundant, stale, malformed_field, freshness_s, ag_overrides,
                  acp_manifest_digest_override, commit_drift, stack_op_override):
        # --- 1. Context Minimization (real) ---
        ctx = build_enterprise_context(
            op, context_id=scenario_id, n_filler=n_filler, n_history=n_history,
            n_redundant=n_redundant, stale=stale, malformed_field=malformed_field)
        mr = run_minimization(ctx, target_reduction)
        cdigest = context_digest(context_id=ctx.id, base=ctx.base,
                                 surviving_spans=list(mr.surviving_spans))

        # --- 2. deterministic reader (real, offline) ---
        rr = self._reader.read(mr, ctx)
        if not rr.ok:
            rec = self._front_record(
                scenario_id, EndToEndClass.INSUFFICIENT_CONTEXT.value, mr, rr,
                cdigest)
            self.sink.append(rec)
            return ControlPlaneResult(
                scenario_id, EndToEndClass.INSUFFICIENT_CONTEXT, mr, rec)

        # (proceed to ActionGate + ACP)

        reader_op_facts = rr.op_facts
        stack_op_facts = stack_op_override or reader_op_facts

        # --- 3. ActionGate + ACP (real) via the V2.1 integrated harness ---
        kop = KubernetesOperation(provenance="AUTHORED_DETERMINISTIC",
                                  **stack_op_facts)
        integrated = self._integrated.evaluate(
            kop, scenario_id=scenario_id, freshness_s=freshness_s,
            ag_overrides=ag_overrides,
            acp_manifest_digest_override=acp_manifest_digest_override,
            commit_drift=commit_drift)

        comp = integrated.composition
        ag = integrated.actiongate
        irec = integrated.record

        # --- 4. full-chain identity binding ---
        ident, chain_reason = verify_chain(
            reader_op_facts=reader_op_facts, stack_op_facts=stack_op_facts,
            context_digest_value=cdigest,
            actiongate_action_hash=ag.action_hash if ag else "",
            acp_candidate_identity=irec.acp_candidate_identity or "")
        chain_bound = ident is not None

        if not chain_bound:
            e2e = EndToEndClass.CONTEXT_IDENTITY_MISMATCH.value
        else:
            e2e = comp.composition_class.value

        rec = ControlPlaneRecord(
            scenario_id=scenario_id, end_to_end_class=e2e,
            compression_ratio=mr.compression_ratio,
            original_tokens=mr.original_tokens, reduced_tokens=mr.reduced_tokens,
            protected_preserved=mr.protected_preserved,
            actiongate_spans_preserved=mr.actiongate_spans_preserved,
            acp_spans_preserved=mr.acp_spans_preserved,
            decision_invariant=mr.decision_invariant, fell_back=mr.fell_back,
            reader_ok=True, reader_reason=rr.reason,
            authorization_outcome=ag.outcome if ag else None,
            acp_recommendation=irec.acp_recommendation,
            composition_class=comp.composition_class.value,
            hypothetically_eligible=(chain_bound and comp.hypothetically_eligible),
            context_digest=cdigest,
            actiongate_action_hash=ag.action_hash if ag else None,
            acp_candidate_identity=irec.acp_candidate_identity,
            execution_identity=(ident.identity if ident else None),
            chain_bound=chain_bound, chain_reason=chain_reason,
            commit_revalidation=irec.commit_revalidation)
        self.sink.append(rec)
        return ControlPlaneResult(scenario_id, EndToEndClass(e2e), mr, rec)

    # ---- record builders ----
    def _front_record(self, scenario_id, e2e, mr, rr, cdigest):
        return ControlPlaneRecord(
            scenario_id=scenario_id, end_to_end_class=e2e,
            compression_ratio=mr.compression_ratio,
            original_tokens=mr.original_tokens, reduced_tokens=mr.reduced_tokens,
            protected_preserved=mr.protected_preserved,
            actiongate_spans_preserved=mr.actiongate_spans_preserved,
            acp_spans_preserved=mr.acp_spans_preserved,
            decision_invariant=mr.decision_invariant, fell_back=mr.fell_back,
            reader_ok=False, reader_reason=rr.reason,
            authorization_outcome=None, acp_recommendation=None,
            composition_class=None, hypothetically_eligible=False,
            context_digest=cdigest, actiongate_action_hash=None,
            acp_candidate_identity=None, execution_identity=None,
            chain_bound=False, chain_reason="reader_insufficient",
            commit_revalidation=None)

    def _error_record(self, scenario_id, kind):
        return ControlPlaneRecord(
            scenario_id=scenario_id,
            end_to_end_class=CompositionClass.SHADOW_ERROR.value,
            compression_ratio=0.0, original_tokens=0, reduced_tokens=0,
            protected_preserved=False, actiongate_spans_preserved=False,
            acp_spans_preserved=False, decision_invariant=False, fell_back=False,
            reader_ok=False, reader_reason=f"SHADOW_ERROR:{kind}",
            authorization_outcome=None, acp_recommendation=None,
            composition_class=None, hypothetically_eligible=False,
            context_digest=None, actiongate_action_hash=None,
            acp_candidate_identity=None, execution_identity=None,
            chain_bound=False, chain_reason="shadow_error",
            commit_revalidation=None, shadow_error=True)


def _empty_min(scenario_id: str) -> MinimizationResult:
    return MinimizationResult(
        context_id=scenario_id, original_tokens=0, reduced_tokens=0,
        compression_ratio=0.0, surviving_ids=(), protected_ids=(),
        protected_preserved=False, actiongate_spans_preserved=False,
        acp_spans_preserved=False, fell_back=False, decision_invariant=False,
        surviving_spans=())
