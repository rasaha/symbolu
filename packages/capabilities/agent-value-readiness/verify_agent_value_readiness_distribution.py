#!/usr/bin/env python3
"""Reproducible proof that the Agent Value Readiness contracts install and operate
from a built wheel, with ONLY the two neutral contract leaves as cross-package
dependencies and NO ``governed-value`` or other foreign package on the path.

Builds ``ugence-agent-value-readiness`` and its two dependencies
(``ugence-uvi-policy-contracts``, ``ugence-governance-contracts``) into a local
find-links directory, installs the former (pip resolves the latter two) into a
fresh venv with no system site packages and no monorepo path (``--no-index`` —
all wheels are local, zero third-party deps), then proves inside that env:

  * ``ugence_agent_value_readiness`` imports from site-packages, ships py.typed;
  * the curated API resolves;
  * representative readiness contracts construct, digest, and enforce structure
    (distinct indicator types; non-waivable mandatory condition; advisory-composite
    Decimal + float rejection; target/classification consistency; immutability);
  * NO ``governed_value`` / capability / product / framework / third-party package
    is importable.

Run:  python packages/capabilities/agent-value-readiness/verify_agent_value_readiness_distribution.py
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
REPO = PKG.parents[2]  # packages/capabilities/agent-value-readiness -> capabilities -> packages -> repo

SOURCES = {
    "ugence_agent_value_readiness": PKG,
    "ugence_uvi_policy_contracts": REPO / "packages" / "uvi-policy-contracts",
    "ugence_governance_contracts": REPO / "packages" / "governance-contracts",
}

_CHECK = r'''
import dataclasses, hashlib, importlib.util, sys
from datetime import datetime, timezone
from decimal import Decimal

import ugence_agent_value_readiness as r
assert r.__version__ == "0.1.0", r.__version__
assert "site-packages" in r.__file__, r.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path
import pathlib as _pl
assert (_pl.Path(r.__file__).resolve().parent / "py.typed").is_file(), "py.typed not installed"

from ugence_governance_contracts.api import MetricClaim, SourceBasis, TransformationMethod, AssessmentWindow
from ugence_uvi_policy_contracts.api import (
    PolicyArtifactMetadata, PolicyReference, PolicyFamily, PolicyLifecycleState,
    AssessmentContext, GeographyPolicy, DomainPolicy, IntendedOutcomePolicy,
    ReadinessTarget, RequirementClass)
from ugence_agent_value_readiness.api import (
    IntelligenceFitnessResult, CapabilityReadinessResult, AdoptionReadinessResult,
    GateResult, GateStatus, ConditionSet, ConditionStatus, AdvisoryComposite,
    AgentValueReadinessDetermination, ReadinessClassification, ReadinessIndicatorClass,
    IntelligenceDimension, CapabilityDimension, AdoptionDimension, CapabilityDemonstration,
    ReadinessContractError)

D = hashlib.sha256(b"c").hexdigest()
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc); T1 = datetime(2027, 1, 1, tzinfo=timezone.utc); MID = datetime(2026, 6, 1, tzinfo=timezone.utc)
WIN = AssessmentWindow(start=T0, end=MID)
def meta(f, p): return PolicyArtifactMetadata(policy_id=p, policy_family=f, version="1", content_digest=D, lifecycle_state=PolicyLifecycleState.APPROVED_ACTIVE, effective_from=T0, effective_to=T1)
geo = GeographyPolicy(metadata=meta(PolicyFamily.GEOGRAPHY, "g"), jurisdiction="US", reporting_currency="USD", functional_currency="USD")
dom = DomainPolicy(metadata=meta(PolicyFamily.DOMAIN, "d"), governed_outcome_unit="ticket")
io = IntendedOutcomePolicy(metadata=meta(PolicyFamily.INTENDED_OUTCOME, "i"), target_outcome="o", task_definition="t")
ctx = AssessmentContext.bind_policies(context_id="ctx1", tenant_id="t1", subject_id="a1", geography=geo, domain=dom, intended_outcome=io, as_of=MID)
rdy = PolicyReference(policy_id="r", policy_family=PolicyFamily.READINESS, version="1", content_digest=D)
claim = MetricClaim(claim_id="c1", tenant_id="t1", subject_id="a1", metric_id="accuracy", value="0.95", governed_unit="ratio", source_basis=SourceBasis.OBSERVED, transformation_method=TransformationMethod.DIRECT, assessment_window=WIN)
intel = IntelligenceFitnessResult(result_id="ir1", tenant_id="t1", subject_id="a1", context_id="ctx1", task_or_outcome_ref="i", dimension=IntelligenceDimension.ACCURACY, claim=claim, requirement_class=RequirementClass.MANDATORY, applicable_targets=[ReadinessTarget.PILOT], status=GateStatus.PASS)
assert intel.indicator_class is ReadinessIndicatorClass.INTELLIGENCE
gate = GateResult(gate_id="g1", readiness_policy_ref=rdy, gate_kind=RequirementClass.MANDATORY, requested_target=ReadinessTarget.PILOT, applicable=True, status=GateStatus.PASS)
det = AgentValueReadinessDetermination(assessment_id="a1", tenant_id="t1", subject_id="a1", context=ctx, readiness_policy_ref=rdy, requested_target=ReadinessTarget.PILOT, classification=ReadinessClassification.PILOT_READY, created_at=MID, intelligence_results=[intel], gate_results=[gate])
assert len(det.canonical_digest()) == 64
assert det.is_advisory is True

# non-waivable mandatory condition
try:
    ConditionSet(condition_id="c", source_gate_or_finding_ref="g", concern_requirement_class=RequirementClass.MANDATORY, current_status=ConditionStatus.PROPOSED)
    raise SystemExit("mandatory-condition guard did not fire")
except ReadinessContractError:
    pass
# composite rejects float
try:
    AdvisoryComposite(method_id="m", method_version="1", score=0.8, scale_min=Decimal("0"), scale_max=Decimal("1"), component_result_refs=["r1"])
    raise SystemExit("composite float guard did not fire")
except ReadinessContractError:
    pass
# target/classification consistency
try:
    AgentValueReadinessDetermination(assessment_id="a", tenant_id="t1", subject_id="a1", context=ctx, readiness_policy_ref=rdy, requested_target=ReadinessTarget.PRODUCTION, classification=ReadinessClassification.PILOT_READY, created_at=MID)
    raise SystemExit("target/classification guard did not fire")
except ReadinessContractError:
    pass
# immutability: list coerced, mutation-proof
evid = ["e1"]
im = IntelligenceFitnessResult(result_id="ir2", tenant_id="t1", subject_id="a1", context_id="ctx1", task_or_outcome_ref="i", dimension=IntelligenceDimension.RELIABILITY, claim=claim, requirement_class=RequirementClass.ADVISORY, applicable_targets=[ReadinessTarget.PILOT], status=GateStatus.PASS, evidence_refs=evid)
d0 = im.canonical_digest(); evid.append("x")
assert im.evidence_refs == ("e1",) and im.canonical_digest() == d0
# no financial fields
for shape in (IntelligenceFitnessResult, CapabilityReadinessResult, AdoptionReadinessResult, GateResult, ConditionSet, AdvisoryComposite, AgentValueReadinessDetermination):
    for f in dataclasses.fields(shape):
        low = f.name.lower()
        assert not any(t in low for t in ("money", "currency", "roi", "benefit", "cost", "multiplier", "revenue")), (shape.__name__, f.name)

for mod in ("governed_value", "ugence_governed_value", "governance_providers", "decision_governance", "ai_hiring", "pydantic"):
    assert importlib.util.find_spec(mod) is None, ("unrelated package present: " + mod)

print("ISOLATED AGENT-VALUE-READINESS VERIFICATION OK")
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
    return {t for t in tops if not (t == "ugence_agent_value_readiness" or t.endswith(".dist-info"))}


def main() -> int:
    findlinks = PKG / "_dist_wheels"
    if findlinks.exists():
        shutil.rmtree(findlinks)
    findlinks.mkdir()

    print("[1/4] build the readiness wheel + its two contract-leaf dependencies")
    for name, src in SOURCES.items():
        _run([sys.executable, "-m", "build", "--wheel", str(src), "-o", str(findlinks)])
    wheel = _latest(findlinks, "ugence_agent_value_readiness-*.whl")
    print(f"      built {wheel.name}")

    print("[2/4] assert the wheel bundles no foreign top-level package + ships py.typed")
    foreign = _foreign_members(wheel)
    assert not foreign, f"wheel bundles foreign packages: {sorted(foreign)}"
    with zipfile.ZipFile(wheel) as z:
        names = set(z.namelist())
    assert "ugence_agent_value_readiness/py.typed" in names, "wheel is missing py.typed"
    print("      wheel contains only ugence_agent_value_readiness/ (+ py.typed) + dist-info")

    print("[3/4] create an isolated venv and install ONLY these local wheels (--no-index)")
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        py = env / "bin" / "python"
        _run([str(py), "-m", "pip", "install", "--quiet", "--no-index",
              "--find-links", str(findlinks), "ugence-agent-value-readiness"])

        print("[4/4] run the isolated proof (cwd has no monorepo source)")
        _run([str(py), "-c", _CHECK], cwd=str(td))

    shutil.rmtree(findlinks, ignore_errors=True)
    print("\nISOLATED AGENT-VALUE-READINESS DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
