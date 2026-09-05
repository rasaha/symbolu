"""The six Governed Agent Studio services (GAS-4) — thin orchestration only.

Same discipline as ``services/orchestration.py``: every step delegates to a public
entry point on the package that owns the logic, and nothing here decides anything.
There is no constitution checking, no compilation, no policy resolution, no governance
evaluation and no audit reconstruction in this module — those live in the compiler, the
activation root, Policy Authority, Decision Authority, the Agent Runtime and the console
respectively, and are reached only through the SD-1 allowlist.

Two rules shape every service below.

**Nothing here is an authority act (SD-2).** Constitution *preflights* only —
``preflight_issuance`` is documented as mutation-free, and ``issue_constitution`` /
``activate_constitution`` are permanently outside the allowlist. Policy compiles with
``require_approval`` left at its default of True. Authority *reads*. Publish reaches the
console's SHADOW loop and nothing else.

**A missing dependency is reported, never faked.** Several of these surfaces need
something the repository does not yet have: no signing key or trust root exists, and the
only reachable policy registry is in-memory. Where a dependency is absent the service
returns a typed ``unavailable`` result naming the gap. It never substitutes a stub and
presents the answer as though the real thing had run.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import ugence_agent_runtime.api as art
import ugence_policy_workflow_compiler.api as compiler

from ..clients.console import ConsoleClient, ConsoleUnavailable
from ..serialization.canonical import canonical_digest, to_jsonable

__all__ = [
    "ConstitutionService",
    "PolicyService",
    "AuthorityService",
    "SimulateService",
    "PublishService",
    "ObserveService",
    "DependencyUnavailable",
    "SIMULATION_MODES",
    "EXECUTION_MODE_ARGUMENT",
]

#: Execution modes the studio may request. ``LIVE`` is deliberately absent and there is
#: no code path that adds it: the studio never executes.
SIMULATION_MODES: Tuple[str, ...] = ("DRY_RUN", "SIMULATION", "SHADOW")
#: The task-argument key the accepted simulation mode is threaded under, so that every
#: proposal and every provider invocation in a simulated run carries it.
EXECUTION_MODE_ARGUMENT = "execution_mode"


class DependencyUnavailable(RuntimeError):
    """A capability this service needs does not exist in this deployment.

    Distinct from a validation failure on purpose. "Your constitution is invalid" and
    "no trust root is configured, so nothing could be checked" are different facts, and
    a screen that showed them identically would be misleading.
    """


def _unavailable(capability: str, reason: str) -> Dict[str, Any]:
    """The shape every service returns when a dependency is missing."""
    return {
        "available": False,
        "capability": capability,
        "reason": reason,
        "result": None,
    }


# --------------------------------------------------------------------------- #
# 1 · Constitution
# --------------------------------------------------------------------------- #
class ConstitutionService:
    """Validate and preflight a constitution. Never issues, never activates.

    ``activation_root`` is injected. When none is configured — the repository ships no
    signing key or trust root — preflight reports itself unavailable and names that,
    rather than preflighting against an ephemeral key and implying a real check ran.
    """

    def __init__(self, activation_root: Any = None) -> None:
        self._root = activation_root

    def validate(self, constitution: Dict[str, Any]) -> Dict[str, Any]:
        """Structural validation through the constitution policy package's own model."""
        from ugence_agent_constitution_policy import AgentConstitutionPolicy

        try:
            policy = AgentConstitutionPolicy.from_dict(constitution)
        except Exception as exc:  # noqa: BLE001 - an invalid document is a 422, not a 500
            return {
                "available": True,
                "validation_state": "INVALID",
                "diagnostics": [{"code": "invalid_constitution", "message": str(exc)}],
                "digest": canonical_digest(constitution),
            }
        return {
            "available": True,
            "validation_state": "VALID",
            "diagnostics": [],
            "digest": canonical_digest(constitution),
            "constitution_id": getattr(policy, "constitution_id", None),
        }

    def preflight(
        self,
        *,
        constitution: Dict[str, Any],
        record_id: str,
        approval_reference: Optional[str],
        expected_reference_tenant_id: Optional[str],
        as_of: Any,
    ) -> Dict[str, Any]:
        """Dry-run every pre-signing check. Mutation-free by the entry point's contract."""
        if self._root is None:
            return _unavailable(
                "constitution_preflight",
                "no ActivationRoot is configured: this repository ships no signing key "
                "and no trust root, so a preflight would check nothing real",
            )
        from ugence_agent_constitution_policy import AgentConstitutionPolicy

        policy = AgentConstitutionPolicy.from_dict(constitution)
        report = self._root.preflight_issuance(
            policy=policy,
            record_id=record_id,
            approval=approval_reference,
            as_of=as_of,
            expected_reference_tenant_id=expected_reference_tenant_id,
        )
        return {"available": True, "result": to_jsonable(report)}


