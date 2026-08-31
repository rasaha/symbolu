#!/usr/bin/env python3
"""Reproducible proof that the strategy-permission policy family installs and
operates from a built wheel, against installed distributions and no monorepo path.

Builds this distribution and every first-party dependency into a local
wheelhouse, installs it **offline** into a fresh virtualenv with no system site
packages, and then proves *inside that environment*:

  * ``ugence_agentic_proposer_strategy_permission_policy`` imports from
    site-packages, at 0.1.0, with no repository source on ``sys.path``;
  * the curated public API resolves and ``py.typed`` ships;
  * a policy constructs, its declared digest binds its own body, and the
    canonical projection omits exactly ``metadata.content_digest``;
  * the construction rules fire — empty, duplicated, unsorted, alien token,
    wrong vocabulary version, and a non-Token ``policy_id``;
  * the accepted token set equals ``set(ReasoningStrategy)`` from the installed
    proposer distribution, so no fork survives packaging;
  * the family issues and resolves through the **real** shared authority, and a
    body swap under the same coordinate fails closed;
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

Run:  python packages/integration/agentic-proposer-strategy-permission-policy/verify_agentic_proposer_strategy_permission_policy_distribution.py
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

DISTRIBUTION = "ugence-agentic-proposer-strategy-permission-policy"
NAMESPACE = "ugence_agentic_proposer_strategy_permission_policy"

#: Distribution names beginning with this prefix are this repository's own and
#: must never be resolved from an index: every one is built below, from source.
FIRST_PARTY_PREFIX = "ugence-"

#: The first-party wheel the negative control removes to prove the offline
#: installation refuses rather than substituting.
NEGATIVE_CONTROL_VICTIM = "ugence-policy-authority"

SOURCES = {
    NAMESPACE: PKG,
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

import ugence_agentic_proposer_strategy_permission_policy as family

assert family.__version__ == "0.1.0", family.__version__
assert "site-packages" in family.__file__, family.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path

import pathlib as _pl
assert (_pl.Path(family.__file__).resolve().parent / "py.typed").is_file(), "no py.typed"

# -- identity constants are what the snapshot pinned ------------------------
assert family.STRATEGY_PERMISSION_ADAPTER_ID == "ugence.agentic-proposer.strategy-permission/v1"
assert family.STRATEGY_PERMISSION_POLICY_FAMILY == "agentic_proposer.strategy_permission"
assert family.STRATEGY_PERMISSION_POLICY_TYPE == "StrategyPermissionPolicy"
assert family.STRATEGY_VOCABULARY_VERSION == "ugence.agentic-proposer.reasoning-strategy/v1"

# -- one vocabulary, across a packaging boundary ----------------------------
from ugence_agentic_proposer import ReasoningStrategy
assert family.ADMITTED_STRATEGY_TOKENS == {m.value for m in ReasoningStrategy}, (
    "the installed family and the installed proposer disagree on the vocabulary")

SINGLE = ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED.value
MULTI = ReasoningStrategy.MULTI_CANDIDATE_UNREVISED.value
REF = "policy-authority/strategy-permission/reconciliation"
T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)

ADAPTER = family.StrategyPermissionPolicyFamilyAdapter()


def metadata(digest, **overrides):
    fields = dict(policy_id="strategy-permission", version="1.0.0",
                  content_digest=digest, scope=family.POLICY_SCOPE_TENANT,
                  lifecycle_state=family.LIFECYCLE_APPROVED_ACTIVE,
                  tenant_id="tenant-1", effective_from=T_FROM, effective_to=T_TO)
    fields.update(overrides)
    return family.StrategyPermissionPolicyMetadata(**fields)


def build(permitted=(MULTI, SINGLE), **overrides):
    permitted = tuple(sorted(permitted))
    draft = family.StrategyPermissionPolicy(
        metadata=metadata(family.PLACEHOLDER_CONTENT_DIGEST, **overrides),
        strategy_policy_ref=REF, permitted_strategies=permitted)
    digest = ADAPTER.describe(draft).body_digest()
    return family.StrategyPermissionPolicy(
        metadata=metadata(digest, **overrides),
        strategy_policy_ref=REF, permitted_strategies=permitted)


policy = build()
descriptor = ADAPTER.describe(policy)
assert descriptor.body_digest() == descriptor.declared_content_digest
assert descriptor.policy_type == family.STRATEGY_PERMISSION_POLICY_TYPE

projection = descriptor.canonical_projection
assert "content_digest" not in projection["metadata"], "the digest was not removed"
assert projection["strategy_policy_ref"] == REF
assert projection["vocabulary_version"] == family.STRATEGY_VOCABULARY_VERSION
assert projection["permitted_strategies"] == sorted((MULTI, SINGLE))

# -- the construction rules fire -------------------------------------------
def refuses(fn, expected):
    try:
        fn()
    except expected:
        return
    raise SystemExit("a construction rule did not fire: " + expected.__name__)


refuses(lambda: build(permitted=()), family.StrategyPermissionFieldError)
refuses(lambda: build(permitted=("STAGED_DECOMPOSITION",)), family.StrategyPermissionFieldError)
refuses(lambda: build(policy_id="tenant/strategy"), family.StrategyPermissionFieldError)
refuses(
    lambda: family.StrategyPermissionPolicy(
        metadata=metadata(family.PLACEHOLDER_CONTENT_DIGEST),
        strategy_policy_ref=REF, permitted_strategies=(SINGLE, SINGLE)),
    family.StrategyPermissionDuplicateError)
refuses(
    lambda: family.StrategyPermissionPolicy(
        metadata=metadata(family.PLACEHOLDER_CONTENT_DIGEST),
        strategy_policy_ref=REF, permitted_strategies=(SINGLE, MULTI)),
    family.StrategyPermissionOrderingError)
refuses(
    lambda: family.StrategyPermissionPolicy(
        metadata=metadata(family.PLACEHOLDER_CONTENT_DIGEST),
        strategy_policy_ref=REF, permitted_strategies=(SINGLE,),
        vocabulary_version="ugence.agentic-proposer.reasoning-strategy/v2"),
    family.StrategyPermissionFieldError)

# -- the real authority issues and resolves this family ---------------------
from ugence_policy_authority.api import (
    AdapterRegistry, ApprovalEvidenceRef, ApprovalVerification,
    ApprovalVerificationStatus, Ed25519PolicySigner, InMemoryPolicyRegistry,
    KeyEntitlement, PolicyKeyRing, PolicyResolutionReason, PolicyResolutionStatus,
    SigningKey, framed_body_digest, issue_policy, resolve_policy,
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

resolution = resolve_policy(
    reference=family.strategy_permission_coordinate(policy.metadata),
    expected_reference_tenant_id="tenant-1", as_of=T_MID, registry=registry,
    signature_verifier=key_ring, adapters=adapters)
assert resolution.status is PolicyResolutionStatus.RESOLVED, resolution.reason
assert resolution.reason is PolicyResolutionReason.RESOLVED
assert resolution.policy is policy

recomputed = framed_body_digest(
    adapter_id=resolution.descriptor_adapter_id,
    policy_type=resolution.descriptor_policy_type,
    projection=resolution.descriptor_canonical_projection)
assert recomputed == record.policy_body_digest, "the published projection does not rebuild"

# a body swap under the same coordinate fails closed
import dataclasses
coordinate = family.strategy_permission_coordinate(policy.metadata)
tampered = family.StrategyPermissionPolicy(
    metadata=policy.metadata, strategy_policy_ref=policy.strategy_policy_ref,
    permitted_strategies=tuple(sorted(m.value for m in ReasoningStrategy)))
registry._issued[coordinate] = dataclasses.replace(
    registry._issued[coordinate], policy=tampered)
after = resolve_policy(
    reference=coordinate, expected_reference_tenant_id="tenant-1", as_of=T_MID,
    registry=registry, signature_verifier=key_ring, adapters=adapters)
assert after.status is PolicyResolutionStatus.UNRESOLVED, after.status
assert after.policy is None

# -- nothing that authorizes execution came along --------------------------
for mod in ("risk_authority", "ugence_risk_authority", "actiongate_provider",
            "ugence_decision_authority", "ugence_agent_runtime", "ugence_console_api",
            "ai_hiring", "platform_freeze", "decision_governance",
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
assert len(_first_party) >= 4, _first_party
print("first-party installed:", sorted(_n + "==" + _v for _n, _v in _first_party.items()))

# -- every imported first-party module resolves under the clean venv ------------
# Derived from what is actually loaded, not a hand-listed few: a first-party
# module imported by any check above is covered without anyone remembering it.
_checked = 0
for _name, _module in sorted(sys.modules.items()):
    if "." in _name or not _name.startswith("ugence_"):
        continue
    _origin = getattr(_module, "__file__", None)
    assert _origin, _name
    assert "site-packages" in _origin, (_name, _origin)
    assert "/symbolu" not in _origin, (_name, _origin)
    _checked += 1
assert _checked >= 4, _checked
print("first-party modules resolved under the venv:", _checked)

print("ISOLATED STRATEGY-PERMISSION-POLICY VERIFICATION OK")
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
