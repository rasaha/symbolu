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

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import ugence_agent_runtime.api as art
import ugence_policy_workflow_compiler.api as compiler

from ugence_clearance_export import (
    ClearanceExportError,
    ContractViolation as ExportContractViolation,
    ExportAuthenticity,
    ExportDataClassification,
    ExportIntegrityError,
    IdentityAssurance,
    artifact_to_dict,
    build_export,
    verify_export,
)
from ugence_vendor_dependency import (
    ContractViolation as VendorContractViolation,
    CrossTenantRefused as VendorCrossTenantRefused,
    DeclarationStorageError as VendorStorageError,
    DeclarationSupersessionError as VendorSupersessionError,
    DuplicateDeclarationError as DuplicateVendorDeclarationError,
    VendorDependencyDeclaration,
    VendorRiskLabel,
    binding_from_dict as vendor_binding_from_dict,
    declaration_id_for as vendor_declaration_id_for,
    declaration_record as vendor_declaration_record,
    validity_from_dict as vendor_validity_from_dict,
)
from ugence_data_use_admission import (
    ContractViolation as DeclarationContractViolation,
    DataClassificationLabel,
    CrossTenantRefused as DeclarationCrossTenantRefused,
    DataUseDeclaration,
    DeclarationStorageError,
    DeclarationSupersessionError,
    DuplicateDeclarationError,
    binding_from_dict as declaration_binding_from_dict,
    declaration_id_for,
    declaration_record,
    validity_from_dict as declaration_validity_from_dict,
)
from ugence_ai_system_registry import (
    ContractViolation as RegistryContractViolation,
    CrossTenantRefused,
    DuplicateRegistrationError,
    RegistrationSupersessionError,
    RegistryStorageError,
    SystemRegistration,
    binding_from_dict,
    registration_id_for,
    registration_record,
    validity_from_dict,
)

from ..clients.console import ConsoleClient, ConsoleUnavailable
from ..serialization.canonical import canonical_digest, to_jsonable

__all__ = [
    "ClearanceExportService",
    "ConstitutionService",
    "PolicyService",
    "AuthorityService",
    "SimulateService",
    "PublishService",
    "ObserveService",
    "RegistryService",
    "DeclarationService",
    "VendorDeclarationService",
    "VENDOR_RISK_POSTURE_NOTE",
    "VENDOR_DECLARATION_CONFERS",
    "DECLARED_BY_STATUS",
    "DECLARATION_CONFERS",
    "EGRESS_RESTRICTIONS_NOTE",
    "StartRunService",
    "WORKER_RELAY_PATH",
    "LedgerObserveService",
    "WORKER_LEDGER_SOURCE",
    "OWNER_REF_STATUS",
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

    Input is typed only (front-door ruling FD-4): a constitution document is decoded
    by the policy authority's own typed decoder into the family's artifact, and an
    approval reference must carry every field an ``ApprovalEvidenceRef`` needs. No
    default is inferred and nothing is repaired; what does not decode is refused with
    a typed diagnostic.
    """

    CAPABILITY = "constitution_preflight"

    def __init__(self, activation_root: Any = None) -> None:
        self._root = activation_root

    @staticmethod
    def _decode(constitution: Dict[str, Any]) -> Any:
        """The family artifact from its canonical document, or a typed error."""
        from ugence_agent_constitution_policy import AgentConstitutionPolicy
        from ugence_policy_authority import decode_dataclass

        return decode_dataclass(AgentConstitutionPolicy, constitution, path="$")

    @staticmethod
    def _approval_evidence_ref(text: Optional[str]) -> Any:
        """``ApprovalEvidenceRef`` from the v2 request's reference string.

        The frozen v2 contract carries one string. It is read as exactly three
        ``|``-separated parts, ``<approving_authority_id>|<approval_ref>|<digest>`` (the digest a bare lowercase
        64-character sha-256 hex string), every part required; anything else is refused. This is a typed encoding, not
        an inference: a missing or partial reference never becomes a default.
        """
        from ugence_policy_authority import ApprovalEvidenceRef

        if not isinstance(text, str) or text.count("|") != 2:
            raise ValueError(
                "approval_reference must be '<approving_authority_id>|<approval_ref>|<digest>'; "
                "preflight needs the approval artifact's authority, reference and digest and "
                "infers none of them"
            )
        authority, ref, digest = (part.strip() for part in text.split("|"))
        return ApprovalEvidenceRef(approval_ref=ref, approval_digest=digest,
                                   approving_authority_id=authority)

    def validate(self, constitution: Dict[str, Any]) -> Dict[str, Any]:
        """Structural validation through the family's own typed decoder."""
        try:
            policy = self._decode(constitution)
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
            "constitution_id": getattr(policy, "agent_constitution_ref", None),
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
        """Dry-run every pre-signing check. Mutation-free by the entry point's contract.

        With a root configured, the answer is the activation package's own: its report
        when the request is well-formed, its typed refusal when it is not. Neither
        issues, signs or stores anything.
        """
        if self._root is None:
            return _unavailable(
                self.CAPABILITY,
                "no ActivationRoot is configured: this repository ships no signing key "
                "and no trust root, so a preflight would check nothing real",
            )
        from ugence_agent_constitution_activation import AgentConstitutionActivationError
        from ugence_policy_authority import PolicyAuthorityError

        def refused(code: str, message: str) -> Dict[str, Any]:
            return {"available": True, "preflight_state": "REFUSED", "result": None,
                    "diagnostics": [{"code": code, "message": message}]}

        try:
            policy = self._decode(constitution)
        except Exception as exc:  # noqa: BLE001 - typed refusal, never a 500
            return refused("invalid_constitution", str(exc))
        try:
            approval = self._approval_evidence_ref(approval_reference)
        except Exception as exc:  # noqa: BLE001
            return refused("approval_reference_unstructured", str(exc))
        try:
            report = self._root.preflight_issuance(
                policy=policy,
                record_id=record_id,
                approval=approval,
                as_of=as_of,
                expected_reference_tenant_id=expected_reference_tenant_id,
            )
        except (AgentConstitutionActivationError, PolicyAuthorityError, ValueError) as exc:
            return refused("preflight_refused", str(exc))
        return {"available": True, "preflight_state": "REPORTED", "result": to_jsonable(report)}


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
def _public_view(obj: Any) -> Any:
    """A registry record as the screen displays it: every canonical reference, never
    the signature bytes and never the policy body (the body is reachable through the
    coordinate's content digest; display is by reference, FD-6)."""
    import dataclasses
    import enum
    from datetime import datetime

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _public_view(getattr(obj, f.name)) for f in dataclasses.fields(obj)
                if f.name not in ("signature", "policy")}
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (list, tuple)):
        return [_public_view(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): _public_view(v) for k, v in obj.items()}
    if isinstance(obj, bytes):
        return None
    return obj