# --------------------------------------------------------------------------- #
# 2 · Policy
# --------------------------------------------------------------------------- #
class PolicyService:
    """Validate, preview and compile a policy pack.

    Three entry points, deliberately separated. ``validate`` and ``synthesize`` are what
    the canvas calls while a pack is being authored — neither requires an approval and
    neither produces a release. ``compile`` is the only one that produces a compiled
    package, and it always carries a real approval record.
    """

    def __init__(self) -> None:
        self._compiler = compiler.GovernedWorkflowCompiler()

    @staticmethod
    def _pack(pack: Dict[str, Any]):
        return compiler.PolicyPack.model_validate(pack)

    def validate(self, pack: Dict[str, Any]) -> Dict[str, Any]:
        report = self._compiler.validate(self._pack(pack))
        return {"available": True, "result": to_jsonable(report)}

    def synthesize(self, pack: Dict[str, Any]) -> Dict[str, Any]:
        """Preview the Workflow IR without approval.

        The compiler raises on an authority-boundary violation in the synthesized IR,
        carrying its own ``ValidationReport``, so the canvas gets boundary feedback from
        the compiler itself and the studio does not re-derive it.

        NOTE `[G]`: ``CompilationError`` is not exported from
        ``ugence_policy_workflow_compiler.api``, so this cannot narrow the except clause
        without reaching into a private submodule — which SD-1 prohibits. The failure is
        therefore reported by type name rather than distinguished structurally. Closing
        this properly means exporting the error from the compiler's public surface, which
        is a change to that package and outside GAS-4.
        """
        try:
            ir = self._compiler.synthesize(self._pack(pack))
        except Exception as exc:  # noqa: BLE001 - see the note above
            report = getattr(exc, "report", None)
            return {
                "available": True,
                "synthesized": False,
                "error_type": type(exc).__name__,
                "result": to_jsonable(report) if report is not None else str(exc),
            }
        return {"available": True, "synthesized": True, "result": to_jsonable(ir)}

    def compile(self, pack: Dict[str, Any], approval: Dict[str, Any]) -> Dict[str, Any]:
        """Full compile. ``require_approval`` is left at its default of True.

        The studio never passes ``require_approval=False``; a pack without a genuine
        approval record does not compile here, exactly as it does not compile anywhere
        else.
        """
        record = compiler.HumanApprovalRecord.model_validate(approval)
        result = compiler.compile_policy_pack(self._pack(pack), record)
        return {
            "available": True,
            "success": result.success,
            "logical_digest": result.logical_digest,
            "result": to_jsonable(result.validation_report),
            "workflow_ir": to_jsonable(result.workflow_ir),
            "assurance_manifest": to_jsonable(result.assurance_manifest),
            "audit_schema": to_jsonable(result.audit_schema),
            "compiled_package": to_jsonable(result.compiled_package),
        }


# --------------------------------------------------------------------------- #
# 3 · Authority
# --------------------------------------------------------------------------- #
class AuthorityService:
    """Read-only view of issued policies and recorded decisions.

    A reader. It calls no issue and no revoke path, and those entry points are
    permanently outside the SD-1 allowlist (SD-2).
    """

    def __init__(
        self,
        registry: Any = None,
        decision_store: Any = None,
        identities: Optional[Tuple[str, ...]] = None,
    ) -> None:
        self._registry = registry
        self._decisions = decision_store
        self._identities = tuple(identities or ())

    def policies(self) -> Dict[str, Any]:
        if self._registry is None:
            return _unavailable(
                "authority_registry",
                "no PolicyRegistry is configured: the only reachable implementation is "
                "in-memory and holds one process's view, so an empty list would "
                "misrepresent an enterprise registry",
            )
        # ``PolicyRegistry`` is keyed by policy identity, so "list everything" is not a
        # read the port offers. The studio asks for the identities it was configured
        # with rather than inventing an enumeration the registry does not support.
        records = []
        for identity in self._identities:
            records.extend(self._registry.issued_records_for_identity(identity))
        return {
            "available": True,
            "result": [to_jsonable(r) for r in records],
            "registry_kind": type(self._registry).__name__,
            "identities_queried": list(self._identities),
        }

    def policy(self, record_id: str) -> Dict[str, Any]:
        if self._registry is None:
            return _unavailable("authority_registry", "no PolicyRegistry is configured")
        record = self._registry.get_issued(record_id)
        if record is None:
            return {"available": True, "found": False, "result": None}
        return {
            "available": True,
            "found": True,
            "result": to_jsonable(record),
            "revocations": [to_jsonable(r) for r in self._registry.revocations_for(record_id)],
            "supersessions": [
                to_jsonable(s) for s in self._registry.supersessions_for(record_id)
            ],
        }

    def decision(self, decision_id: str) -> Dict[str, Any]:
        if self._decisions is None:
            return _unavailable(
                "decision_authority_store",
                "no Decision Authority record store is configured",
            )
        return {"available": True, "result": to_jsonable(self._decisions.get(decision_id))}


