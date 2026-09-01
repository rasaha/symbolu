#!/usr/bin/env python3
"""Reproducible proof that BOTH Agent Constitution distributions install and
operate from built wheels, against installed distributions and no monorepo path.

Builds this distribution, the family distribution and every first-party
dependency into a local wheelhouse, installs the conformance wheel **offline**
into a fresh virtualenv with no system site packages — which pulls the family
wheel in as a declared dependency — and then proves *inside that environment*:

  * ``ugence_agent_constitution_conformance`` and
    ``ugence_agent_constitution_policy`` import from site-packages, both at
    0.1.0, with no repository source on ``sys.path``, and both ship ``py.typed``;
  * the family's ratified identity constants are exactly the ACC-S1-Q1 values;
  * a constitution constructs, its declared digest binds its own body, and the
    canonical projection omits exactly ``metadata.content_digest``;
  * the construction rules fire — unsorted role list, alien bound token, wrong
    clause-vocabulary version;
  * the guarded composition path works and the ACC-S1-Q3 collision guard
    refuses an impostor registry inside the installed environment;
  * the family issues through the **real** shared authority, the resolver
    returns the exact signed artifact with the framed digest independently
    recomputed, and the conformance predicate answers True and False for
    conforming and non-conforming presented facts;
  * a body swap under the same coordinate fails closed, and a near-miss role
    reference fails closed;
  * every installed first-party distribution is exactly the version built here,
    and every loaded first-party module resolves under the clean venv;
  * no execution authority, console, product or unrelated package is importable.

**The installation is offline and pinned, and that is the point.** Installing by
distribution name with only ``--find-links`` leaves an index reachable, so a
higher-versioned ``ugence-*`` published anywhere could satisfy the resolution
instead of the wheel this repository just built — and the proof would then be
about something else entirely. So: every first-party wheel is built here from
source; third-party dependencies are vendored into the same wheelhouse in a
separate, clearly marked step, read from packaging metadata rather than listed
here; the clean-venv installation names the **exact built wheel path** and runs
under ``--no-index`` with ``PIP_NO_INDEX=1`` and a sanitized environment; and
every first-party distribution is constrained to, and then asserted at, the exact
version built. Building and vendoring may both use a network — ``python -m build``
installs its backend into a PEP 517 isolated environment — but neither can
introduce a first-party distribution, and the stray check fails if one appears
that was not built here. A negative control removes one required first-party wheel and
proves the installation **refuses** rather than substituting — verifying
offline resolution positively from pip's own verbose log, not by the absence of
an index marker, since pip's not-found error is identical either way.

The permissive approval verifier below exists only inside this script, for the
same reason the authority's own permissive verifiers exist only under ``tests/``:
issuance must be exercised, and the shipped default is deny-by-default. Neither
distribution ships anything like it, and a package test asserts that.

Run:  python packages/integration/agent-constitution-conformance/verify_agent_constitution_conformance_distribution.py
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

DISTRIBUTION = "ugence-agent-constitution-conformance"
NAMESPACE = "ugence_agent_constitution_conformance"
FAMILY_DISTRIBUTION = "ugence-agent-constitution-policy"
FAMILY_NAMESPACE = "ugence_agent_constitution_policy"

#: Distribution names beginning with this prefix are this repository's own and
#: must never be resolved from an index: every one is built below, from source.
FIRST_PARTY_PREFIX = "ugence-"

#: The first-party wheel the negative control removes to prove the offline
#: installation refuses rather than substituting. The family distribution is the
#: natural victim: it is this distribution's own declared dependency.
NEGATIVE_CONTROL_VICTIM = FAMILY_DISTRIBUTION

SOURCES = {
    NAMESPACE: PKG,
    FAMILY_NAMESPACE: REPO / "packages" / "integration" / "agent-constitution-policy",
    "ugence_policy_authority": REPO / "packages" / "policy-authority",
    "ugence_uvi_policy_contracts": REPO / "packages" / "uvi-policy-contracts",
    "ugence_governance_contracts": REPO / "packages" / "governance-contracts",
    "ugence_agentic_proposer": REPO / "packages" / "capabilities" / "agentic-proposer",
    "ugence_jcs": REPO / "packages" / "jcs",
}

_CHECK = r'''
import importlib.util
import sys
from datetime import datetime, timezone

import ugence_agent_constitution_conformance as conformance
import ugence_agent_constitution_policy as family

assert conformance.__version__ == "0.1.0", conformance.__version__
assert family.__version__ == "0.2.0", family.__version__
assert "site-packages" in conformance.__file__, conformance.__file__
assert "site-packages" in family.__file__, family.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path

import pathlib as _pl
for _mod in (conformance, family):
    assert (_pl.Path(_mod.__file__).resolve().parent / "py.typed").is_file(), _mod

# -- the ratified ACC-S1-Q1 identity values, across a packaging boundary ------
assert family.AGENT_CONSTITUTION_ADAPTER_ID == "ugence.agent-constitution/v1"
assert family.AGENT_CONSTITUTION_POLICY_FAMILY == "agent_governance.agent_constitution"
assert family.AGENT_CONSTITUTION_POLICY_TYPE == "AgentConstitutionPolicy"
assert family.CONSTITUTION_VOCABULARY_VERSION == "ugence.agent-constitution/clauses/v1"

from ugence_agentic_proposer import CandidateDisposition, ReviewAction
assert family.ADMITTED_CANDIDATE_DISPOSITION_TOKENS == {m.value for m in CandidateDisposition}
assert family.ADMITTED_REVIEW_ACTION_TOKENS == {m.value for m in ReviewAction}

TENANT = "tenant-1"
ROLE_REF = "ugence.roles/tenant-1/reconciler/v1"
OTHER_ROLE = "ugence.roles/tenant-1/proposer-reviewer/v1"
CONSTITUTION_REF = "ugence.agent-constitution/tenant-1/baseline/v1"
T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)

ADAPTER = family.AgentConstitutionPolicyFamilyAdapter()
GOVERNED = tuple(sorted((ROLE_REF, OTHER_ROLE)))
DISPOSITIONS = tuple(sorted(m.value for m in CandidateDisposition))[:2]
REVIEW_ACTIONS = tuple(sorted(m.value for m in ReviewAction))[:1]
SCOPES = ("scope.evidence-read",)


def metadata(digest, **overrides):
    fields = dict(policy_id="agent-constitution-baseline", version="1.0.0",
                  content_digest=digest, scope=family.POLICY_SCOPE_TENANT,
                  lifecycle_state=family.LIFECYCLE_APPROVED_ACTIVE,
                  tenant_id=TENANT, effective_from=T_FROM, effective_to=T_TO)
    fields.update(overrides)
    return family.AgentConstitutionPolicyMetadata(**fields)


def build(tool_scopes=SCOPES, **overrides):
    body = dict(agent_constitution_ref=CONSTITUTION_REF, governed_role_refs=GOVERNED,
                permitted_candidate_dispositions_bound=DISPOSITIONS,
                permitted_review_actions_bound=REVIEW_ACTIONS,
                permitted_tool_scopes_bound=tool_scopes)
    draft = family.AgentConstitutionPolicy(
        metadata=metadata(family.PLACEHOLDER_CONTENT_DIGEST, **overrides), **body)
    digest = ADAPTER.describe(draft).body_digest()
    return family.AgentConstitutionPolicy(metadata=metadata(digest, **overrides), **body)


policy = build()
descriptor = ADAPTER.describe(policy)
assert descriptor.body_digest() == descriptor.declared_content_digest
assert descriptor.policy_type == family.AGENT_CONSTITUTION_POLICY_TYPE
assert "content_digest" not in descriptor.canonical_projection["metadata"]

# -- the construction rules fire -------------------------------------------
def refuses(fn, expected):
    try:
        fn()
    except expected:
        return
    raise SystemExit("a construction rule did not fire: " + expected.__name__)


refuses(lambda: family.AgentConstitutionPolicy(
    metadata=metadata(family.PLACEHOLDER_CONTENT_DIGEST),
    agent_constitution_ref=CONSTITUTION_REF,
    governed_role_refs=tuple(reversed(GOVERNED)),
    permitted_candidate_dispositions_bound=DISPOSITIONS,
    permitted_review_actions_bound=REVIEW_ACTIONS,
    permitted_tool_scopes_bound=SCOPES), family.AgentConstitutionOrderingError)
refuses(lambda: family.AgentConstitutionPolicy(
    metadata=metadata(family.PLACEHOLDER_CONTENT_DIGEST),
    agent_constitution_ref=CONSTITUTION_REF,
    governed_role_refs=GOVERNED,
    permitted_candidate_dispositions_bound=("SOMETHING_NO_ENUM_CONTAINS",),
    permitted_review_actions_bound=REVIEW_ACTIONS,
    permitted_tool_scopes_bound=SCOPES), family.AgentConstitutionFieldError)
refuses(lambda: family.AgentConstitutionPolicy(
    metadata=metadata(family.PLACEHOLDER_CONTENT_DIGEST),
    agent_constitution_ref=CONSTITUTION_REF,
    governed_role_refs=GOVERNED,
    permitted_candidate_dispositions_bound=DISPOSITIONS,
    permitted_review_actions_bound=REVIEW_ACTIONS,
    permitted_tool_scopes_bound=SCOPES,
    constitution_vocabulary_version="ugence.agent-constitution/clauses/v2"),
    family.AgentConstitutionFieldError)

# -- the real authority issues; the guarded resolver resolves ----------------
from ugence_policy_authority.api import (
    AdapterRegistry, ApprovalEvidenceRef, ApprovalVerification,
    ApprovalVerificationStatus, Ed25519PolicySigner, InMemoryPolicyRegistry,
    KeyEntitlement, PolicyKeyRing, SigningKey, framed_body_digest, issue_policy,
)


class _ScriptApprovalVerifier:
    """Verification-script only. Neither distribution ships anything like it."""

    def verify_approval(self, *, coordinate, policy_body_digest, approval, as_of):
        return ApprovalVerification(
            verified=True, status=ApprovalVerificationStatus.APPROVED,
            coordinate=coordinate, policy_body_digest=policy_body_digest,
            approving_authority_id=approval.approving_authority_id,
            approval_ref=approval.approval_ref,
            approval_digest=approval.approval_digest, verified_at=as_of)


signer = Ed25519PolicySigner(
    authority_id="ugence.policy-authority", key_id="key-1",
    signing_key=SigningKey.from_seed(bytes([1]) * 32))
key_ring = PolicyKeyRing(
    [signer.verification_key(entitlements=(KeyEntitlement.ISSUE_POLICY,))])
registry = InMemoryPolicyRegistry()
adapters = AdapterRegistry([ADAPTER])
approval = ApprovalEvidenceRef(
    approval_ref="APPROVAL-1", approval_digest="a" * 64,
    approving_authority_id="ugence.governance.policy-approval-board")

record = issue_policy(
    policy=policy, record_id="rec-1", approval=approval,
    approval_verifier=_ScriptApprovalVerifier(), signer=signer, registry=registry,
    adapters=adapters, issued_at=T_MID)

coordinate = family.agent_constitution_coordinate(policy.metadata)
resolver = conformance.build_constitution_resolver(
    reference_map={(TENANT, ROLE_REF): coordinate},
    registry=registry, signature_verifier=key_ring,
    approval_verifier=_ScriptApprovalVerifier(), adapters=adapters)

resolved = resolver.resolve(
    tenant_id=TENANT, role_contract_ref=ROLE_REF, as_of=T_MID,
    presented_constitution_ref=CONSTITUTION_REF)
assert resolved is policy

recomputed = framed_body_digest(
    adapter_id=descriptor.adapter_id, policy_type=descriptor.policy_type,
    projection=descriptor.canonical_projection)
assert recomputed == record.policy_body_digest, "the projection does not rebuild"

# -- the predicate answers both ways ----------------------------------------
conforming = conformance.GovernedRoleFacts(
    tenant_id=TENANT, role_contract_ref=ROLE_REF,
    declared_candidate_dispositions=DISPOSITIONS,
    declared_review_actions=REVIEW_ACTIONS, declared_tool_scopes=SCOPES)
assert conformance.role_facts_conform(policy=resolved, facts=conforming) is True

outside = conformance.GovernedRoleFacts(
    tenant_id=TENANT, role_contract_ref=ROLE_REF,
    declared_candidate_dispositions=DISPOSITIONS,
    declared_review_actions=REVIEW_ACTIONS,
    declared_tool_scopes=SCOPES + ("scope.unbounded",))
assert conformance.role_facts_conform(policy=resolved, facts=outside) is False

# -- fail closed: near-miss key, and a body swap under the same coordinate ---
refuses(lambda: resolver.resolve(
    tenant_id=TENANT, role_contract_ref=ROLE_REF + "x", as_of=T_MID),
    conformance.UnknownConstitutionReferenceError)

import dataclasses
tampered = family.AgentConstitutionPolicy(
    metadata=policy.metadata, agent_constitution_ref=policy.agent_constitution_ref,
    governed_role_refs=policy.governed_role_refs,
    permitted_candidate_dispositions_bound=policy.permitted_candidate_dispositions_bound,
    permitted_review_actions_bound=policy.permitted_review_actions_bound,
    permitted_tool_scopes_bound=("scope.everything",))
registry._issued[coordinate] = dataclasses.replace(
    registry._issued[coordinate], policy=tampered)
refuses(lambda: resolver.resolve(
    tenant_id=TENANT, role_contract_ref=ROLE_REF, as_of=T_MID),
    conformance.ConstitutionUnresolvedError)

# -- the ACC-S1-Q3 guard runs inside the installed environment too -----------
class _Impostor:
    @property
    def adapter_id(self):
        return "impostor.agent-constitution/v9"

    def recognizes(self, artifact):
        return type(artifact) is family.AgentConstitutionPolicy

    def describe(self, artifact):
        raise NotImplementedError

    def coordinate_for(self, reference):
        return None


refuses(lambda: family.assert_agent_constitution_family_registration(
    AdapterRegistry([family.AgentConstitutionPolicyFamilyAdapter(), _Impostor()])),
    family.AgentConstitutionFamilyCollisionError)
refuses(lambda: conformance.build_constitution_resolver(
    reference_map={(TENANT, ROLE_REF): coordinate},
    registry=registry, signature_verifier=key_ring,
    approval_verifier=_ScriptApprovalVerifier(),
    adapters=AdapterRegistry([_Impostor()])),
    family.AgentConstitutionFamilyCollisionError)

# -- nothing that authorizes execution came along --------------------------
for mod in ("risk_authority", "ugence_risk_authority", "actiongate_provider",
            "ugence_decision_authority", "ugence_agent_runtime", "ugence_console_api",
            "ai_hiring", "platform_freeze", "decision_governance",
            "ugence_agentic_proposer_strategy_permission_policy",
            "ugence_agentic_proposer_strategy_permission_runtime"):
    assert importlib.util.find_spec(mod) is None, ("unrelated package present: " + mod)


# -- every installed first-party distribution is exactly the version built here --
# The pins file is written from the wheels this repository built, so this asserts
# against the build rather than against a number typed into this script.
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
assert "ugence-agent-constitution-policy" in _first_party
assert len(_first_party) >= 5, _first_party
print("first-party installed:", sorted(_n + "==" + _v for _n, _v in _first_party.items()))

# -- every imported first-party module resolves under the clean venv ------------
_checked = 0
for _name, _module in sorted(sys.modules.items()):
    if "." in _name or not _name.startswith("ugence_"):
        continue
    _origin = getattr(_module, "__file__", None)
    assert _origin, _name
    assert "site-packages" in _origin, (_name, _origin)
    assert "/symbolu" not in _origin, (_name, _origin)
    _checked += 1
assert _checked >= 5, _checked
print("first-party modules resolved under the venv:", _checked)

print("ISOLATED AGENT-CONSTITUTION CONFORMANCE VERIFICATION OK")
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
    """Every non-first-party requirement any source built here declares.

    Read from the packaging metadata rather than listed in this script, so a new
    third-party dependency cannot silently go un-vendored and turn the offline
    installation below back into a networked one.
    """

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

    This is what makes the offline guarantee falsifiable. If the installation
    still succeeded with a required first-party wheel absent from the wheelhouse,
    something other than the wheelhouse supplied it — an index, or ambient site
    packages — which is exactly the substitution this step exists to prevent.
    """

    with tempfile.TemporaryDirectory() as td:
        crippled = Path(td) / "wheelhouse"
        shutil.copytree(findlinks, crippled)
        (crippled / victim.name).unlink()

        env_dir = Path(td) / "venv"
        venv.create(env_dir, with_pip=True, clear=True, system_site_packages=False)
        py = env_dir / "bin" / "python"

        # ``-vv`` rather than quiet, because the offline claim has to be verified
        # POSITIVELY. pip's not-found error is word-for-word identical with and
        # without an index configured, and pip's own "Ignoring indexes:" line
        # contains the string "pypi.org" — so scanning the output for the absence
        # of an index marker establishes nothing, and would even misfire on a
        # correctly offline run. At -vv pip states what it actually did.
        result = _run(
            [str(py), "-m", "pip", "install", "-vv", "--no-index",
             "--find-links", str(crippled), str(target)],
            capture=True, env=_isolated_env(), cwd=str(td),
        )
        combined = (result.stdout + result.stderr).lower()

        # What the return code establishes: the install refused.
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

        # Tie the refusal to the wheel that was REMOVED. Without this the control
        # would pass on any resolution failure whatsoever — a typo in the target
        # path, a corrupt wheelhouse, a missing third-party dependency — and would
        # stop being evidence about substitution at all.
        #
        # Scanned over the FAILURE LINES, not the whole log: at -vv pip narrates
        # every project it considers, so the victim's name appears in the transcript
        # of a healthy resolution too. Checking the whole log passes when some other
        # package is what actually went missing, which is exactly the false
        # reassurance this assertion exists to prevent.
        victim_name, _ = _wheel_identity(victim)
        assert victim_name in failure_lines, (
            f"the refusal does not name {victim_name!r}, so it is some other "
            f"resolution failure and not the removal this control performed: "
            f"{failure_lines or combined[-2000:]}"
        )

        # What the verbose log establishes: the attempt was offline. pip announces
        # that it is ignoring the index and names the directory it searched; when
        # an index IS consulted it logs the lookup and the connection, so the
        # absence of THOSE markers is meaningful in a way "pypi.org" was not.
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
    assert FAMILY_DISTRIBUTION in first_party, sorted(built)
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

    # TWO steps may use a network, not one. This is the obvious one; step 1 is the
    # other, because ``python -m build`` creates a PEP 517 isolated environment and
    # installs the build backend into it from an index. Neither can introduce a
    # FIRST-PARTY distribution: every ugence-* wheel is built from source above,
    # and the stray check below fails if one appears that was not. What must be
    # offline is the clean-venv INSTALL, and step 4 is where that is enforced.
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