class AuthorityService:
    """Read-only view of issued policies and recorded decisions (front-door seam 2, FD-6).

    A reader. It calls no issue, revoke or supersede path, and those entry points are
    permanently outside the SD-1 allowlist (SD-2). Typed retrieval and display only:
    every record is returned with its canonical references (the registry's
    ``PolicyCoordinate`` including its tenant, the record id, revocation and
    supersession ids) exactly as the registry stores them. A policy identity is typed:
    ``<policy_family>|<policy_id>|<scope>|<tenant_id>``, every part required. Anything
    the registry refuses, and anything malformed, is a typed refusal, never inferred,
    repaired or synthesized.
    """

    CAPABILITY = "authority_registry"

    def __init__(
        self,
        registry: Any = None,
        decision_store: Any = None,
        identities: Optional[Tuple[str, ...]] = None,
    ) -> None:
        self._registry = registry
        self._decisions = decision_store
        self._identities = tuple(identities or ())

    @staticmethod
    def _identity(text: str) -> Dict[str, str]:
        if not isinstance(text, str) or text.count("|") != 3:
            raise ValueError(
                "a policy identity must be '<policy_family>|<policy_id>|<scope>|<tenant_id>'; "
                f"got {text!r}")
        family, policy_id, scope, tenant = text.split("|")
        if not family or not policy_id or not scope or not tenant:
            raise ValueError(f"a policy identity has an empty part: {text!r}")
        return {"policy_family": family, "policy_id": policy_id, "scope": scope, "tenant_id": tenant}

    @staticmethod
    def _refused(code: str, message: str) -> Dict[str, Any]:
        return {"available": True, "refused": True, "code": code, "reason": message, "result": None}

    def _records(self):
        """Every issued record of every configured identity, in registry order."""
        for text in self._identities:
            for record in self._registry.issued_records_for_identity(**self._identity(text)):
                yield record

    def policies(self) -> Dict[str, Any]:
        if self._registry is None:
            return _unavailable(
                self.CAPABILITY,
                "no PolicyRegistry is configured: the only reachable implementation is "
                "in-memory and holds one process's view, so an empty list would "
                "misrepresent an enterprise registry",
            )
        from ugence_policy_authority import PolicyAuthorityError

        # ``PolicyRegistry`` is keyed by policy identity, so "list everything" is not a
        # read the port offers. The studio asks for the identities it was configured
        # with rather than inventing an enumeration the registry does not support.
        try:
            records = [_public_view(r) for r in self._records()]
        except ValueError as exc:
            return self._refused("policy_identity_unstructured", str(exc))
        except PolicyAuthorityError as exc:
            return self._refused("authority_read_refused", str(exc))
        return {
            "available": True,
            "result": records,
            "registry_kind": type(self._registry).__name__,
            "identities_queried": list(self._identities),
        }

    def policy(self, record_id: str) -> Dict[str, Any]:
        if self._registry is None:
            return _unavailable(self.CAPABILITY, "no PolicyRegistry is configured")
        from ugence_policy_authority import PolicyAuthorityError

        # The registry is addressed by exact coordinate, never by record id; the record
        # id is resolved through the configured identities' records, read-only.
        try:
            record = next((r for r in self._records() if r.record_id == record_id), None)
            if record is None:
                return {"available": True, "found": False, "result": None}
            coordinate = record.coordinate
            revocations = [_public_view(r) for r in self._registry.revocations_for(coordinate)]
            supersessions = [_public_view(s) for s in self._registry.supersessions_for(coordinate)]
        except ValueError as exc:
            return self._refused("policy_identity_unstructured", str(exc))
        except PolicyAuthorityError as exc:
            return self._refused("authority_read_refused", str(exc))
        return {
            "available": True,
            "found": True,
            "result": _public_view(record),
            "revocations": revocations,
            "supersessions": supersessions,
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
#: FD-8.2: a frozen console scenario id is a typed token. Anything else is not a
#: scenario id and is refused before any outbound request; nothing is inferred.
SCENARIO_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
PUBLISH_PAYLOAD_UNMAPPED = "publish_payload_unmapped"


def _refused(code: str, reason: str) -> Dict[str, Any]:
    return {"available": True, "refused": True, "code": code, "reason": reason, "result": None}


def scenario_id_refusal(scenario_id: Any) -> Optional[str]:
    """Why ``scenario_id`` cannot name a frozen console scenario, or ``None``."""
    if scenario_id is None:
        return ("a compiled release package is not a governed-loop request: the console's "
                "shadow loop needs an assertion, an action and operational signals that a "
                "compiled package does not carry, and the studio invents none of them; "
                "name a frozen console scenario_id instead")
    if not isinstance(scenario_id, str):
        return f"scenario_id must be a string, got {type(scenario_id).__name__}"
    if scenario_id == "":
        return "scenario_id is empty"
    if not SCENARIO_ID_PATTERN.fullmatch(scenario_id):
        return ("scenario_id is not a typed scenario token (letters, digits, '.', '_' and "
                "'-', at most 64 characters, no whitespace, no path separator)")
    return None


class PublishService:
    """Hand a frozen console scenario to the console's SHADOW governed loop (FD-8.2).

    The mode is never the caller's to choose: the console client names ``shadow`` in
    every governed-loop body it sends. A compiled release package is not a
    governed-loop request, so without a valid ``scenario_id`` the answer is the typed
    refusal ``publish_payload_unmapped``, decided before any outbound request. No field
    of ``compiled_package`` is read, forwarded or used to infer anything.
    """

    def __init__(self, console: Optional[ConsoleClient] = None) -> None:
        self._console = console

    def shadow(
        self, *, compiled_package: Dict[str, Any], scenario_id: Optional[str]
    ) -> Dict[str, Any]:
        del compiled_package  # never read (FD-8.2): nothing of it crosses the boundary
        reason = scenario_id_refusal(scenario_id)
        if reason is not None:
            return _refused(PUBLISH_PAYLOAD_UNMAPPED, reason)
        if self._console is None:
            return _unavailable(
                "console_api", "no ugence_console_api base URL is configured"
            )
        try:
            body = self._console.governed_loop_scenario(scenario_id)
        except ConsoleUnavailable as exc:
            return _unavailable("console_api", str(exc))
        return {"available": True, "mode": "SHADOW", "scenario_id": scenario_id, "result": body}


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

    def submit_decision(self, body: Dict[str, Any], *, proof: str = "") -> Dict[str, Any]:
        """Relay verbatim. The studio adds nothing and reads nothing but the answer.

        ``proof`` is the opaque approver proof the request presented (ID-1), passed
        through to the client unread and kept in no attribute of this service.
        """
        return self._guard(lambda: self._review.submit_decision(body, proof=proof))


# --------------------------------------------------------------------------- #
# 7a · The worker shadow-run relay (front-door seam 6, FD-10)
# --------------------------------------------------------------------------- #
#: FD-10.5: how the Simulate screen labels this path, distinct from the in-process
#: fixture run of seam 3. Stated by the backend so the label cannot drift from the
#: service that answers.
WORKER_RELAY_PATH: Dict[str, str] = {
    "path": "worker_shadow_run",
    "executor": "the governed runtime worker (a separate unit; the studio executes nothing)",
    "hook": "the worker's governed hook over the approval-bound source: a consequential "
            "task parks on ESCALATE in the review queue until a recorded human decision",
    "definition": "the worker's own wf-shadow under its own definition digest; the studio "
                  "sends no workflow, task, provider, mode or digest (FD-10.3)",
    "providers": "FIXTURE_ONLY",
    "maturity": "REFERENCE_GRADE_SHADOW_ONLY",
}


class StartRunService:
    """Relay-only (FD-10.1 ``START_IS_A_RELAY``): forward a typed start request to the
    worker's sixth route and return its typed answer unchanged.

    No interpretation, no default and no LIVE: the only field the studio carries is the
    operator's correlation id, the client pins the mode word, and the worker's own
    definition digest binds the run. A missing review-service URL is the typed gap
    ``review_service``; an older worker without the route (404) is a gap naming it;
    the worker's refusals (``REFUSED_MODE``, ``REFUSED_DEFINITION``, ``REFUSED_CONFLICT``,
    ``REFUSED_UNCONFIGURED``) come back as the worker said them.
    """

    CAPABILITY = "review_service"

    def __init__(self, review: Optional[Any] = None) -> None:
        self._review = review

    def start(self, *, correlation_id: Optional[str]) -> Dict[str, Any]:
        from ..clients.review import ReviewNotFound, ReviewServiceUnavailable

        if self._review is None:
            return _unavailable(self.CAPABILITY,
                                "no governed review service base URL is configured")
        try:
            answer = self._review.start_shadow_run(correlation_id)
        except ReviewNotFound as exc:
            return _unavailable(self.CAPABILITY,
                                f"the review service has no start route (an older worker): {exc}")
        except ReviewServiceUnavailable as exc:
            return _unavailable(self.CAPABILITY, str(exc))
        return {"available": True, "path": dict(WORKER_RELAY_PATH), "result": answer}


# --------------------------------------------------------------------------- #
# 7b · Observe over the worker's ledger (front-door seam 7, FD-11)
# --------------------------------------------------------------------------- #
#: FD-11.4: how the Observe screen labels this source, distinct from the console's
#: stage chain. Stated by the backend so the label cannot drift from the service.
WORKER_LEDGER_SOURCE: Dict[str, str] = {
    "source": "worker_audit_ledger",
    "record_type": "control-plane audit-ledger rows: receipts and references (kind, payload, "
                   "digests), raw and uninterpreted; not stage narratives",
    "executor": "the governed runtime worker's own ledger, read by the worker for its own "
                "tenant; the studio names no tenant and re-derives nothing",
    "durability": "durable, per-tenant, hash-chained, append-only by database trigger; "
                  "tamper-evident, not tamper-proof",
    "verification": "the worker's own verify_chain, shown as the worker reported it; a chain "
                    "that does not verify withholds its entries",
    "maturity": "REFERENCE_GRADE",
}


class LedgerObserveService:
    """Relay-only: ask the worker for its own tenant's ledger rows by correlation id and
    return the worker's answer unchanged (FD-11.3, FD-11.4).

    A missing review-service URL is the typed gap ``review_service``; an older worker
    without the route is a gap naming it; an unknown correlation id is the worker's
    typed not-found; the worker's refusals (``REFUSED_INTEGRITY``, ``REFUSED_SCHEMA``,
    ``REFUSED_UNCONFIGURED``) come back as the worker said them. Nothing here reads,
    orders, joins or re-hashes an entry.
    """

    CAPABILITY = "review_service"

    def __init__(self, review: Optional[Any] = None) -> None:
        self._review = review

    def chain(self, correlation_id: str) -> Dict[str, Any]:
        from ..clients.review import ReviewNotFound, ReviewServiceUnavailable

        if self._review is None:
            return _unavailable(self.CAPABILITY,
                                "no governed review service base URL is configured")
        try:
            answer = self._review.read_audit(correlation_id)
        except ReviewNotFound as exc:
            return {"available": True, "found": False, "result": None,
                    "source": dict(WORKER_LEDGER_SOURCE), "reason": str(exc)}
        except ReviewServiceUnavailable as exc:
            return _unavailable(self.CAPABILITY, str(exc))
        return {"available": True, "found": True, "source": dict(WORKER_LEDGER_SOURCE),
                "result": answer}


# --------------------------------------------------------------------------- #
# 8 · Registration (front-door seam 5, FD-9)
# --------------------------------------------------------------------------- #
#: FD-9.3: the registrant is a typed opaque handle the form supplied. No identity is
#: claimed; every answer says so.
OWNER_REF_STATUS = "PRESENTED_UNPROVEN"
REGISTRATION_CONFERS = "nothing: a registration is a record, not a permission (registry ADR D-5)"


def _instant(text: str) -> Optional[datetime]:
    """A timezone-aware ISO-8601 instant, or ``None``. Naive text is not an instant."""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


class RegistryService:
    """Typed intake over the deployment's ``SqliteSystemRegistry`` (FD-9).

    The tenant is the registry's, never the caller's. The registration id is derived
    by the package, never chosen. Every field is validated by ai-system-registry's own
    refusal reasons; the classification label is recorded uninterpreted; a superseding
    registration is admitted only by the package's supersession rule. The only write is
    ``register`` (FD-9.5); there is no edit, revocation, gate, admission or attestation.
    """

    CAPABILITY = "system_registry"

    def __init__(self, registry: Any = None, registered_by: str = "") -> None:
        self._registry = registry
        self._registered_by = registered_by

    def _gap(self) -> Dict[str, Any]:
        return _unavailable(
            self.CAPABILITY,
            "no system registry is configured: this deployment holds no registration file, "
            "so nothing can be recorded or listed",
        )

    @staticmethod
    def _refused(code: str, message: str) -> Dict[str, Any]:
        return {"available": True, "refused": True, "code": code, "reason": message, "result": None}

    def register(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self._registry is None:
            return self._gap()
        tenant_id = self._registry.tenant_id
        try:
            binding_input = dict(payload.get("binding") or {})
            if "tenant_id" in binding_input:
                return self._refused("registration_refused",
                                     "tenant_id is the deployment's and is never caller-supplied")
            binding = binding_from_dict({**binding_input, "tenant_id": tenant_id})
            validity_input = dict(payload.get("validity") or {})
            for name in ("issued_at", "expires_at", "stale_after"):
                raw = validity_input.get(name)
                if raw in (None, ""):
                    continue
                if not isinstance(raw, str) or _instant(raw) is None:
                    return self._refused(
                        "registration_refused",
                        f"validity.{name} must be an ISO-8601 instant with a timezone")
            validity = validity_from_dict(validity_input)
            if validity is None:
                return self._refused("registration_refused", "validity is required")
            owner_ref = payload.get("owner_ref", "")
            registration = SystemRegistration(
                registration_id=registration_id_for(binding, owner_ref, validity),
                binding=binding,
                owner_ref=owner_ref,
                classification_label=payload.get("classification_label", ""),
                validity=validity,
                supersedes=payload.get("supersedes", "") or "",
                registered_by=self._registered_by,
                notes=payload.get("notes", "") or "",
            )
        except RegistryContractViolation as exc:
            return self._refused("registration_refused", str(exc))
        except (TypeError, ValueError) as exc:
            return self._refused("registration_refused", f"typed input refused: {exc}")
        try:
            self._registry.register(registration)
        except DuplicateRegistrationError as exc:
            return self._refused("registration_duplicate", str(exc))
        except RegistrationSupersessionError as exc:
            return self._refused("supersession_refused", str(exc))
        except CrossTenantRefused as exc:
            return self._refused("registration_refused", str(exc))
        except RegistryStorageError as exc:
            return _unavailable(self.CAPABILITY, f"the registry could not be written: {exc}")
        return {
            "available": True,
            "registered": True,
            "tenant_id": tenant_id,
            "registry_kind": type(self._registry).__name__,
            "record": registration_record(registration),
            "record_digest": registration.record_digest(),
            "registration_id": registration.registration_id,
            "owner_ref_status": OWNER_REF_STATUS,
            "registered_by": self._registered_by,
            "confers": REGISTRATION_CONFERS,
            "result": registration_record(registration),
        }

    def list(self, *, as_of: Optional[str]) -> Dict[str, Any]:
        if self._registry is None:
            return self._gap()
        tenant_id = self._registry.tenant_id
        if as_of is None:
            instant = datetime.now(timezone.utc)
            source = "request"
        else:
            parsed = _instant(as_of) if isinstance(as_of, str) else None
            if parsed is None:
                return self._refused("as_of_untyped",
                                     "as_of must be an ISO-8601 instant with a timezone")
            instant = parsed
            source = "caller"
        try:
            registrations = self._registry.registrations_for_tenant(tenant_id=tenant_id, as_of=instant)
        except CrossTenantRefused as exc:
            return self._refused("registration_refused", str(exc))
        except (RegistryStorageError, RegistryContractViolation) as exc:
            return _unavailable(self.CAPABILITY, f"the registry could not be read: {exc}")
        records = [registration_record(r) for r in registrations]
        return {
            "available": True,
            "tenant_id": tenant_id,
            "registry_kind": type(self._registry).__name__,
            "as_of": instant.isoformat(),
            "as_of_source": source,
            "count": len(records),
            "owner_ref_status": OWNER_REF_STATUS,
            "confers": REGISTRATION_CONFERS,
            "result": records,
        }


# --------------------------------------------------------------------------- #
# Screen 5 · Data-use declarations (front-door seam 8, FD-12)
# --------------------------------------------------------------------------- #
#: FD-12.3: the declarer is a typed opaque handle the form supplied. No identity is
#: claimed until an enterprise issuer exists (AI-E); every answer says so.
DECLARED_BY_STATUS = "PRESENTED_UNPROVEN"
DECLARATION_CONFERS = (
    "nothing: a declaration is a record of what a declarer asserted, not an admission, "
    "an approval or a permission (data-egress ADR DE-1, FD-12.5)"
)
#: FD-12.5: the egress package does not exist, so no egress restriction is expressible
#: here and none is invented.
EGRESS_RESTRICTIONS_NOTE = (
    "not expressible: no egress-authority package exists in this repository, so this "
    "seam records declared use and restricts nothing"
)


class DeclarationService:
    """Typed intake over the deployment's ``SqliteDataUseDeclarations`` (FD-12).

    The tenant is the store's, never the caller's. The declaration id is derived by
    the package, never chosen. Every field is validated by data-use-admission's own
    refusal reasons; the classification, purpose and residency labels are recorded
    uninterpreted (DE-2, DE-3); a superseding declaration is admitted only by
    ``supersession_refusals``. The only write is ``declare`` (FD-12.5): there is no
    edit, revocation, admission, verification, scoring or enforcement, and the record
    carries an opaque ``data_ref`` and never the data.
    """

    CAPABILITY = "data_use_declarations"

    def __init__(self, declarations: Any = None, recorded_by: str = "") -> None:
        self._declarations = declarations
        self._recorded_by = recorded_by

    def _gap(self) -> Dict[str, Any]:
        return _unavailable(
            self.CAPABILITY,
            "no data-use declarations file is configured: this deployment holds no "
            "declarations file, so nothing can be recorded or listed",
        )

    @staticmethod
    def _refused(code: str, message: str) -> Dict[str, Any]:
        return {"available": True, "refused": True, "code": code, "reason": message, "result": None}

    def declare(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self._declarations is None:
            return self._gap()
        tenant_id = self._declarations.tenant_id
        try:
            binding_input = dict(payload.get("binding") or {})
            if "tenant_id" in binding_input:
                return self._refused("declaration_refused",
                                     "tenant_id is the deployment's and is never caller-supplied")
            binding = declaration_binding_from_dict({**binding_input, "tenant_id": tenant_id})
            validity_input = dict(payload.get("validity") or {})
            for name in ("issued_at", "expires_at", "stale_after"):
                raw = validity_input.get(name)
                if raw in (None, ""):
                    continue
                if not isinstance(raw, str) or _instant(raw) is None:
                    return self._refused(
                        "declaration_refused",
                        f"validity.{name} must be an ISO-8601 instant with a timezone")
            validity = declaration_validity_from_dict(validity_input)
            if validity is None:
                return self._refused("declaration_refused", "validity is required")
            classification = DataClassificationLabel(payload.get("classification_label", ""))
            data_ref = payload.get("data_ref", "")
            purpose_label = payload.get("purpose_label", "")
            declaration = DataUseDeclaration(
                declaration_id=declaration_id_for(binding, data_ref, classification,
                                                  purpose_label, validity),
                tenant_id=tenant_id,
                binding=binding,
                data_ref=data_ref,
                classification=classification,
                purpose_label=purpose_label,
                validity=validity,
                residency_label=payload.get("residency_label", "") or "",
                supersedes=payload.get("supersedes", "") or "",
                declared_by=payload.get("declared_by", "") or "",
                correlation_id=payload.get("correlation_id", "") or "",
                notes=payload.get("notes", "") or "",
            )
        except DeclarationContractViolation as exc:
            return self._refused("declaration_refused", str(exc))
        except (TypeError, ValueError) as exc:
            return self._refused("declaration_refused", f"typed input refused: {exc}")
        try:
            self._declarations.declare(declaration)
        except DuplicateDeclarationError as exc:
            return self._refused("declaration_duplicate", str(exc))
        except DeclarationSupersessionError as exc:
            return self._refused("supersession_refused", str(exc))
        except DeclarationCrossTenantRefused as exc:
            return self._refused("declaration_refused", str(exc))
        except DeclarationStorageError as exc:
            return _unavailable(self.CAPABILITY,
                                f"the declarations file could not be written: {exc}")
        record = declaration_record(declaration)
        return {
            "available": True,
            "declared": True,
            "tenant_id": tenant_id,
            "store_kind": type(self._declarations).__name__,
            "record": record,
            "record_digest": declaration.record_digest(),
            "declaration_id": declaration.declaration_id,
            "declared_by": declaration.declared_by,
            "declared_by_status": DECLARED_BY_STATUS,
            "recorded_by": self._recorded_by,
            "confers": DECLARATION_CONFERS,
            "egress_restrictions": EGRESS_RESTRICTIONS_NOTE,
            "result": record,
        }

    def list(self, *, as_of: Optional[str]) -> Dict[str, Any]:
        if self._declarations is None:
            return self._gap()
        tenant_id = self._declarations.tenant_id
        if as_of is None:
            instant = datetime.now(timezone.utc)
            source = "request"
        else:
            parsed = _instant(as_of) if isinstance(as_of, str) else None
            if parsed is None:
                return self._refused("as_of_untyped",
                                     "as_of must be an ISO-8601 instant with a timezone")
            instant = parsed
            source = "caller"
        try:
            declarations = self._declarations.declarations_for_tenant(
                tenant_id=tenant_id, as_of=instant)
        except DeclarationCrossTenantRefused as exc:
            return self._refused("declaration_refused", str(exc))
        except (DeclarationStorageError, DeclarationContractViolation) as exc:
            return _unavailable(self.CAPABILITY,
                                f"the declarations file could not be read: {exc}")
        records = [declaration_record(d) for d in declarations]
        return {
            "available": True,
            "tenant_id": tenant_id,
            "store_kind": type(self._declarations).__name__,
            "as_of": instant.isoformat(),
            "as_of_source": source,
            "count": len(records),
            "declared_by_status": DECLARED_BY_STATUS,
            "recorded_by": self._recorded_by,
            "confers": DECLARATION_CONFERS,
            "egress_restrictions": EGRESS_RESTRICTIONS_NOTE,
            "result": records,
        }


# --------------------------------------------------------------------------- #
# Screen 5b · Vendor dependencies (front-door seam 9, FD-13)
# --------------------------------------------------------------------------- #
#: FD-13.4: the posture is what the declarer called it. Nothing here or anywhere in
#: this repository orders, compares, ranks or scores it, and no approval or
#: onboarding status exists to show beside it.
VENDOR_RISK_POSTURE_NOTE = (
    "uninterpreted: the posture is recorded exactly as the declarer typed it and is "
    "ordered, compared, ranked and scored nowhere; no vendor approval, onboarding "
    "status, tier or certification is implied, because no package computes one"
)
VENDOR_DECLARATION_CONFERS = (
    "nothing: a vendor declaration is a record of what a declarer asserted, not an "
    "approval, an onboarding decision or a permission (vendor-risk ADR VR-1, FD-13.4)"
)


class VendorDeclarationService:
    """Typed intake over the deployment's ``SqliteVendorDeclarations`` (FD-13).

    The tenant is the store's, never the caller's. The declaration id is derived by
    the package, never chosen. Every field is validated by vendor-dependency's own
    refusal reasons; the risk posture is recorded uninterpreted (VR-3, FD-13.4) and
    the ``policy_ref`` recorded and never resolved (VR-4); a superseding declaration
    is admitted only by ``supersession_refusals``. The only write is ``declare``
    (FD-13.4): there is no edit, revocation, approval, onboarding, verification,
    scoring or enforcement, and the record carries an opaque ``vendor_ref`` and never
    a way to reach the vendor.
    """

    CAPABILITY = "vendor_declarations"

    def __init__(self, declarations: Any = None, recorded_by: str = "") -> None:
        self._declarations = declarations
        self._recorded_by = recorded_by

    def _gap(self) -> Dict[str, Any]:
        return _unavailable(
            self.CAPABILITY,
            "no vendor declarations file is configured: this deployment holds no "
            "vendor declarations file, so nothing can be recorded or listed",
        )

    @staticmethod
    def _refused(code: str, message: str) -> Dict[str, Any]:
        return {"available": True, "refused": True, "code": code, "reason": message, "result": None}

    def declare(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self._declarations is None:
            return self._gap()
        tenant_id = self._declarations.tenant_id
        try:
            binding_input = dict(payload.get("binding") or {})
            if "tenant_id" in binding_input:
                return self._refused("vendor_declaration_refused",
                                     "tenant_id is the deployment's and is never caller-supplied")
            binding = vendor_binding_from_dict({**binding_input, "tenant_id": tenant_id})
            validity_input = dict(payload.get("validity") or {})
            for name in ("issued_at", "expires_at", "stale_after"):
                raw = validity_input.get(name)
                if raw in (None, ""):
                    continue
                if not isinstance(raw, str) or _instant(raw) is None:
                    return self._refused(
                        "vendor_declaration_refused",
                        f"validity.{name} must be an ISO-8601 instant with a timezone")
            validity = vendor_validity_from_dict(validity_input)
            if validity is None:
                return self._refused("vendor_declaration_refused", "validity is required")
            posture = VendorRiskLabel(payload.get("risk_posture_label", ""))
            vendor_ref = payload.get("vendor_ref", "")
            policy_ref = payload.get("policy_ref", "")
            declaration = VendorDependencyDeclaration(
                declaration_id=vendor_declaration_id_for(binding, vendor_ref, posture,
                                                         policy_ref, validity),
                tenant_id=tenant_id,
                binding=binding,
                vendor_ref=vendor_ref,
                risk_posture=posture,
                policy_ref=policy_ref,
                validity=validity,
                supersedes=payload.get("supersedes", "") or "",
                declared_by=payload.get("declared_by", "") or "",
                correlation_id=payload.get("correlation_id", "") or "",
                notes=payload.get("notes", "") or "",
            )
        except VendorContractViolation as exc:
            return self._refused("vendor_declaration_refused", str(exc))
        except (TypeError, ValueError) as exc:
            return self._refused("vendor_declaration_refused", f"typed input refused: {exc}")
        try:
            self._declarations.declare(declaration)
        except DuplicateVendorDeclarationError as exc:
            return self._refused("vendor_declaration_duplicate", str(exc))
        except VendorSupersessionError as exc:
            return self._refused("supersession_refused", str(exc))
        except VendorCrossTenantRefused as exc:
            return self._refused("vendor_declaration_refused", str(exc))
        except VendorStorageError as exc:
            return _unavailable(self.CAPABILITY,
                                f"the vendor declarations file could not be written: {exc}")
        record = vendor_declaration_record(declaration)
        return {
            "available": True,
            "declared": True,
            "tenant_id": tenant_id,
            "store_kind": type(self._declarations).__name__,
            "record": record,
            "record_digest": declaration.record_digest(),
            "declaration_id": declaration.declaration_id,
            "declared_by": declaration.declared_by,
            "declared_by_status": DECLARED_BY_STATUS,
            "recorded_by": self._recorded_by,
            "risk_posture": VENDOR_RISK_POSTURE_NOTE,
            "confers": VENDOR_DECLARATION_CONFERS,
            "result": record,
        }

    def list(self, *, as_of: Optional[str]) -> Dict[str, Any]:
        if self._declarations is None:
            return self._gap()
        tenant_id = self._declarations.tenant_id
        if as_of is None:
            instant = datetime.now(timezone.utc)
            source = "request"
        else:
            parsed = _instant(as_of) if isinstance(as_of, str) else None
            if parsed is None:
                return self._refused("as_of_untyped",
                                     "as_of must be an ISO-8601 instant with a timezone")
            instant = parsed
            source = "caller"
        try:
            declarations = self._declarations.declarations_for_tenant(
                tenant_id=tenant_id, as_of=instant)
        except VendorCrossTenantRefused as exc:
            return self._refused("vendor_declaration_refused", str(exc))
        except (VendorStorageError, VendorContractViolation) as exc:
            return _unavailable(self.CAPABILITY,
                                f"the vendor declarations file could not be read: {exc}")
        records = [vendor_declaration_record(d) for d in declarations]
        return {
            "available": True,
            "tenant_id": tenant_id,
            "store_kind": type(self._declarations).__name__,
            "as_of": instant.isoformat(),
            "as_of_source": source,
            "count": len(records),
            "declared_by_status": DECLARED_BY_STATUS,
            "recorded_by": self._recorded_by,
            "risk_posture": VENDOR_RISK_POSTURE_NOTE,
            "confers": VENDOR_DECLARATION_CONFERS,
            "result": records,
        }


#: CE-1, stated on every answer. Exporting is not clearing: this service copies a
#: clearance the deployment received and mints nothing.
EXPORT_IS_NOT_CLEARING = (
    "EXPORT_IS_A_READ: this operation returns a copy of a clearance the deployment "
    "already received. It does not evaluate, grant, sign, approve or clear anything, "
    "and holding the artifact confers nothing."
)

#: §13.1, stated on every answer alongside the artifact's own three labels. The
#: service repeats it rather than relying on a reader opening the artifact.
EXPORT_CONFERS = (
    "NOTHING: a seeded receipt exercises the export path and the verifier. No "
    "authority granted it, it satisfies no obligation, and it is not evidence that "
    "any action may proceed."
)


class ClearanceExportService:
    """The one v2 read CE-5 ruled: the export artifact for a clearance already held.

    **A read, structurally.** The deployment hands this service a
    ``ReceivedClearanceSource``, whose port has two reads and no write, so there is no
    method here that could accept, store or mint a clearance (CE-5, §13.3). The
    service never constructs a ``ClearanceResult``: it reads a receipt somebody else
    evaluated and wraps it.

    **Three ceilings travel, and the service re-states them.** ``build_export``
    already refuses any artifact that omits or softens ``PRESENTED_UNPROVEN``,
    ``UNSIGNED`` or ``SYNTHETIC_DEMONSTRATION_ONLY``; this service passes exactly
    those three and echoes them in its own answer, so a caller reading only the
    envelope still sees all three.

    **A missing source is reported, never faked.** Absent a source the operation
    returns a typed ``unavailable`` naming the gap, rather than an empty list that
    would read as "this tenant holds no clearances".
    """

    CAPABILITY = "clearance_export"

    def __init__(self, source: Any = None, tenant_id: str = "") -> None:
        self._source = source
        self._tenant_id = tenant_id

    def _gap(self) -> Dict[str, Any]:
        return _unavailable(
            self.CAPABILITY,
            "no received-clearance source is configured: this deployment holds no "
            "clearance receipts, so there is nothing to export",
        )

    @staticmethod
    def _refused(code: str, message: str) -> Dict[str, Any]:
        return {"available": True, "refused": True, "code": code, "reason": message,
                "result": None}

    def read(self, *, receipt_id: str) -> Dict[str, Any]:
        """Return the export artifact for one clearance this deployment already holds.

        Unknown ids are refused typed, never 404-shaped as an empty success: "the
        deployment holds no such clearance" and "the deployment holds no clearances"
        must not look alike to an external runtime.
        """
        if self._source is None:
            return self._gap()
        if not isinstance(receipt_id, str) or not receipt_id.strip():
            return self._refused("receipt_id_untyped",
                                 "receipt_id must be a non-empty string")
        tenant_id = self._tenant_id
        try:
            body = self._source.read_receipt(
                tenant_id=tenant_id, receipt_id=receipt_id.strip())
        except ClearanceExportError as exc:
            return self._refused("clearance_export_refused", str(exc))
        except (OSError, ValueError) as exc:
            return _unavailable(
                self.CAPABILITY,
                f"the received-clearance source could not be read: {exc}")
        if body is None:
            return self._refused(
                "clearance_not_held",
                f"this deployment holds no clearance receipt {receipt_id.strip()!r}")

        try:
            artifact = build_export(
                body,
                identity_assurance=IdentityAssurance.PRESENTED_UNPROVEN,
                authenticity=ExportAuthenticity.UNSIGNED,
                data_classification=(
                    ExportDataClassification.SYNTHETIC_DEMONSTRATION_ONLY),
            )
            verification = verify_export(artifact)
        except ExportIntegrityError as exc:
            return self._refused("clearance_export_integrity_refused", str(exc))
        except (ExportContractViolation, ClearanceExportError) as exc:
            return self._refused("clearance_export_refused", str(exc))

        record = artifact_to_dict(artifact)
        return {
            "available": True,
            "tenant_id": tenant_id,
            "source_kind": type(self._source).__name__,
            "artifact_id": artifact.artifact_id,
            "receipt_id": artifact.receipt_id,
            "identity_assurance": artifact.identity_assurance.value,
            "authenticity": artifact.authenticity.value,
            "authenticity_prerequisite": artifact.authenticity_prerequisite,
            "data_classification": artifact.data_classification.value,
            "integrity_verified": verification.integrity_verified,
            "uncheckable": list(verification.uncheckable),
            "export_is_not_clearing": EXPORT_IS_NOT_CLEARING,
            "confers": EXPORT_CONFERS,
            "artifact": record,
            "result": record,
        }
