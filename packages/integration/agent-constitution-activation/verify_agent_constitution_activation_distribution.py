#!/usr/bin/env python3
"""Reproducible proof that the issuance & activation distribution installs and
operates from built wheels, against installed distributions and no monorepo path.

Builds this distribution and every first-party dependency into a local
wheelhouse, installs the activation wheel **offline** into a fresh virtualenv
with no system site packages — which pulls the conformance and family wheels in
as declared dependencies — and then proves *inside that environment*:

  * ``ugence_agent_constitution_activation``, the conformance distribution and
    the family distribution import from site-packages, all at 0.1.0, with no
    repository source on ``sys.path``, and the activation package ships
    ``py.typed``;
  * the composition root refuses an incomplete wiring, composes with the
    shipped deny-by-default verifiers, and the `ACC-S1-Q3` collision guard
    runs inside the installed environment;
  * on **ephemeral keys minted in-process** the full ratified chain runs:
    preflight (ready, mutation-free) → issue (receipted) → activate (the
    reference map derived from the issued record, receipted) → resolve (the
    exact signed artifact) → bind (the proposer's ratified builders stamp from
    the genuinely resolved constitution and the advisory identity replays) →
    conform (the predicate answers True inside the bounds, False outside the
    tool-scope ceiling);
  * the four-way fail-closed matrix refuses with typed errors: missing
    approval (nothing registered), missing trust (an unknown key at
    resolution), missing mapping, and a revoked policy;
  * every installed first-party distribution is exactly the version built here,
    and every loaded first-party module resolves under the clean venv;
  * no execution authority, console, product or unrelated package is importable.

**The installation is offline and pinned, and that is the point** — see the
conformance distribution's verify script for the full rationale; this script
follows it step for step, including the negative control that removes a
required first-party wheel and proves the installation refuses rather than
substituting.

The permissive approval verifier below exists only inside this script, for the
same reason the authority's own permissive verifiers exist only under
``tests/``: issuance must be exercised, and the shipped default is
deny-by-default. No distribution ships anything like it. The Ed25519 seeds are
drawn from process randomness at run time — nothing key-shaped exists in this
repository, and a re-run mints a different world.

Run:  python packages/integration/agent-constitution-activation/verify_agent_constitution_activation_distribution.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parent
REPO = PKG.parents[2]  # packages/integration/<pkg> -> packages/integration -> packages -> repo

DISTRIBUTION = "ugence-agent-constitution-activation"
NAMESPACE = "ugence_agent_constitution_activation"
CONFORMANCE_DISTRIBUTION = "ugence-agent-constitution-conformance"

#: Distribution names beginning with this prefix are this repository's own and
#: must never be resolved from an index: every one is built below, from source.
FIRST_PARTY_PREFIX = "ugence-"

#: The first-party wheel the negative control removes to prove the offline
#: installation refuses rather than substituting. The conformance distribution
#: is the natural victim: it is this distribution's own declared dependency.
NEGATIVE_CONTROL_VICTIM = CONFORMANCE_DISTRIBUTION

SOURCES = {
    NAMESPACE: PKG,
    "ugence_agent_constitution_conformance": (
        REPO / "packages" / "integration" / "agent-constitution-conformance"
    ),
    "ugence_agent_constitution_policy": (
        REPO / "packages" / "integration" / "agent-constitution-policy"
    ),
    "ugence_policy_authority": REPO / "packages" / "policy-authority",
    "ugence_uvi_policy_contracts": REPO / "packages" / "uvi-policy-contracts",
    "ugence_governance_contracts": REPO / "packages" / "governance-contracts",
    "ugence_agentic_proposer": REPO / "packages" / "capabilities" / "agentic-proposer",
    "ugence_jcs": REPO / "packages" / "jcs",
}

_CHECK = r'''
import importlib.util
import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone

import ugence_agent_constitution_activation as activation
import ugence_agent_constitution_conformance as conformance
import ugence_agent_constitution_policy as family
import ugence_agentic_proposer as ap

assert activation.__version__ == "0.1.0", activation.__version__
assert conformance.__version__ == "0.1.0", conformance.__version__
assert family.__version__ == "0.1.0", family.__version__
assert "site-packages" in activation.__file__, activation.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path

import pathlib as _pl
assert (_pl.Path(activation.__file__).resolve().parent / "py.typed").is_file()

from ugence_policy_authority.api import (
    GLOBAL_TENANT, AdapterRegistry, ApprovalEvidenceRef, ApprovalVerification,
    ApprovalVerificationStatus, DenyAllApprovalVerifier, Ed25519PolicySigner,
    InMemoryPolicyRegistry, KeyEntitlement, PolicyApprovalError, PolicyKeyRing,
    PolicyRevocationReasonCode, SigningKey, revoke_policy,
)

T_ISSUE = datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc)
T_LATER = T_ISSUE + timedelta(hours=1)

# -- the ratified ACC-FC content values --------------------------------------
POLICY_ID = "agent-constitution-ugence"
POLICY_VERSION = "1.0.0"
CONSTITUTION_REF = "ugence.agent-constitution/ugence/baseline/v1"
GOVERNED_ROLE_REF = "ugence.roles/ugence/invoice-reconciler/v1"
TOOL_SCOPES = ("invoice.read", "ledger.read")
DISPOSITIONS = tuple(sorted(m.value for m in ap.CandidateDisposition))
REVIEW_ACTIONS = tuple(sorted(m.value for m in ap.ReviewAction))

ADAPTER = family.AgentConstitutionPolicyFamilyAdapter()


def build_constitution():
    body = dict(
        agent_constitution_ref=CONSTITUTION_REF,
        governed_role_refs=(GOVERNED_ROLE_REF,),
        permitted_candidate_dispositions_bound=DISPOSITIONS,
        permitted_review_actions_bound=REVIEW_ACTIONS,
        permitted_tool_scopes_bound=TOOL_SCOPES)

    def metadata(digest):
        return family.AgentConstitutionPolicyMetadata(
            policy_id=POLICY_ID, version=POLICY_VERSION, content_digest=digest,
            scope=family.POLICY_SCOPE_GLOBAL,
            lifecycle_state=family.LIFECYCLE_APPROVED_ACTIVE,
            tenant_id=GLOBAL_TENANT, effective_from=T_ISSUE, effective_to=None)

    draft = family.AgentConstitutionPolicy(
        metadata=metadata(family.PLACEHOLDER_CONTENT_DIGEST), **body)
    digest = ADAPTER.describe(draft).body_digest()
    return family.AgentConstitutionPolicy(metadata=metadata(digest), **body)


class _ScriptApprovalVerifier:
    """Verification-script only: re-hashes evidence bytes it actually holds."""

    def __init__(self, artifacts):
        self.artifacts = artifacts

    def verify_approval(self, *, coordinate, policy_body_digest, approval, as_of):
        held = self.artifacts.get(approval.approval_ref)
        genuine = (held is not None
                   and hashlib.sha256(held).hexdigest() == approval.approval_digest)
        return ApprovalVerification(
            verified=genuine,
            status=(ApprovalVerificationStatus.APPROVED if genuine
                    else ApprovalVerificationStatus.UNVERIFIED),
            coordinate=coordinate, policy_body_digest=policy_body_digest,
            approving_authority_id=approval.approving_authority_id,
            approval_ref=approval.approval_ref,
            approval_digest=approval.approval_digest, verified_at=as_of)


def make_world(*, approval_verifier=None, key_in_ring=True):
    """Ephemeral custody, minted in-process: a re-run mints a different world."""

    signer = Ed25519PolicySigner(
        authority_id="ugence.policy-authority", key_id="issuance-key-1",
        signing_key=SigningKey.from_seed(os.urandom(32)))
    revoker = Ed25519PolicySigner(
        authority_id="ugence.policy-authority.revocation", key_id="revocation-key-1",
        signing_key=SigningKey.from_seed(os.urandom(32)))
    keys = [revoker.verification_key(entitlements=(KeyEntitlement.REVOKE_POLICY,))]
    if key_in_ring:
        keys.insert(0, signer.verification_key(
            entitlements=(KeyEntitlement.ISSUE_POLICY,)))
    ring = PolicyKeyRing(keys)
    artifact_bytes = os.urandom(48)
    evidence = ApprovalEvidenceRef(
        approval_ref="APPROVAL-RUNTIME-1",
        approval_digest=hashlib.sha256(artifact_bytes).hexdigest(),
        approving_authority_id="ugence.governance.policy-approval-board")
    verifier = (approval_verifier if approval_verifier is not None
                else _ScriptApprovalVerifier({evidence.approval_ref: artifact_bytes}))
    registry = InMemoryPolicyRegistry()
    root = activation.build_activation_root(
        registry=registry, signer=signer, signature_verifier=ring,
        approval_verifier=verifier)
    return root, registry, ring, revoker, evidence


def refuses(fn, expected):
    try:
        fn()
    except expected:
        return
    raise SystemExit("a refusal did not fire: " + expected.__name__)


# -- composition: no defaults that grant; the guard runs here too -------------
refuses(lambda: activation.build_activation_root(
    registry=InMemoryPolicyRegistry(), signer=object(),
    signature_verifier=object(), approval_verifier=None),
    activation.ActivationCompositionError)


class _Impostor:
    @property
    def adapter_id(self):
        return "impostor.agent-constitution/v9"

    @property
    def policy_family(self):
        return family.AGENT_CONSTITUTION_POLICY_FAMILY

    def recognizes(self, artifact):
        return True

    def describe(self, artifact):
        raise NotImplementedError

    def coordinate_for(self, reference):
        return None


root, registry, ring, revoker, evidence = make_world()
refuses(lambda: activation.build_activation_root(
    registry=InMemoryPolicyRegistry(), signer=root._signer,
    signature_verifier=ring,
    approval_verifier=DenyAllApprovalVerifier(),
    adapters=AdapterRegistry([_Impostor()])),
    family.AgentConstitutionFamilyCollisionError)

# -- the chain: preflight -> issue -> activate -> resolve ---------------------
policy = build_constitution()
report = root.preflight_issuance(
    policy=policy, record_id="rec-acc-fc-1", approval=evidence, as_of=T_ISSUE)
assert report.ready is True, [ (c.name, c.ok, c.detail) for c in report.checks ]
assert registry.get_issued(
    family.agent_constitution_coordinate(policy.metadata)) is None, (
    "preflight stored something")

receipt = root.issue_constitution(
    policy=policy, record_id="rec-acc-fc-1", approval=evidence, issued_at=T_ISSUE)
assert receipt.coordinate.policy_id == POLICY_ID
assert receipt.coordinate.version == POLICY_VERSION
assert receipt.coordinate.tenant_id == GLOBAL_TENANT
assert not hasattr(receipt, "signature")

reference_map, activation_receipt = root.activate_constitution(
    coordinate=receipt.coordinate, activated_at=T_ISSUE)
assert activation_receipt.activated_entries == ((GLOBAL_TENANT, GOVERNED_ROLE_REF),)
assert dict(reference_map) == {(GLOBAL_TENANT, GOVERNED_ROLE_REF): receipt.coordinate}

resolver = root.constitution_resolver(reference_map=reference_map)
resolved = resolver.resolve(
    tenant_id=GLOBAL_TENANT, role_contract_ref=GOVERNED_ROLE_REF, as_of=T_LATER,
    presented_constitution_ref=CONSTITUTION_REF)
assert resolved == policy

# -- bind: the proposer's builders stamp from the genuine resolution ----------
_ROLE_CONTRACT = getattr(ap, "Cognitive" + "RoleContract")
FIXED = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
LATER = FIXED + timedelta(days=365)
PLACEHOLDER = "sha" "256:" + "0" * 64
PROFILE_ID, PROFILE_VERSION = "invoice.reconciliation", "2026.1"


class _Provider:
    def evaluate(self, *, request):
        return ap.DomainEvaluationResponse(
            candidate_id=request.candidate_id, profile_id=request.profile_id,
            profile_version=request.profile_version,
            outcome=ap.DomainEvaluationOutcome.SATISFIED)


class _StrategyResolver:
    def resolve(self, *, request):
        return ap.StrategyPolicyResponse(
            strategy_policy_id="ugence.strategy_permission.reconciliation",
            strategy_policy_version="v1",
            permitted_strategies=tuple(ap.ReasoningStrategy),
            strategy_policy_ref=request.strategy_policy_ref)


identity = ap.AgentIdentityRef(
    schema_version="1.0", tenant_id="tenant-1", created_at=FIXED,
    agent_id="agent-1", agent_version="1.0.0",
    lifecycle_state=ap.AgentLifecycleState.ACTIVE,
    bound_role_contract_id="role-1", owner_role_ref="role-owner")
role = _ROLE_CONTRACT(
    schema_version="1.0", tenant_id="tenant-1", created_at=FIXED,
    role_contract_id="role-1", primary_function="reconcile invoices",
    permitted_tool_scopes=["invoice.read"],
    permitted_candidate_dispositions=[ap.CandidateDisposition.RECOMMEND_WITHHOLD],
    permitted_review_actions=[ap.ReviewAction.ROUTE_APPROVAL_BUNDLE],
    escalation_role_ref="role-2", activation_status=ap.RoleActivationStatus.ACTIVE,
    strategy_policy_ref="policy-authority/strategy-permission/reconciliation",
    constitution_ref=CONSTITUTION_REF)
mandate = ap.WorkMandate(
    schema_version="1.0", tenant_id="tenant-1", created_at=FIXED,
    mandate_id="mandate-1", case_ref="case-1", assigned_role_contract_id="role-1",
    purpose="reconcile invoices for Q1", allowed_source_scopes=["ledger.read"],
    expires_at=LATER)
context = ap.BoundedContextEnvelope(
    schema_version="1.0", tenant_id="tenant-1", created_at=FIXED,
    context_id="context-1", mandate_id="mandate-1",
    allowed_record_refs=["record-1"], excluded_data_classes=[],
    context_hash=PLACEHOLDER, expires_at=LATER)
observation = ap.ToolObservation(
    schema_version="1.0", tenant_id="tenant-1", created_at=FIXED,
    observation_id="obs-1", case_ref="case-1", tool_name="invoice.read",
    operation_class=ap.ToolOperationClass.READ_ONLY, source_ref="record-1",
    observed_at=FIXED, content_hash=PLACEHOLDER,
    normalized_fields={"vendor.name": "Acme Corp"})
provider = _Provider()
candidate = ap.build_candidate_advisory(
    candidate_id="cand-1", identity=identity, role=role, mandate=mandate,
    context=context, observations=[observation],
    disposition=ap.CandidateDisposition.RECOMMEND_WITHHOLD,
    requested_review_action=ap.ReviewAction.ROUTE_APPROVAL_BUNDLE,
    observation_refs=["obs-1"], claim_refs=[], assumptions=[], uncertainties=[],
    evaluated_at=FIXED, provider=provider,
    profile_id=PROFILE_ID, profile_version=PROFILE_VERSION)
candidate_set = ap.build_advisory_candidate_set(
    candidate_set_id="set-1", tenant_id="tenant-1", case_ref="case-1",
    created_at=FIXED, candidates=(candidate,), selected_candidate_id="cand-1",
    domain_evaluation_profile_id=PROFILE_ID,
    domain_evaluation_profile_version=PROFILE_VERSION)
advisory = ap.build_proposer_advisory(
    tenant_id="tenant-1", case_ref="case-1", created_at=FIXED,
    identity=identity, role=role, mandate=mandate, context=context,
    observations=[observation], candidate_set=candidate_set,
    parent_advisory_digest=None, claim_summaries=[], observation_refs=[],
    uncertainties=[], expires_at=LATER, provider=provider,
    expected_profile_id=PROFILE_ID, expected_profile_version=PROFILE_VERSION,
    requested_review_destination_role_ref="role-approver",
    strategy_policy_resolver=_StrategyResolver(),
    constitution_resolution=resolved,
    declared_strategy=ap.ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED)
assert advisory.constitution_policy_id == POLICY_ID
assert advisory.constitution_policy_version == POLICY_VERSION
assert ap.verify_advisory_identity(advisory=advisory) is True

# -- conform ------------------------------------------------------------------
conforming = conformance.GovernedRoleFacts(
    tenant_id=GLOBAL_TENANT, role_contract_ref=GOVERNED_ROLE_REF,
    declared_candidate_dispositions=(
        ap.CandidateDisposition.RECOMMEND_WITHHOLD.value,),
    declared_review_actions=(ap.ReviewAction.ROUTE_APPROVAL_BUNDLE.value,),
    declared_tool_scopes=("invoice.read",))
assert conformance.role_facts_conform(policy=resolved, facts=conforming) is True
outside = conformance.GovernedRoleFacts(
    tenant_id=GLOBAL_TENANT, role_contract_ref=GOVERNED_ROLE_REF,
    declared_candidate_dispositions=(
        ap.CandidateDisposition.RECOMMEND_WITHHOLD.value,),
    declared_review_actions=(ap.ReviewAction.ROUTE_APPROVAL_BUNDLE.value,),
    declared_tool_scopes=("invoice.read", "ledger.write"))
assert conformance.role_facts_conform(policy=resolved, facts=outside) is False

# -- the four-way fail-closed matrix ------------------------------------------
# 1. Missing approval: deny-by-default verifier -> typed refusal, nothing stored.
deny_root, deny_registry, *_ , deny_evidence = make_world(
    approval_verifier=DenyAllApprovalVerifier())
refuses(lambda: deny_root.issue_constitution(
    policy=policy, record_id="rec-nobody", approval=deny_evidence,
    issued_at=T_ISSUE), PolicyApprovalError)
assert deny_registry.get_issued(receipt.coordinate) is None

# 2. Missing trust: the ring never learned the issuance key -> resolve refuses.
trustless_root, t_registry, t_ring, t_revoker, t_evidence = make_world(
    key_in_ring=False)
t_receipt = trustless_root.issue_constitution(
    policy=build_constitution(), record_id="rec-untrusted",
    approval=t_evidence, issued_at=T_ISSUE)
t_map, _ = trustless_root.activate_constitution(
    coordinate=t_receipt.coordinate, activated_at=T_ISSUE)
t_resolver = trustless_root.constitution_resolver(reference_map=t_map)
refuses(lambda: t_resolver.resolve(
    tenant_id=GLOBAL_TENANT, role_contract_ref=GOVERNED_ROLE_REF, as_of=T_LATER),
    conformance.ConstitutionUnresolvedError)

# 3. Missing mapping: an empty configured map -> typed refusal, mints nothing.
empty_resolver = root.constitution_resolver(reference_map={})
refuses(lambda: empty_resolver.resolve(
    tenant_id=GLOBAL_TENANT, role_contract_ref=GOVERNED_ROLE_REF, as_of=T_LATER),
    conformance.UnknownConstitutionReferenceError)

# 4. Revoked: the authority's own signed revocation -> resolve refuses after.
revoke_policy(
    reference=receipt.coordinate, revocation_id="revocation-1",
    reason_code=PolicyRevocationReasonCode.APPROVAL_WITHDRAWN,
    registry=registry, adapters=root._adapters, signer=revoker,
    signature_verifier=ring, revoked_at=T_LATER)
refuses(lambda: resolver.resolve(
    tenant_id=GLOBAL_TENANT, role_contract_ref=GOVERNED_ROLE_REF,
    as_of=T_LATER + timedelta(minutes=1)),
    conformance.ConstitutionUnresolvedError)

# -- nothing that authorizes execution came along -----------------------------
for mod in ("risk_authority", "ugence_risk_authority", "actiongate_provider",
            "ugence_decision_authority", "ugence_agent_runtime", "ugence_console_api",
            "ai_hiring", "platform_freeze", "decision_governance",
            "ugence_agentic_proposer_strategy_permission_policy",
            "ugence_agentic_proposer_strategy_permission_runtime"):
    assert importlib.util.find_spec(mod) is None, ("unrelated package present: " + mod)

# -- every installed first-party distribution is exactly the version built here --
import importlib.metadata as _md

_pins = {}
for _line in open(sys.argv[1], encoding="utf-8"):
    _line = _line.strip()
    if _line:
        _n, _v = _line.split("==")
        _pins[_n] = _v
_first_party = {}
for _dist in _md.distributions():
    _n = (_dist.metadata["Name"] or "").lower()
    if _n.startswith("ugence-"):
        assert _n in _pins, "an unpinned first-party distribution is installed: " + _n
        assert _dist.version == _pins[_n], (_n, _dist.version, _pins[_n])
        _first_party[_n] = _dist.version
assert "ugence-agent-constitution-activation" in _first_party
assert "ugence-agent-constitution-conformance" in _first_party
assert len(_first_party) >= 6, _first_party
print("first-party installed:", sorted(_n + "==" + _v for _n, _v in _first_party.items()))

_checked = 0
for _name, _module in sorted(sys.modules.items()):
    if "." in _name or not _name.startswith("ugence_"):
        continue
    _origin = getattr(_module, "__file__", None)
    assert _origin, _name
    assert "site-packages" in _origin, (_name, _origin)
    assert "/symbolu" not in _origin, (_name, _origin)
    _checked += 1
assert _checked >= 6, _checked
print("first-party modules resolved under the venv:", _checked)

print("ISOLATED AGENT-CONSTITUTION ACTIVATION VERIFICATION OK")
'''


def _run(cmd, capture=False, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True, **kw)
    return subprocess.run(cmd, check=True, **kw)


def _foreign_members(wheel: Path) -> set:
    with zipfile.ZipFile(wheel) as z:
        tops = {n.split("/", 1)[0] for n in z.namelist() if "/" in n}
    return {t for t in tops if not (t == NAMESPACE or t.endswith(".dist-info"))}


def _wheel_identity(wheel: Path) -> tuple:
    """The (canonical distribution name, version) a wheel filename encodes."""

    name, version = wheel.name.split("-")[:2]
    return name.replace("_", "-").lower(), version


def _declared_dependencies(source: Path) -> list:
    block = re.search(
        r"^dependencies\s*=\s*\[(.*?)\]",
        (source / "pyproject.toml").read_text(encoding="utf-8"),
        re.S | re.M,
    )
    return re.findall(r'"([^"]+)"', block.group(1)) if block else []


def _third_party_requirements() -> list:
    """Every non-first-party requirement any source built here declares."""

    found = {}
    for source in SOURCES.values():
        for spec in _declared_dependencies(source):
            name = re.split(r"[<>=!~\[ ]", spec, 1)[0].strip()
            if not name.lower().startswith(FIRST_PARTY_PREFIX):
                found[name.lower()] = spec
    return sorted(found.values())


def _isolated_env() -> dict:
    """A pip environment that cannot reach an index or a monorepo path."""

    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP")
    }
    env["PIP_NO_INDEX"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return env


def _negative_control(findlinks: Path, target: Path, victim: Path) -> None:
    """Removing a required first-party wheel must FAIL, never fetch a replacement.

    Identical in structure and rationale to the conformance script's control:
    the refusal must be tied to the wheel that was removed, verified from pip's
    own verbose transcript, positively.
    """

    with tempfile.TemporaryDirectory() as td:
        crippled = Path(td) / "wheelhouse"
        shutil.copytree(findlinks, crippled)
        (crippled / victim.name).unlink()

        env_dir = Path(td) / "venv"
        venv.create(env_dir, with_pip=True, clear=True, system_site_packages=False)
        py = env_dir / "bin" / "python"

        result = _run(
            [str(py), "-m", "pip", "install", "-vv", "--no-index",
             "--find-links", str(crippled), str(target)],
            capture=True, env=_isolated_env(), cwd=str(td),
        )
        combined = (result.stdout + result.stderr).lower()

        assert result.returncode != 0, (
            "the installation SUCCEEDED with "
            f"{victim.name} removed from the wheelhouse; resolution is not "
            "offline-and-local, and an index or ambient environment supplied it"
        )
        failure_lines = "\n".join(
            line for line in combined.splitlines()
            if "no matching distribution" in line or "could not find a version" in line
        )
        assert failure_lines, combined[-2000:]

        victim_name, _ = _wheel_identity(victim)
        assert victim_name in failure_lines, (
            f"the refusal does not name {victim_name!r}, so it is some other "
            f"resolution failure and not the removal this control performed: "
            f"{failure_lines or combined[-2000:]}"
        )

        assert "ignoring indexes" in combined, combined[-3000:]
        assert str(crippled).lower() in combined, combined[-3000:]
        for consulted in (
            "found index url",
            "fetching project page",
            "starting new https connection",
            "getting page http",
        ):
            assert consulted not in combined, f"pip consulted an index: {consulted}"

        print(
            f"      refused as intended ({victim.name} removed); pip reported "
            "ignoring the index and searched only the wheelhouse"
        )


def main() -> int:
    findlinks = PKG / "_dist_wheels"
    if findlinks.exists():
        shutil.rmtree(findlinks)
    findlinks.mkdir()

    print(f"[1/7] build every first-party wheel {DISTRIBUTION} needs, from THIS repository")
    for src in SOURCES.values():
        _run([sys.executable, "-m", "build", "--wheel", str(src), "-o", str(findlinks)])
    first_party = {}
    for wheel in sorted(findlinks.glob("*.whl")):
        name, version = _wheel_identity(wheel)
        first_party[name] = (version, wheel)
    built = set(first_party)
    assert DISTRIBUTION in first_party, sorted(built)
    assert CONFORMANCE_DISTRIBUTION in first_party, sorted(built)
    target = first_party[DISTRIBUTION][1]
    for name in sorted(built):
        print(f"      built {name}=={first_party[name][0]}")
    print(f"      target wheel: {target}")

    print("[2/7] assert the target wheel bundles no foreign top-level package + ships py.typed")
    foreign = _foreign_members(target)
    assert not foreign, f"wheel bundles foreign packages: {sorted(foreign)}"
    with zipfile.ZipFile(target) as z:
        names = set(z.namelist())
    assert f"{NAMESPACE}/py.typed" in names, "wheel is missing py.typed"
    print(f"      wheel contains only {NAMESPACE}/ (+ py.typed) + dist-info")

    print("[3/7] vendor third-party dependencies into the wheelhouse "
          "(a networked step, as is step 1's build isolation)")
    requirements = _third_party_requirements()
    print(f"      third-party requirements, read from packaging metadata: {requirements}")
    if requirements:
        _run([sys.executable, "-m", "pip", "download", "--quiet",
              "--only-binary=:all:", "--dest", str(findlinks), *requirements])
    present = {name for name, _ in (_wheel_identity(w) for w in findlinks.glob("*.whl"))}
    strays = {n for n in present if n.startswith(FIRST_PARTY_PREFIX)} - built
    assert not strays, (
        f"a first-party distribution entered the wheelhouse from an index: {sorted(strays)}"
    )
    print(f"      wheelhouse holds {len(list(findlinks.glob('*.whl')))} wheels; "
          "every first-party one was built above")

    print("[4/7] create a clean venv and install OFFLINE, by exact wheel path")
    with tempfile.TemporaryDirectory() as td:
        pins = Path(td) / "first-party-pins.txt"
        pins.write_text(
            "".join(f"{n}=={v}\n" for n, (v, _) in sorted(first_party.items())),
            encoding="utf-8",
        )
        env_dir = Path(td) / "venv"
        venv.create(env_dir, with_pip=True, clear=True, system_site_packages=False)
        py = env_dir / "bin" / "python"

        install = [
            str(py), "-m", "pip", "install", "--quiet",
            "--no-index",
            "--find-links", str(findlinks),
            "--constraint", str(pins),
            str(target),
        ]
        assert install[-1].endswith(".whl") and Path(install[-1]).is_file(), install[-1]
        _run(install, env=_isolated_env())

        print("[5/7] assert the installed first-party versions are exactly those built")
        frozen = _run([str(py), "-m", "pip", "list", "--format=freeze"],
                      capture=True, env=_isolated_env())
        assert frozen.returncode == 0, frozen.stderr
        installed = dict(
            line.lower().split("==", 1)
            for line in frozen.stdout.split() if "==" in line
        )
        for name, version in sorted(installed.items()):
            if name.startswith(FIRST_PARTY_PREFIX):
                assert name in first_party, f"an unbuilt first-party dist is installed: {name}"
                assert version == first_party[name][0], (name, version, first_party[name][0])
                print(f"      {name}=={version}  (built here)")

        print("[6/7] run the isolated proof (cwd has no monorepo source)")
        _run([str(py), "-c", _CHECK, str(pins)], cwd=str(td), env=_isolated_env())

    print("[7/7] negative control: a missing first-party wheel must refuse, not substitute")
    _negative_control(findlinks, target, first_party[NEGATIVE_CONTROL_VICTIM][1])

    shutil.rmtree(findlinks, ignore_errors=True)
    print(f"\nISOLATED {DISTRIBUTION.upper()} DISTRIBUTION VERIFIED (offline, pinned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
