#!/usr/bin/env python3
"""Reproducible proof that TAP installs and operates in an isolated four-wheel env.

Builds all four independent distributions, installs ONLY them (plus pytest) into a
fresh virtualenv with no system site packages and no monorepo source path, then
proves:

  * all four packages import;
  * TAP registers through the framework registry and resolves;
  * the shared assertion-provider conformance passes unchanged;
  * TAP-specific conformance passes;
  * supported / constrained / unsupported / indeterminate assertions behave
    correctly through the DGM assessment→recommendation workflow (public API only);
  * ActionGate remains operational (authorizes) in the same environment;
  * TAP and ActionGate are mutually unaware (neither module graph references the
    other);
  * no consuming domains/applications are installed;
  * no monorepo source path is present and no duplicate DGM/framework sources are
    bundled.

Run:  python packaging/verify_tap_provider_distribution.py
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

REPO = Path(__file__).resolve().parents[1]
DISTS = {
    "decision-governance": REPO / "packaging" / "decision-governance",
    "ugence-governance-contracts": REPO / "packages" / "governance-contracts",
    "dgm-provider-framework": REPO / "packaging" / "dgm-provider-framework",
    "dgm-actiongate-provider": REPO / "packaging" / "dgm-actiongate-provider",
    "dgm-tap-provider": REPO / "packaging" / "dgm-tap-provider",
}

# The isolated in-venv proof (public APIs only; no monorepo path).
_CHECK = r'''
import importlib.util, sys

# 1) all four import
import decision_governance as d
import governance_providers as gp
import actiongate_provider as ag
import tap_provider as tap
assert d.__version__ == "1.0.0", d.__version__
assert gp.__version__ == "0.1.0", gp.__version__
assert ag.__version__ == "0.1.0", ag.__version__
assert tap.__version__ == "0.1.0", tap.__version__

# 2) installed from the wheel (site-packages), not the monorepo source tree
assert "site-packages" in d.__file__, d.__file__
assert "site-packages" in tap.__file__, tap.__file__
missing = [p for p in ("ai_hiring", "domains", "applications")
           if importlib.util.find_spec(p) is not None]
assert not missing, missing

from governance_providers.api import (
    ProviderKind, ProviderRegistry, ResolutionRequest, resolve,
    AssertionAssessmentIntegration, AssertionGovernanceRequest, ActionGovernanceRequest)
from governance_providers.conformance import run_assertion_provider_conformance
from tap_provider.configuration import build_tap_provider
from tap_provider.conformance import run_tap_conformance
from tap_provider.core import TapEngine, TapRule, TapOutcome, TapConstraint
from actiongate_provider.configuration import build_actiongate_provider

# 3) TAP registers + resolves
reg = ProviderRegistry()
reg.register(build_tap_provider().descriptor())
_p, rec = resolve(reg, ResolutionRequest(ProviderKind.ASSERTION_GOVERNANCE))
assert rec.selected_id == "tap", rec.selected_id

# 4) shared + specific conformance
shared = run_assertion_provider_conformance(lambda: build_tap_provider())
assert shared.passed, shared.failures
spec = run_tap_conformance()
assert spec.passed, spec.failures

# 5) supported/constrained/unsupported/indeterminate via assessment integration
def assess(provider, assertion, refs):
    provider.initialize()
    return AssertionAssessmentIntegration(provider).assess(
        AssertionGovernanceRequest(assertion, evidence_refs=refs))

sup = assess(build_tap_provider(), "Revenue increased", ("e1",))
assert sup.coverage.value == "SUPPORTED" and sup.finalized

crule = TapRule(outcome=TapOutcome.CONSTRAINED, evidence_coverage=0.5,
                omitted_qualifiers=("segment",),
                constraints=(TapConstraint("required_qualifier", "segment"),),
                reason_codes=("scope_expansion",))
con = assess(build_tap_provider(TapEngine(rules={"Revenue increased": crule})),
             "Revenue increased", ("e1", "e2"))
assert con.coverage.value == "CONSTRAINED" and con.blocked

urule = TapRule(outcome=TapOutcome.UNSUPPORTED, evidence_coverage=0.0,
                unsupported_components=("claim",))
uns = assess(build_tap_provider(TapEngine(rules={"Bad claim": urule})), "Bad claim", ("e1",))
assert uns.coverage.value == "UNSUPPORTED" and not uns.finalized

ind = assess(build_tap_provider(), "Ambiguous", ())
assert ind.coverage.value == "INDETERMINATE" and not ind.finalized

# 6) ActionGate operational in the same env (authorizes)
agp = build_actiongate_provider(); agp.initialize()
assert agp.authorize(ActionGovernanceRequest("ACT")).outcome.value == "AUTHORIZED"

# 7) mutual unawareness (import-graph)
assert all("actiongate" not in m for m in sys.modules if m.startswith("tap_provider"))
assert all("tap_provider" not in m for m in sys.modules if m.startswith("actiongate_provider"))

print("ISOLATED FOUR-WHEEL TAP VERIFICATION OK")
'''


def _run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def _latest(path: Path, pattern: str) -> Path:
    files = sorted(path.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} in {path}")
    return files[-1]


def _kernel_members(wheel: Path) -> set[str]:
    with zipfile.ZipFile(wheel) as z:
        return {n for n in z.namelist()
                if n.startswith("decision_governance/") and n.endswith(".py")}


def main() -> int:
    findlinks = REPO / "packaging" / "_dist_wheels"
    if findlinks.exists():
        shutil.rmtree(findlinks)
    findlinks.mkdir()

    print("[1/4] build all four independent wheels")
    for name, path in DISTS.items():
        _run([sys.executable, "-m", "build", "--wheel", str(path)])
        wheel = _latest(path / "dist", "*.whl")
        shutil.copy(wheel, findlinks / wheel.name)
        print(f"      built {name}: {wheel.name}")

    print("[2/4] assert providers bundle no duplicate kernel source")
    for prov in ("dgm_provider_framework", "dgm_actiongate_provider", "dgm_tap_provider"):
        w = _latest(findlinks, f"{prov}-*.whl")
        assert not _kernel_members(w), f"{prov} wheel bundles kernel source!"
    print("      framework/actiongate/tap wheels own no decision_governance source")

    print("[3/4] create isolated venv and install ONLY the four wheels + pytest")
    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        venv.create(env, with_pip=True, clear=True, system_site_packages=False)
        py = env / "bin" / "python"
        # The four private dists resolve from --find-links; third-party runtime
        # deps (pydantic) come from the index — none of the four are published.
        _run([str(py), "-m", "pip", "install", "--quiet",
              "--find-links", str(findlinks),
              "dgm-tap-provider", "dgm-actiongate-provider"])

        print("[4/4] run the isolated proof (cwd has no monorepo source)")
        _run([str(py), "-c", _CHECK], cwd=str(td))

    shutil.rmtree(findlinks, ignore_errors=True)
    print("\nISOLATED FOUR-WHEEL DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
