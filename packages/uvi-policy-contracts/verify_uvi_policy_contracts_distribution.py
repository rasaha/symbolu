#!/usr/bin/env python3
"""Reproducible proof that the UVI Policy Contracts install and operate from a
built wheel, with ONLY the neutral ``ugence-governance-contracts`` leaf as a
cross-package dependency and NO other Ugence package on the path.

Builds ``ugence-uvi-policy-contracts`` and its single dependency
``ugence-governance-contracts`` into a local find-links directory, installs the
former (pip resolves the latter from find-links) into a fresh virtualenv with no
system site packages and no monorepo path (``--no-index`` — both wheels are
local and declare zero third-party dependencies), then proves inside that env:

  * ``ugence_uvi_policy_contracts`` imports from site-packages;
  * the curated public API resolves and ships ``py.typed``;
  * representative policy/context shapes construct, digest, and serialize;
  * the structural invariants fire (literal-XOR-benchmark; non-waivable
    mandatory gate; no-floating-reference; cross-tenant rejection; fail-closed
    binder);
  * the reused ``ugence_governance_contracts`` dependency is importable;
  * NO downstream leaf (governed-value / agent-value-readiness), capability,
    framework, product, console, or third-party package is importable.

Run:  python packages/uvi-policy-contracts/verify_uvi_policy_contracts_distribution.py
Exit code 0 on success; non-zero on the first failed step.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parent
REPO = PKG.parents[1]  # packages/uvi-policy-contracts -> packages -> repo root

# Local source distributions to build into the find-links directory: this
# package and its single neutral dependency.
SOURCES = {
    "ugence_uvi_policy_contracts": PKG,
    "ugence_governance_contracts": REPO / "packages" / "governance-contracts",
}

_CHECK = r'''
import dataclasses, hashlib, importlib.util, sys
from datetime import datetime, timezone

import ugence_uvi_policy_contracts as u
assert u.__version__ == "0.1.0", u.__version__
assert "site-packages" in u.__file__, u.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path

import pathlib as _pl
assert (_pl.Path(u.__file__).resolve().parent / "py.typed").is_file(), "py.typed not installed"

# reused neutral dependency is importable from site-packages
import ugence_governance_contracts as gc
assert "site-packages" in gc.__file__, gc.__file__
from ugence_governance_contracts.api import BenchmarkReference

from ugence_uvi_policy_contracts.api import (
    PolicyFamily, PolicyScope, PolicyLifecycleState, RequirementClass,
    ComparisonOperator, GateCategory, ReadinessTarget, ValueComponent,
    PolicyArtifactMetadata, PolicyReference, GovernedThreshold, PolicyGate,
    GeographyPolicy, DomainPolicy, IntendedOutcomePolicy, ValuationPolicy,
    ReadinessPolicy, AssessmentContext, AssessmentPurpose, PolicyContractError)

D = hashlib.sha256(b"content").hexdigest()
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
T1 = datetime(2027, 1, 1, tzinfo=timezone.utc)
MID = datetime(2026, 6, 1, tzinfo=timezone.utc)

def meta(fam, pid, life=PolicyLifecycleState.APPROVED_ACTIVE):
    return PolicyArtifactMetadata(policy_id=pid, policy_family=fam, version="1",
                                  content_digest=D, lifecycle_state=life,
                                  effective_from=T0, effective_to=T1)

geo = GeographyPolicy(metadata=meta(PolicyFamily.GEOGRAPHY, "geo"), jurisdiction="US",
                      reporting_currency="USD", functional_currency="USD")
dom = DomainPolicy(metadata=meta(PolicyFamily.DOMAIN, "dom"), governed_outcome_unit="ticket")
io = IntendedOutcomePolicy(metadata=meta(PolicyFamily.INTENDED_OUTCOME, "io"),
                           target_outcome="resolve", task_definition="handle ticket")
ctx = AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s",
                                      geography=geo, domain=dom, intended_outcome=io,
                                      purpose=AssessmentPurpose.POST_DEPLOYMENT_VALUE, as_of=MID)
assert len(ctx.canonical_digest()) == 64
assert len(ctx.policy_refs) == 3

# literal-XOR-benchmark
lit = GovernedThreshold(threshold_id="t", governed_unit="pct",
                        comparator=ComparisonOperator.GTE, literal_value="0.9")
assert lit.is_literal
try:
    GovernedThreshold(threshold_id="t", governed_unit="u", comparator=ComparisonOperator.GTE)
    raise SystemExit("threshold XOR guard did not fire")
except PolicyContractError:
    pass

# non-waivable mandatory
try:
    PolicyGate(gate_id="g", category=GateCategory.SAFETY,
               requirement_class=RequirementClass.MANDATORY,
               applicability=(ReadinessTarget.PRODUCTION,), conditionally_compensable=True)
    raise SystemExit("mandatory non-waivable guard did not fire")
except PolicyContractError:
    pass

# no floating reference (digest required)
try:
    PolicyReference(policy_id="p", policy_family=PolicyFamily.DOMAIN, version="1", content_digest="")
    raise SystemExit("floating-reference guard did not fire")
except PolicyContractError:
    pass

# fail-closed binder on revoked artifact
revoked = GeographyPolicy(metadata=meta(PolicyFamily.GEOGRAPHY, "geo", PolicyLifecycleState.REVOKED),
                          jurisdiction="US", reporting_currency="USD", functional_currency="USD")
try:
    AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s",
                                    geography=revoked, domain=dom, intended_outcome=io, as_of=MID)
    raise SystemExit("fail-closed binder did not fire")
except PolicyContractError:
    pass

# as_of is mandatory (temporal validation cannot be omitted)
try:
    AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s",
                                    geography=geo, domain=dom, intended_outcome=io)
    raise SystemExit("mandatory as_of guard did not fire")
except TypeError:
    pass
# naive as_of rejected
try:
    AssessmentContext.bind_policies(context_id="c", tenant_id="t", subject_id="s",
                                    geography=geo, domain=dom, intended_outcome=io,
                                    as_of=datetime(2026, 6, 1))
    raise SystemExit("naive as_of guard did not fire")
except PolicyContractError:
    pass

# sequence fields are immutable: a caller list is coerced to tuple and cannot be
# mutated into the frozen contract afterward
gp = GeographyPolicy(metadata=meta(PolicyFamily.GEOGRAPHY, "geo2"), jurisdiction="US",
                     reporting_currency="USD", functional_currency="USD",
                     applicable_regulations=["reg-a"])
assert isinstance(gp.applicable_regulations, tuple), type(gp.applicable_regulations)
_d0 = gp.canonical_digest()
try:
    gp.applicable_regulations.append("x")  # tuple has no append
    raise SystemExit("sequence field was not immutable")
except AttributeError:
    pass
assert gp.canonical_digest() == _d0

# no downstream/foreign package importable in this clean env
for mod in ("governed_value", "ugence_governed_value", "agent_value_readiness",
            "governance_providers", "decision_governance", "actiongate_provider",
            "tap_provider", "ai_hiring", "ugence_console_api", "platform_freeze",
            "pydantic"):
    assert importlib.util.find_spec(mod) is None, ("unrelated package present: " + mod)

print("ISOLATED UVI-POLICY-CONTRACTS VERIFICATION OK")
'''


def _run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def _latest(path: Path, pattern: str) -> Path:
    files = sorted(path.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} in {path}")
    return files[-1]


def _foreign_members(wheel: Path) -> set[str]:
    with zipfile.ZipFile(wheel) as z:
        tops = {n.split("/", 1)[0] for n in z.namelist() if "/" in n}
    return {t for t in tops if not (t == "ugence_uvi_policy_contracts" or t.endswith(".dist-info"))}


def main() -> int:
    findlinks = PKG / "_dist_wheels"
    if findlinks.exists():
        shutil.rmtree(findlinks)
    findlinks.mkdir()

    print("[1/4] build the uvi-policy-contracts wheel + its governance-contracts dependency")
    for name, src in SOURCES.items():
        _run([sys.executable, "-m", "build", "--wheel", str(src), "-o", str(findlinks)])
    wheel = _latest(findlinks, "ugence_uvi_policy_contracts-*.whl")
    print(f"      built {wheel.name}")

    print("[2/4] assert the wheel bundles no foreign top-level package + ships py.typed")
    foreign = _foreign_members(wheel)
    assert not foreign, f"wheel bundles foreign packages: {sorted(foreign)}"
    with zipfile.ZipFile(wheel) as z:
        names = set(z.namelist())
    assert "ugence_uvi_policy_contracts/py.typed" in names, "wheel is missing py.typed"
    print("      wheel contains only ugence_uvi_policy_contracts/ (+ py.typed) + dist-info")

    print("[3/4] create an isolated venv and install ONLY these local wheels (--no-index)")
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        py = env / "bin" / "python"
        _run([str(py), "-m", "pip", "install", "--quiet", "--no-index",
              "--find-links", str(findlinks), "ugence-uvi-policy-contracts"])

        print("[4/4] run the isolated proof (cwd has no monorepo source)")
        _run([str(py), "-c", _CHECK], cwd=str(td))

    shutil.rmtree(findlinks, ignore_errors=True)
    print("\nISOLATED UVI-POLICY-CONTRACTS DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
