#!/usr/bin/env python3
"""Reproducible independent-packaging proof for ``ugence-agentic-proposer`` (S1).

Builds the wheel + sdist, audits wheel contents, installs the wheel into a fresh
virtualenv with NO monorepo path, and proves the S1 contract surface behaves
outside the repository:

  1. build wheel + sdist and record artifact hashes;
  2. audit wheel contents — only ``ugence_agentic_proposer`` source + metadata;
     ``py.typed`` present, every S1 module present; NO tests/docs; NO foreign
     Ugence package bundled;
  3. build the ``ugence-jcs`` dependency wheel from the sibling package into a local
     wheelhouse, clean-install this wheel against it and, with no ``/symbolu`` on
     ``sys.path``: read the version, exercise the ratified D4 vocabulary, assert
     the public surface is exactly the full H3 surface as amended by OD-7
     (``public_api.json``), build a complete advisory end to end — including a
     domain evaluation through a locally declared stub provider and the ratified
     deterministic selection — through the real installed ``ugence-jcs`` dependency,
     verify its identity and replay both, confirm a drifted provider refuses
     construction, and assert that importing the public API
     loads none of the forbidden capability, legacy-framework, network or
     model-SDK modules — the same boundary the source-tree suite proves statically;
  4. report wheel reproducibility honestly.

Run:  python packages/capabilities/agentic-proposer/verify_agentic_proposer_distribution.py
Exit 0 on success; non-zero on the first failed step.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parent
#: ugence-jcs is a core dependency and is not published to an index, so the clean
#: install resolves it from a locally built wheel. Building it here also proves the
#: declared dependency is satisfiable rather than aspirational.
JCS_PKG = PKG.parents[1] / "jcs"

#: A fixed timestamp so wheel zip entries are deterministic (bit-for-bit builds).
_BUILD_ENV = {**os.environ, "SOURCE_DATE_EPOCH": "1704067200", "PYTHONHASHSEED": "0"}

CLEAN_INSTALL_CHECK = r'''
import sys
from datetime import datetime, timezone
import ugence_agentic_proposer as ap

assert ap.__version__ == "0.3.0", ap.__version__
assert "site-packages" in ap.__file__, ap.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path

# --- ratified D4 vocabulary ---
assert {m.value for m in ap.TerminalOutcome} == {
    "PROPOSAL", "NEED_EVIDENCE", "ABSTAIN", "ESCALATE"}
assert {m.value for m in ap.CandidateDisposition} == {
    "RECOMMEND_MATCHED_FOR_APPROVAL", "RECOMMEND_WITHHOLD",
    "REQUEST_EVIDENCE", "ESCALATE_EXCEPTION"}
assert {m.value for m in ap.SemanticAuditorFindingStatus} == {
    "CONSISTENT", "INCONSISTENT", "INDETERMINATE", "CONFLICTING"}

# No outcome or disposition is a reserved authority claim.
reserved = ap.RESERVED_AUTHORITY_VOCABULARY
assert not {m.value for m in ap.TerminalOutcome} & reserved
assert not {m.value for m in ap.CandidateDisposition} & reserved
# INDETERMINATE is reserved in those two positions and ratified only for the auditor.
assert "INDETERMINATE" in reserved
assert ap.SemanticAuditorFindingStatus.INDETERMINATE.value == "INDETERMINATE"

# The public surface is exactly the full H3 surface as amended by OD-7 and by S2-B
# (I6, I8): 8 contracts, 2 nested public shapes, 4 call-boundary shapes, 2 injected
# protocols, 12 enums, 5 builders, 2 equation functions, 2 identity functions,
# 6 verifiers, 3 exceptions, 4 constants, __version__ = 51 names. The thirty-nine
# 0.1.0 froze are all still here; neither 0.2.0 nor 0.3.0 removes any of them
# (`S2B-S1-Q6=A`: no removals, no renames).
EXPECTED_SURFACE = {
    "AgentIdentityRef", "CognitiveRoleContract", "WorkMandate",
    "BoundedContextEnvelope", "ToolObservation", "AdvisoryCandidateSet",
    "ProposerAdvisory", "ProposerProcessRecord",
    "CandidateAdvisory", "ProposerProcessStateTransition",
    "DomainEvaluationRequest", "DomainEvaluationResponse", "DomainEvaluationProvider",
    "StrategyPolicyRequest", "StrategyPolicyResponse", "StrategyPolicyResolver",
    "TerminalOutcome", "CandidateDisposition", "SemanticAuditorFindingStatus",
    "ReviewAction", "DomainCheckCompletion", "AgentLifecycleState",
    "RoleActivationStatus", "ToolOperationClass", "ToolObservationAdmissionStatus",
    "ProposerProcessState", "DomainEvaluationOutcome", "ReasoningStrategy",
    "build_candidate_advisory", "build_advisory_candidate_set",
    "build_proposer_advisory", "build_advisory_revision",
    "build_proposer_process_record",
    "evaluate_eligibility", "evaluate_readiness",
    "compute_advisory_identity", "verify_advisory_identity",
    "verify_candidate_eligibility", "verify_advisory_selection",
    "verify_observation_resolution", "verify_domain_evaluation",
    "verify_deterministic_selection", "verify_strategy_permission",
    "EligibilityMismatchError", "CrossContractViolationError",
    "DomainEvaluationProviderError",
    "RESERVED_AUTHORITY_VOCABULARY", "ADVISORY_KIND",
    "ADVISORY_IDENTITY_SET_PATHS", "ADVISORY_IDENTITY_NFC_PATHS",
    "__version__",
}
assert set(ap.__all__) == EXPECTED_SURFACE, ap.__all__
assert len(EXPECTED_SURFACE) == 51
assert not any(n.startswith(("Proposal", "Recommendation")) for n in ap.__all__)

# --- a complete advisory, built end to end through the installed ugence-jcs wheel ---
NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
LATER = datetime(2027, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
identity = ap.AgentIdentityRef(
    schema_version="1.0", tenant_id="t", created_at=NOW, agent_id="a",
    agent_version="1.0.0", lifecycle_state=ap.AgentLifecycleState.ACTIVE,
    bound_role_contract_id="r", owner_role_ref="ro")
role = ap.CognitiveRoleContract(
    schema_version="1.0", tenant_id="t", created_at=NOW, role_contract_id="r",
    primary_function="reconcile", permitted_tool_scopes=["tool"],
    permitted_candidate_dispositions=[ap.CandidateDisposition.RECOMMEND_WITHHOLD],
    permitted_review_actions=[ap.ReviewAction.ROUTE_APPROVAL_BUNDLE],
    escalation_role_ref="r2", activation_status=ap.RoleActivationStatus.ACTIVE,
    strategy_policy_ref="policy-authority/strategy-permission/v0")
mandate = ap.WorkMandate(
    schema_version="1.0", tenant_id="t", created_at=NOW, mandate_id="m",
    case_ref="c", assigned_role_contract_id="r", purpose="reconcile",
    allowed_source_scopes=["scope"], expires_at=LATER)
context = ap.BoundedContextEnvelope(
    schema_version="1.0", tenant_id="t", created_at=NOW, context_id="ctx",
    mandate_id="m", allowed_record_refs=["rec"], excluded_data_classes=[],
    context_hash="sha256:" + "0" * 64, expires_at=LATER)
observation = ap.ToolObservation(
    schema_version="1.0", tenant_id="t", created_at=NOW, observation_id="obs",
    case_ref="c", tool_name="tool", operation_class=ap.ToolOperationClass.READ_ONLY,
    source_ref="rec", observed_at=NOW, content_hash="sha256:" + "0" * 64,
    normalized_fields={})
# OD-7's injected evaluator: a stub declared here, in the clean interpreter, because
# no evaluator ships in this wheel and none may. It satisfies the exported protocol
# and computes nothing about any business domain — which is the boundary working.
class _Stub:
    def evaluate(self, *, request):
        return ap.DomainEvaluationResponse(
            candidate_id=request.candidate_id,
            profile_id=request.profile_id,
            profile_version=request.profile_version,
            outcome=ap.DomainEvaluationOutcome.SATISFIED)


provider = _Stub()
assert isinstance(provider, ap.DomainEvaluationProvider)
# S2-B's injected resolver: a stub declared here, in the clean interpreter, for exactly
# the reason the evaluator stub is. No strategy policy ships in this wheel and none may
# — `S2B-D1=A` excludes this capability as an issuer — and no strategy-permission family
# is registered with Policy Authority at all, which blocks execution end to end. The
# protocol being injected is what lets the wheel still prove itself.
class _PolicyStub:
    def resolve(self, *, request):
        return ap.StrategyPolicyResponse(
            strategy_policy_id="ugence.strategy_permission.v0",
            strategy_policy_version="v1",
            permitted_strategies=tuple(ap.ReasoningStrategy),
            strategy_policy_ref=request.strategy_policy_ref)


resolver = _PolicyStub()
assert isinstance(resolver, ap.StrategyPolicyResolver)
candidate = ap.build_candidate_advisory(
    candidate_id="cand", identity=identity, role=role, mandate=mandate,
    context=context, observations=[observation],
    disposition=ap.CandidateDisposition.RECOMMEND_WITHHOLD,
    requested_review_action=ap.ReviewAction.ROUTE_APPROVAL_BUNDLE,
    observation_refs=[], claim_refs=[], assumptions=[], uncertainties=[],
    evaluated_at=NOW, provider=provider, profile_id="profile.v0",
    profile_version="1.0.0")
assert candidate.is_eligible is True
assert candidate.domain_check_completion is ap.DomainCheckCompletion.COMPLETE
assert candidate.domain_evaluation_outcome is ap.DomainEvaluationOutcome.SATISFIED
# Selection-policy v1: exactly one qualifying candidate, so it is selected (OD-8).
candidate_set = ap.build_advisory_candidate_set(
    candidate_set_id="set", tenant_id="t", case_ref="c", created_at=NOW,
    candidates=(candidate,), selected_candidate_id="cand",
    domain_evaluation_profile_id="profile.v0",
    domain_evaluation_profile_version="1.0.0")
advisory = ap.build_proposer_advisory(
    tenant_id="t", case_ref="c", created_at=NOW, identity=identity, role=role,
    mandate=mandate, context=context, observations=[observation],
    candidate_set=candidate_set, parent_advisory_digest=None, claim_summaries=[],
    observation_refs=[], uncertainties=[], expires_at=LATER, provider=provider,
    expected_profile_id="profile.v0", expected_profile_version="1.0.0",
    requested_review_destination_role_ref="role-approver",
    strategy_policy_resolver=resolver,
    declared_strategy=ap.ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED)
assert ap.verify_advisory_identity(advisory=advisory) is True
assert advisory.selected_candidate_id == "cand"
assert ap.verify_advisory_selection(
    advisory=advisory, candidate_set=candidate_set, role=role, context=context,
    observations=[observation]) is True
assert ap.verify_deterministic_selection(candidate_set=candidate_set) is True
assert ap.verify_domain_evaluation(
    provider=provider, candidate_set=candidate_set, mandate=mandate, context=context,
    observations=[observation], expected_profile_id="profile.v0",
    expected_profile_version="1.0.0") is True
# The fail-closed direction, in the same clean interpreter: a provider that no longer
# reproduces the stored outcome refuses construction (OD-7 part 7, row 2).
class _Drifted:
    def evaluate(self, *, request):
        return ap.DomainEvaluationResponse(
            candidate_id=request.candidate_id, profile_id=request.profile_id,
            profile_version=request.profile_version,
            outcome=ap.DomainEvaluationOutcome.NOT_SATISFIED)


try:
    ap.build_proposer_advisory(
        tenant_id="t", case_ref="c", created_at=NOW, identity=identity, role=role,
        mandate=mandate, context=context, observations=[observation],
        candidate_set=candidate_set, parent_advisory_digest=None, claim_summaries=[],
        observation_refs=[], uncertainties=[], expires_at=LATER, provider=_Drifted(),
        expected_profile_id="profile.v0", expected_profile_version="1.0.0",
        requested_review_destination_role_ref="role-approver",
        strategy_policy_resolver=resolver,
        declared_strategy=ap.ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED)
except ap.DomainEvaluationProviderError:
    pass
else:
    raise AssertionError("a drifted provider did not refuse construction")

# --- S2-B: the strategy-permission replay, in the same clean interpreter ---
# The advisory binds its governing policy identity, its version and the declared
# strategy (`S2B-D6=B1`), and the process record derives its declaration and its digest
# reference from that advisory (rider `R1`). Replay then re-establishes both across two
# independently held artifacts.
assert advisory.strategy_policy_id == "ugence.strategy_permission.v0"
assert advisory.strategy_policy_version == "v1"
assert advisory.declared_strategy is ap.ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED
record = ap.build_proposer_process_record(
    process_record_id="rec", tenant_id="t", case_ref="c", created_at=NOW,
    advisory=advisory, state_transitions=[], tool_invocations=[],
    candidate_ids=["cand"], selected_candidate_id="cand",
    terminal_outcome=ap.TerminalOutcome.PROPOSAL, started_at=NOW, completed_at=NOW)
assert record.declared_strategy is advisory.declared_strategy
assert record.advisory_digest == advisory.advisory_digest
policy = ap.StrategyPolicyResponse(
    strategy_policy_id="ugence.strategy_permission.v0", strategy_policy_version="v1",
    permitted_strategies=tuple(ap.ReasoningStrategy),
    strategy_policy_ref="policy-authority/strategy-permission/v0")
assert ap.verify_strategy_permission(
    advisory=advisory, policy=policy, role=role, process_record=record) is True
# The fail-closed direction: a policy permitting nothing. Replay returns False and
# raises nothing — `S2B-D5=A`'s structural result, with no disposition emitted.
assert ap.verify_strategy_permission(
    advisory=advisory,
    policy=ap.StrategyPolicyResponse(
        strategy_policy_id="ugence.strategy_permission.v0",
        strategy_policy_version="v1", permitted_strategies=(),
        strategy_policy_ref="policy-authority/strategy-permission/v0"),
    role=role, process_record=record) is False
# And construction refuses when the resolver permits nothing (`S2B-D5=A`): no
# identity-bearing artifact is produced, through an existing H2 class (`Q8=A`).
class _PermitsNothing:
    def resolve(self, *, request):
        return ap.StrategyPolicyResponse(
            strategy_policy_id="ugence.strategy_permission.v0",
            strategy_policy_version="v1", permitted_strategies=(),
            strategy_policy_ref=request.strategy_policy_ref)


try:
    ap.build_proposer_advisory(
        tenant_id="t", case_ref="c", created_at=NOW, identity=identity, role=role,
        mandate=mandate, context=context, observations=[observation],
        candidate_set=candidate_set, parent_advisory_digest=None, claim_summaries=[],
        observation_refs=[], uncertainties=[], expires_at=LATER, provider=provider,
        expected_profile_id="profile.v0", expected_profile_version="1.0.0",
        requested_review_destination_role_ref="role-approver",
        strategy_policy_resolver=_PermitsNothing(),
        declared_strategy=ap.ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED)
except ap.CrossContractViolationError:
    pass
else:
    raise AssertionError("an unpermitted declaration did not refuse construction")

# --- leaf boundary, observed at runtime in a clean interpreter ---
# OD-2: *defining* a pydantic BaseModel loads `socket` via pydantic-core's schema
# build, even though bare `import pydantic` does not; every contract above already
# defined several. So the boundary this process checks is the one OD-2 ratifies —
# no module beyond what the approved `pydantic` dependency itself would already have
# loaded by this point in *this same process* — not a bare "socket never loads"
# assertion, which the S0-era version of this check made and which S1 falsifies for
# a reason unrelated to this package's authority (test_boundaries.py's layered
# design is the source of truth; this mirrors its baseline-comparison shape).
FORBIDDEN = {"agentic", "agent_runtime_migration", "ugence_agent_runtime",
             "ugence_decision_authority", "ugence_actiongate_provider",
             "ugence_action_clearance", "ugence_storygraph",
             "ugence_agent_workforce_composer", "ugence_policy_workflow_compiler",
             "cer_v0_1", "cer_v0_2", "cer_v0_3", "action_gate_ref",
             "control_plane", "cloud_controller",
             "requests", "httpx", "openai", "anthropic"}
loaded = {m.split(".")[0] for m in sys.modules}
assert not (loaded & FORBIDDEN), sorted(loaded & FORBIDDEN)
# `socket` is expected here — pydantic-core's schema build loads it the moment a
# BaseModel is defined, which every contract above already did — and is asserted
# present rather than absent, so a future pydantic release that stops loading it
# is noticed rather than silently making this assertion vacuous.
assert "socket" in sys.modules, (
    "pydantic no longer loads socket on model definition; the OD-2 exemption this "
    "check carries forward may no longer be needed")

print("S1_OK:" + ap.__version__)
'''

FORBIDDEN_WHEEL_SUBSTRINGS = ("agentic_framework", "agent_runtime", "cer_v0_",
                              "action_gate", "control_plane", "cloud_controller",
                              "ugence_jcs", "/tests/", "conftest", "/docs/")

#: Every module the S1 wheel must ship, so a build that silently dropped one of
#: the five new modules is caught here rather than by a downstream ImportError.
REQUIRED_WHEEL_MODULES = (
    "vocabulary.py", "contracts.py", "identity.py", "equations.py",
    "verification.py", "builders.py",
)


def _run(cmd, **kw):
    print("  $", " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, check=True, **kw)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build(outdir: Path) -> tuple[Path, Path]:
    _run([sys.executable, "-m", "build", "--outdir", str(outdir), str(PKG)], env=_BUILD_ENV)
    wheels = list(outdir.glob("*.whl"))
    sdists = list(outdir.glob("*.tar.gz"))
    assert wheels and sdists, "build did not produce wheel + sdist"
    return wheels[0], sdists[0]


def _audit_wheel(wheel: Path) -> None:
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    assert any(n.endswith("ugence_agentic_proposer/py.typed") for n in names), \
        "py.typed missing from wheel"
    for module in REQUIRED_WHEEL_MODULES:
        assert any(n.endswith(f"ugence_agentic_proposer/{module}") for n in names), \
            f"{module} missing from wheel"
    for name in names:
        low = name.lower()
        if not (low.startswith("ugence_agentic_proposer/")
                or low.startswith("ugence_agentic_proposer-")):
            raise AssertionError(f"foreign wheel entry {name!r}")
        for bad in FORBIDDEN_WHEEL_SUBSTRINGS:
            assert bad not in low, f"forbidden wheel content {name!r} (matched {bad!r})"
    print("  wheel audit OK:", len(names), "entries; py.typed present; no foreign content")


def main() -> int:
    print("== build ==")
    work = Path(tempfile.mkdtemp(prefix="agentic_proposer_dist_"))
    try:
        dist1 = work / "dist1"
        wheel1, sdist1 = _build(dist1)
        print("  wheel:", wheel1.name, _sha256(wheel1)[:16])
        print("  sdist:", sdist1.name, _sha256(sdist1)[:16])

        print("== wheel content audit ==")
        _audit_wheel(wheel1)

        print("== clean-install outside the repo ==")
        env_dir = work / "venv"
        venv.create(env_dir, with_pip=True)
        py = env_dir / "bin" / "python"
        # ugence-jcs is unpublished; build it from the sibling package so the declared
        # dependency resolves from a real wheel rather than being skipped.
        wheelhouse = work / "wheelhouse"
        _run([sys.executable, "-m", "build", "--outdir", str(wheelhouse), str(JCS_PKG)],
             env=_BUILD_ENV, stdout=subprocess.DEVNULL)
        _run([str(py), "-m", "pip", "install", "--quiet",
              "--find-links", str(wheelhouse), str(wheel1)])
        # ugence-jcs installs and reports a version on its own, independent of
        # whether the proposer package's own identity module ends up using it —
        # CLEAN_INSTALL_CHECK below is what proves the latter.
        _run([str(py), "-c", "import ugence_jcs; assert ugence_jcs.__version__"],
             stdout=subprocess.DEVNULL)

        for i in (1, 2):  # two SEPARATE processes
            res = _run([str(py), "-c", CLEAN_INSTALL_CHECK], capture_output=True, text=True)
            line = [l for l in res.stdout.splitlines() if l.startswith("S1_OK:")][0]
            print(f"  process {i}: full H3 surface + domain evaluation + selection "
                 f"+ advisory identity + leaf boundary OK ({line[6:]})")

        print("== reproducibility ==")
        dist2 = work / "dist2"
        wheel2, sdist2 = _build(dist2)
        print(f"  wheel bit-for-bit reproducible: {_sha256(wheel1) == _sha256(wheel2)}")
        print(f"  sdist bit-for-bit reproducible: {_sha256(sdist1) == _sha256(sdist2)} "
              f"(content-stable; gzip mtime may vary)")

        print("\nARTIFACT HASHES")
        print("  wheel:", _sha256(wheel1))
        print("  sdist:", _sha256(sdist1))
        print("\nAGENTIC_PROPOSER_S1_DISTRIBUTION_VERIFIED")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