# --------------------------------------------------------------------------- #
# 4 · Simulate
# --------------------------------------------------------------------------- #
class SimulateService:
    """Run a workflow against fixture providers, recording every governance decision.

    The runtime does the running. This service constructs a runtime from the injected
    configuration, drives it a bounded number of quanta, and reports the trace. It
    never constructs a ``TransitionProposal``, never evaluates a disposition, and never
    renders one the runtime did not return.

    ``governance_hook`` is injected. With none supplied the runtime's own default —
    ``UnconfiguredGovernanceHook``, which BLOCKs — applies, which is the correct
    behaviour for an unconfigured deployment and is reported as such.
    """

    def __init__(
        self,
        *,
        governance_hook: Any = None,
        provider_registry: Any = None,
        hook_is_permissive: bool = False,
    ) -> None:
        self._hook = governance_hook
        self._providers = provider_registry
        self._hook_is_permissive = hook_is_permissive

    def run(
        self,
        *,
        workflow: Dict[str, Any],
        execution_mode: str,
        max_quanta: int,
        correlation_id: Optional[str],
    ) -> Dict[str, Any]:
        if not isinstance(execution_mode, str) or execution_mode not in SIMULATION_MODES:
            raise ValueError(
                f"execution_mode must be one of {SIMULATION_MODES}; the studio never "
                f"executes, so LIVE is not accepted (got {execution_mode!r})"
            )
        # The accepted mode is threaded into what the runtime actually sees, not merely
        # echoed: it names the runtime, and it is placed in every task's arguments so it
        # is part of each proposal the governance boundary evaluates and of each
        # invocation a provider receives. A task that already carries a different mode
        # is a conflict, refused rather than silently overwritten.
        tasks: List[Any] = []
        for t in workflow.get("tasks", []):
            arguments = dict(t.get("arguments") or {})
            declared = arguments.get(EXECUTION_MODE_ARGUMENT)
            if declared is not None and declared != execution_mode:
                raise ValueError(
                    f"task {t.get('task_id')!r} declares {EXECUTION_MODE_ARGUMENT}="
                    f"{declared!r}, which conflicts with the requested "
                    f"{execution_mode!r}"
                )
            arguments[EXECUTION_MODE_ARGUMENT] = execution_mode
            tasks.append(
                art.TaskDefinition(
                    task_id=str(t["task_id"]),
                    operation=str(t["operation"]),
                    provider_id=t.get("provider_id"),
                    consequential=bool(t.get("consequential", True)),
                    arguments=arguments,
                    depends_on=tuple(t.get("depends_on") or ()),
                    metadata={EXECUTION_MODE_ARGUMENT: execution_mode},
                )
            )
        if self._providers is None:
            return _unavailable(
                "simulation_providers",
                "no fixture provider registry is configured, so nothing could be run",
            )

        runtime_id = f"studio-simulation:{execution_mode}"
        config_kwargs: Dict[str, Any] = {
            "provider_registry": self._providers,
            "runtime_id": runtime_id,
        }
        if self._hook is not None:
            config_kwargs["governance_hook"] = self._hook
        config = art.AgentRuntimeConfig(**config_kwargs)
        runtime = art.create_runtime(config)

        definition = art.WorkflowDefinition(
            workflow_id=str(workflow.get("workflow_id", "studio-simulation")),
            tasks=tuple(tasks),
            metadata={EXECUTION_MODE_ARGUMENT: execution_mode},
        )
        instance = art.prepare_workflow(runtime, definition, correlation_id)

        quanta: List[Dict[str, Any]] = []
        for _ in range(max(1, min(int(max_quanta), 64))):
            outcome = art.advance_workflow(runtime, instance.instance_id)
            quanta.append(to_jsonable(outcome))
            if outcome.terminal or outcome.waiting or outcome.paused:
                break

        return {
            "available": True,
            "execution_mode": execution_mode,
            # Read back from the objects the runtime ran with, so the response reports
            # the mode that was applied rather than the one that was requested.
            "execution_mode_binding": {
                "runtime_id": config.runtime_id,
                "task_argument": EXECUTION_MODE_ARGUMENT,
                "tasks": {
                    t.task_id: t.arguments.get(EXECUTION_MODE_ARGUMENT)
                    for t in definition.tasks
                },
            },
            "instance_id": instance.instance_id,
            "governance_hook_configured": self._hook is not None,
            # Stated explicitly: a run that clears everything because a permissive test
            # hook was injected is not a governance result, and a screen that did not
            # say so would be presenting a foregone conclusion as an outcome.
            "governance_hook_permissive": self._hook_is_permissive,
            "quanta": quanta,
            "result": quanta,
        }


