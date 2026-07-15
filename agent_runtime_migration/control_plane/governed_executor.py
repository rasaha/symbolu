"""Governed executor — the ONLY path that runs a tool.

Implements the runtime's ``ActionExecutor`` protocol. For a GOVERNED_CONSEQUENTIAL
action it builds a CER, submits it to the AI Control Plane, and runs the real tool
**iff** the control plane returned an eligible decision **with** an execution
reference. For a LOCAL_READ_ONLY action it runs a policy-permitted local fast path
(no CER). It never authorizes anything itself; it enforces the boundary.

Invariants:
* a governed tool cannot execute without a control-plane execution reference;
* a tool whose trusted risk class is GOVERNED cannot take the local fast path;
* the CER is never mutated after the decision (identity binding is re-asserted);
* nothing here mints an execution token.
"""
from __future__ import annotations

from typing import Callable, Optional

from ..contracts.action import Action, RiskClass
from ..contracts.errors import GovernanceBoundaryError, ProposalError
from ..contracts.result import ExecutionResult
from ..proposal.cer_builder import ProposalContext, build_cer, cer_identity
from ..proposal.identity_bridge import assert_binding
from ..tools.invocation import invoke_local
from ..tools.local_tool_policy import assert_local_allowed
from ..tools.registry import ToolRegistry
from ..tools.selection import resolve
from .client import ControlPlaneClient


class GovernedExecutor:
    def __init__(self, *, registry: ToolRegistry, client: ControlPlaneClient,
                 provenance: Optional[dict] = None,
                 now_provider: Optional[Callable[[], str]] = None):
        self._registry = registry
        self._client = client
        self._provenance = provenance or {"runtime": "agent-runtime-migration",
                                          "model_provider": "ugence", "model": "n/a",
                                          "objective": ""}
        # deterministic 'now' for governance; caller supplies it.
        self._now = now_provider or (lambda: "2026-01-01T00:10:00.000Z")

    def execute(self, action: Action) -> ExecutionResult:
        tool = resolve(action, self._registry)   # fails closed on risk-class disagreement

        if action.risk_class is RiskClass.LOCAL_READ_ONLY:
            assert_local_allowed(tool)            # only policy-permitted read-only tools
            try:
                output = invoke_local(tool, action.arguments)
            except Exception as exc:  # noqa: BLE001
                return ExecutionResult(action_id=action.action_id, executed=False, eligible=False,
                                       combined_outcome=None, error=str(exc))
            return ExecutionResult(action_id=action.action_id, executed=True, eligible=True,
                                   combined_outcome=None, output=output)

        # --- GOVERNED_CONSEQUENTIAL: CER -> AI Control Plane -> (maybe) tool ---
        ctx = self._context(action)
        try:
            cer = build_cer(action, ctx)
        except ProposalError as exc:
            return ExecutionResult(action_id=action.action_id, executed=False, eligible=False,
                                   combined_outcome=None, error=f"proposal rejected: {exc}")
        identity = cer_identity(cer)

        decision = self._client.submit(cer, now=self._now())
        ControlPlaneClient.ensure_not_self_authorized(decision)

        base = dict(action_id=action.action_id, eligible=decision.eligible,
                    combined_outcome=decision.composed_eligibility,
                    actiongate_outcome=decision.actiongate_authorization,
                    acp_decision=decision.acp_operational_safety,
                    cer_digest=decision.cer_digest,
                    execution_reference=decision.execution_reference,
                    reason_codes=decision.reason_codes)

        if not (decision.eligible and decision.execution_reference):
            # Not authorized+safe: the tool MUST NOT run.
            return ExecutionResult(executed=False, **base)

        # Re-assert exact-action binding: the CER we run must be the one governed.
        assert_binding(cer, identity)
        assert decision.cer_digest == identity, "control-plane digest must match the proposed CER"
        try:
            output = invoke_local(tool, action.arguments)   # the governed tool finally runs
        except Exception as exc:  # noqa: BLE001
            return ExecutionResult(executed=False, error=str(exc), **base)
        return ExecutionResult(executed=True, output=output, **base)

    def _context(self, action: Action) -> ProposalContext:
        args = action.arguments
        for f in ("authority", "state_binding", "policy_ref"):
            if f not in args:
                raise ProposalError(f"governed action missing envelope section {f!r}")
        return ProposalContext(authority=args["authority"], state_binding=args["state_binding"],
                               policy_ref=args["policy_ref"], provenance=dict(self._provenance))
