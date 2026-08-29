#!/usr/bin/env python3
"""Reproducible proof that the strategy-permission runtime installs and operates
from a built wheel, against installed distributions and no monorepo path.

Builds this distribution and every first-party dependency into a local
wheelhouse, installs it **offline** into a fresh virtualenv with no system site
packages, and then proves *inside that environment*:

  * ``ugence_agentic_proposer_strategy_permission_runtime`` imports from
    site-packages, at 0.1.0, with no repository source on ``sys.path``;
  * the curated public API resolves and ``py.typed`` ships;
  * a policy issued and signed through the **real** shared authority resolves
    through the concrete resolver and yields the four ratified response fields,
    with the version a string and no ``verified`` boolean anywhere;
  * an unknown reference, a near-miss reference and a cross-tenant reference all
    fail closed, and the injected mapping is defensively copied;
  * an approval verifier is required at construction;
  * a body swap under the same coordinate fails closed, and the authority's cause
    reaches the caller **only** on the ``reason`` attribute — never in the message;
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
version built. A negative control removes one required first-party wheel and
proves the installation **refuses** rather than substituting.

The permissive approval verifier below exists only inside this script, for the
same reason the authority's own permissive verifiers exist only under ``tests/``:
issuance must be exercised, and the shipped default is deny-by-default. Neither
distribution ships anything like it, and a package test asserts that.

Run:  python packages/integration/agentic-proposer-strategy-permission-runtime/verify_agentic_proposer_strategy_permission_runtime_distribution.py
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
REPO = PKG.parents[2]

DISTRIBUTION = "ugence-agentic-proposer-strategy-permission-runtime"
NAMESPACE = "ugence_agentic_proposer_strategy_permission_runtime"

#: Distribution names beginning with this prefix are this repository's own and
#: must never be resolved from an index: every one is built below, from source.
FIRST_PARTY_PREFIX = "ugence-"

#: The first-party wheel the negative control removes to prove the offline
#: installation refuses rather than substituting.
NEGATIVE_CONTROL_VICTIM = "ugence-agentic-proposer-strategy-permission-policy"

SOURCES = {
    NAMESPACE: PKG,
    "ugence_agentic_proposer_strategy_permission_policy": (
        REPO / "packages" / "integration" / "agentic-proposer-strategy-permission-policy"
    ),
    "ugence_policy_authority": REPO / "packages" / "policy-authority",
    "ugence_uvi_policy_contracts": REPO / "packages" / "uvi-policy-contracts",
    "ugence_governance_contracts": REPO / "packages" / "governance-contracts",
    "ugence_agentic_proposer": REPO / "packages" / "capabilities" / "agentic-proposer",
    "ugence_jcs": REPO / "packages" / "jcs",
}

_CHECK = r'''
import dataclasses
import importlib.util
import sys
from datetime import datetime, timezone

import ugence_agentic_proposer_strategy_permission_runtime as runtime

assert runtime.__version__ == "0.1.0", runtime.__version__
assert "site-packages" in runtime.__file__, runtime.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path

import pathlib as _pl
assert (_pl.Path(runtime.__file__).resolve().parent / "py.typed").is_file(), "no py.typed"

import ugence_agentic_proposer_strategy_permission_policy as family
from ugence_agentic_proposer import (
    ReasoningStrategy, StrategyPolicyRequest, StrategyPolicyResponse,
)
from ugence_policy_authority.api import (
    AdapterRegistry, ApprovalEvidenceRef, ApprovalVerification,
    ApprovalVerificationStatus, Ed25519PolicySigner, InMemoryPolicyRegistry,
    KeyEntitlement, PolicyKeyRing, PolicyResolutionReason, SigningKey, issue_policy,
)

SINGLE = ReasoningStrategy.SINGLE_CANDIDATE_UNREVISED.value
MULTI = ReasoningStrategy.MULTI_CANDIDATE_UNREVISED.value
REF = "policy-authority/strategy-permission/reconciliation"
TENANT = "tenant-1"
T_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)
T_MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
T_TO = datetime(2027, 1, 1, tzinfo=timezone.utc)
T_AFTER = datetime(2027, 6, 1, tzinfo=timezone.utc)

ADAPTER = family.StrategyPermissionPolicyFamilyAdapter()


def metadata(digest):
    return family.StrategyPermissionPolicyMetadata(
        policy_id="strategy-permission", version="1.0.0", content_digest=digest,
        scope=family.POLICY_SCOPE_TENANT,
        lifecycle_state=family.LIFECYCLE_APPROVED_ACTIVE, tenant_id=TENANT,
        effective_from=T_FROM, effective_to=T_TO)


permitted = tuple(sorted((MULTI, SINGLE)))
draft = family.StrategyPermissionPolicy(
    metadata=metadata(family.PLACEHOLDER_CONTENT_DIGEST),
    strategy_policy_ref=REF, permitted_strategies=permitted)
policy = family.StrategyPermissionPolicy(
    metadata=metadata(ADAPTER.describe(draft).body_digest()),
    strategy_policy_ref=REF, permitted_strategies=permitted)


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
# Internal by owner ruling SURFACE=B: reached through its owning module, never
# through the package's curated surface.
from ugence_agentic_proposer_strategy_permission_runtime.composition import (
    with_strategy_permission_adapter,
)

adapters = with_strategy_permission_adapter(None)
assert family.STRATEGY_PERMISSION_ADAPTER_ID in {a.adapter_id for a in adapters.adapters}

issue_policy(
    policy=policy, record_id="rec-1",
    approval=ApprovalEvidenceRef(
        approval_ref="APPROVAL-1", approval_digest="a" * 64,
        approving_authority_id="ugence.governance.policy-approval-board"),
    approval_verifier=_ScriptApprovalVerifier(), signer=signer, registry=registry,
    adapters=adapters, issued_at=T_MID)

coordinate = family.strategy_permission_coordinate(policy.metadata)
supplied = {(TENANT, REF): coordinate}
resolver = runtime.build_strategy_policy_resolver(
    reference_map=supplied, registry=registry, signature_verifier=key_ring,
    approval_verifier=_ScriptApprovalVerifier(), adapters=adapters)


def request(*, ref=REF, tenant=TENANT, case_ref="case-1", as_of=T_MID):
    return StrategyPolicyRequest(
        strategy_policy_ref=ref, tenant_id=tenant, case_ref=case_ref, as_of=as_of)


# -- the four ratified response fields --------------------------------------
response = resolver.resolve(request=request())
assert type(response) is StrategyPolicyResponse
assert response.strategy_policy_id == "strategy-permission"
assert response.strategy_policy_version == "1.0.0"
assert type(response.strategy_policy_version) is str
assert response.strategy_policy_ref == REF
assert [m.value for m in response.permitted_strategies] == list(permitted)
assert not hasattr(response, "verified")
assert "verified" not in type(response).model_fields

# -- case_ref selects nothing ------------------------------------------------
assert resolver.resolve(request=request(case_ref="case-99")) == response

def refuses(fn, expected):
    try:
        fn()
    except expected:
        return
    raise SystemExit("a fail-closed rule did not fire: " + expected.__name__)


# -- the mapping was defensively copied --------------------------------------
# Adding a key to the mapping handed in must not widen what the resolver can
# reach, and removing the real one must not narrow it.
supplied[("tenant-attacker", "any")] = coordinate
supplied.pop((TENANT, REF))
assert resolver.resolve(request=request()).strategy_policy_id == "strategy-permission"
refuses(lambda: resolver.resolve(request=request(tenant="tenant-attacker", ref="any")),
        runtime.UnknownStrategyPolicyReferenceError)

refuses(lambda: resolver.resolve(request=request(ref=REF + "x")),
        runtime.UnknownStrategyPolicyReferenceError)
refuses(lambda: resolver.resolve(request=request(ref="policy-authority")),
        runtime.UnknownStrategyPolicyReferenceError)
refuses(lambda: resolver.resolve(request=request(tenant="tenant-elsewhere")),
        runtime.UnknownStrategyPolicyReferenceError)
refuses(lambda: runtime.build_strategy_policy_resolver(
            reference_map={(TENANT, REF): coordinate}, registry=registry,
            signature_verifier=key_ring, approval_verifier=None), TypeError)

# -- a mis-wired deployment: the key names one tenant, the coordinate another --
mis_wired = runtime.build_strategy_policy_resolver(
    reference_map={("tenant-other", REF): coordinate}, registry=registry,
    signature_verifier=key_ring, approval_verifier=_ScriptApprovalVerifier(),
    adapters=adapters)
refuses(lambda: mis_wired.resolve(request=request(tenant="tenant-other")),
        runtime.StrategyPolicyTenantScopeError)

# -- the effective window, and the reason discipline -------------------------
try:
    resolver.resolve(request=request(as_of=T_AFTER))
    raise SystemExit("an out-of-window resolution did not fail closed")
except runtime.StrategyPolicyUnresolvedError as exc:
    assert exc.reason is PolicyResolutionReason.EXPIRED
    message = str(exc).upper()
    for reason in PolicyResolutionReason:
        assert reason.value not in message, ("the cause leaked into the message: "
                                             + reason.value)

# -- a body swap under the same coordinate fails closed ----------------------
tampered = family.StrategyPermissionPolicy(
    metadata=policy.metadata, strategy_policy_ref=policy.strategy_policy_ref,
    permitted_strategies=tuple(sorted(m.value for m in ReasoningStrategy)))
registry._issued[coordinate] = dataclasses.replace(
    registry._issued[coordinate], policy=tampered)
refuses(lambda: resolver.resolve(request=request()),
        runtime.StrategyPolicyUnresolvedError)

# -- nothing that authorizes execution came along ----------------------------
for mod in ("risk_authority", "ugence_risk_authority", "actiongate_provider",
            "ugence_decision_authority", "ugence_agent_runtime", "ugence_console_api",
            "ai_hiring", "platform_freeze", "decision_governance", "requests",
            "httpx", "boto3"):
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

print("ISOLATED STRATEGY-PERMISSION-RUNTIME VERIFICATION OK")
'''


def _run(cmd, capture=False, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True, **kw)
    return subprocess.run(cmd, check=True, **kw)


def _latest(path: Path, pattern: str) -> Path:
    files = sorted(path.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} in {path}")
    return files[-1]


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

        result = _run(
            [str(py), "-m", "pip", "install", "--no-index",
             "--find-links", str(crippled), str(target)],
            capture=True, env=_isolated_env(), cwd=str(td),
        )
        combined = (result.stdout + result.stderr).lower()
        assert result.returncode != 0, (
            "the installation SUCCEEDED with "
            f"{victim.name} removed from the wheelhouse; resolution is not "
            "offline-and-local, and an index or ambient environment supplied it"
        )
        assert (
            "no matching distribution" in combined
            or "could not find a version" in combined
        ), combined[-2000:]
        for reached in ("pypi.org", "files.pythonhosted.org", "downloading http"):
            assert reached not in combined, f"pip reached an index: {reached}"
        print(f"      refused as intended, with no index contacted ({victim.name})")


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

    print("[3/7] vendor third-party dependencies — the ONLY step that may use a network")
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
        assert "--no-index" in install, install
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