# --------------------------------------------------------------------------- #
# 5 · Publish
# --------------------------------------------------------------------------- #
class PublishService:
    """Hand a compiled release package to the console's SHADOW governed loop."""

    def __init__(self, console: Optional[ConsoleClient] = None) -> None:
        self._console = console

    def shadow(
        self, *, compiled_package: Dict[str, Any], scenario_id: Optional[str]
    ) -> Dict[str, Any]:
        if self._console is None:
            return _unavailable(
                "console_api", "no ugence_console_api base URL is configured"
            )
        try:
            if scenario_id is not None:
                body = self._console.governed_loop_scenario(scenario_id)
            else:
                body = self._console.governed_loop_shadow(compiled_package)
        except ConsoleUnavailable as exc:
            return _unavailable("console_api", str(exc))
        return {"available": True, "mode": "SHADOW", "result": body}


# --------------------------------------------------------------------------- #
# 6 · Observe
# --------------------------------------------------------------------------- #
class ObserveService:
    """Reconstruct a decision chain by correlation id.

    Renders what the console returns. It does not re-derive, re-order or re-hash the
    chain: the console's audit store is the record, and a studio-side reconstruction
    would be a second, unverified account of the same events.
    """

    def __init__(self, console: Optional[ConsoleClient] = None) -> None:
        self._console = console

    def correlation_ids(self) -> Dict[str, Any]:
        if self._console is None:
            return _unavailable("console_api", "no ugence_console_api base URL is configured")
        try:
            return {"available": True, "result": self._console.audit_ids()}
        except ConsoleUnavailable as exc:
            return _unavailable("console_api", str(exc))

    def chain(self, correlation_id: str) -> Dict[str, Any]:
        if self._console is None:
            return _unavailable("console_api", "no ugence_console_api base URL is configured")
        try:
            return {"available": True, "result": self._console.audit_chain(correlation_id)}
        except ConsoleUnavailable as exc:
            return _unavailable("console_api", str(exc))


# --------------------------------------------------------------------------- #
# 7 · Review (GAS-7, HR-D)
# --------------------------------------------------------------------------- #
class ReviewRelayService:
    """Render the review service's queue and run detail; relay a human decision.

    Owner ruling HR-1 (``DISPLAY_AND_TRANSMIT``). Every method returns what the review
    service returned. The one thing this service does of its own is the HR-5 guard on
    the queue: an entry whose recorded disposition is a HOLD is never presented as
    awaiting a human, because a HOLD is released only by an upstream authority change.
    The review service already never lists one; this is the second lock, counted so an
    operator can see it acted.
    """

    CAPABILITY = "review_service"

    def __init__(self, review: Optional[Any] = None) -> None:
        self._review = review

    def _gap(self, reason: str) -> Dict[str, Any]:
        return _unavailable(self.CAPABILITY, reason)

    def _guard(self, fn):
        from ..clients.review import ReviewNotFound, ReviewServiceUnavailable

        if self._review is None:
            return self._gap("no governed review service base URL is configured")
        try:
            return {"available": True, "result": fn()}
        except ReviewNotFound as exc:
            return {"available": True, "found": False, "result": None, "reason": str(exc)}
        except ReviewServiceUnavailable as exc:
            return self._gap(str(exc))

    def queue(self, required_role: str = "") -> Dict[str, Any]:
        answer = self._guard(lambda: self._review.queue(required_role))
        if not answer.get("available") or not isinstance(answer.get("result"), dict):
            return answer
        raw = answer["result"]
        entries = raw.get("entries") if isinstance(raw.get("entries"), list) else []
        kept = [e for e in entries
                if not (isinstance(e, dict) and str(e.get("governance_disposition", "")).upper() == "HOLD")]
        answer["result"] = dict(raw, entries=kept)
        answer["excluded_hold"] = len(entries) - len(kept)
        answer["identity_proof"] = str(raw.get("identity_proof", ""))
        return answer

    def run(self, instance_id: str) -> Dict[str, Any]:
        return self._guard(lambda: self._review.run(instance_id))

    def run_events(self, instance_id: str) -> Dict[str, Any]:
        return self._guard(lambda: self._review.run_events(instance_id))

    def approval(self, approval_id: str) -> Dict[str, Any]:
        return self._guard(lambda: self._review.approval(approval_id))

    def submit_decision(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Relay verbatim. The studio adds nothing and reads nothing but the answer."""
        return self._guard(lambda: self._review.submit_decision(body))
