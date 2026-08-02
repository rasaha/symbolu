#!/usr/bin/env python3
"""Reproducible independent-packaging proof for the canonical Governance Provider
Framework distribution ``ugence-governance-provider-framework``.

Builds the local wheels, then installs them into fresh virtualenvs with NO monorepo
path and proves the framework behaves outside the repository. Covers the six
isolated scenarios required by the migration (§21):

  1. canonical wheel only .......... core installs (contracts only), imports, runs
                                     registry/resolution/conformance; NO TAP/ActionGate
                                     bundled; NO Decision Authority pulled.
  2. legacy wheel + canonical dep .. ``dgm-provider-framework`` pulls the canonical
                                     wheel[adapters]; ``governance_providers`` legacy
                                     namespace (top-level + deep) resolves to the SAME
                                     objects as the canonical package.
  3. canonical core WITHOUT DA ..... same env as (1): ``.api``/``.adapters`` require
                                     the optional kernel; the core does not.
  4. optional adapter install ...... canonical wheel[adapters] exposes the full public
                                     API (48 symbols), adapters, registry, resolve.
  5. TAP provider installed-wheel ... ``dgm-tap-provider`` runs against the installed
                                     canonical framework.
  6. ActionGate provider installed .. ``dgm-actiongate-provider`` runs against it.

Run:  python packages/governance-provider-framework/verify_governance_provider_framework_distribution.py
Exit 0 on success; non-zero on the first failed step.
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
REPO = PKG.parents[1]

# Local source distributions to build into the find-links directory.
SOURCES = {
    "ugence_governance_contracts": REPO / "packages" / "governance-contracts",
    "ugence_governance_provider_framework": PKG,
    "ugence_decision_authority": REPO / "packages" / "capabilities" / "decision-authority",
    "decision_governance": REPO / "packaging" / "decision-governance",
    "dgm_provider_framework": REPO / "packaging" / "dgm-provider-framework",
    "dgm_tap_provider": REPO / "packaging" / "dgm-tap-provider",
    "dgm_actiongate_provider": REPO / "packaging" / "dgm-actiongate-provider",
}

# ---- isolated proofs (run inside each clean venv) -------------------------------

CORE_CHECK = r'''
import importlib.util, sys
import ugence_governance_provider_framework as gpf
assert gpf.__version__ == "0.1.0", gpf.__version__
assert "site-packages" in gpf.__file__, gpf.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path
# core imports (no Decision Authority present)
from ugence_governance_provider_framework.registry import ProviderRegistry
from ugence_governance_provider_framework.resolution import resolve, ResolutionRequest
from ugence_governance_provider_framework.configuration import ProvidersConfiguration
from ugence_governance_provider_framework.observability import record_invocation
from ugence_governance_provider_framework.fingerprint import fingerprint
from ugence_governance_provider_framework.version import CONTRACT_VERSION
from ugence_governance_provider_framework.metadata import ProviderKind
from ugence_governance_provider_framework.reference import (
    DeterministicAssertionProvider, DeterministicActionGovernanceProvider,
    DeterministicExecutionProvider)
import ugence_governance_provider_framework.conformance  # noqa
assert CONTRACT_VERSION == "1.0.0"
# registry + deterministic resolution workflow
reg = ProviderRegistry()
for c in (DeterministicAssertionProvider, DeterministicActionGovernanceProvider,
          DeterministicExecutionProvider):
    reg.register(c().descriptor())
prov, rec = resolve(reg, ResolutionRequest(kind=ProviderKind.ASSERTION_GOVERNANCE))
assert prov.descriptor().provider_id == "deterministic-assertion", prov
# fingerprint determinism preserved
assert fingerprint({"a": 1}) == fingerprint({"a": 1})
# Decision Authority is NOT installed.
assert importlib.util.find_spec("decision_governance") is None, "DA should be absent"
# The canonical public API AND the kernel-bound adapters IMPORT without Decision
# Authority (the dependency is optional); only INVOKING an adapter needs the extra.
import ugence_governance_provider_framework.api as _api
assert len(_api.__all__) == 48, len(_api.__all__)
import ugence_governance_provider_framework.adapters  # imports fine without DA
from ugence_governance_provider_framework.api import ActionGovernanceControlPlaneAdapter
_adapter = ActionGovernanceControlPlaneAdapter(DeterministicActionGovernanceProvider())
try:
    _adapter.authorize(object(), object())
    raise SystemExit("adapter invoked without Decision Authority present")
except ModuleNotFoundError as _e:
    assert "ugence-governance-provider-framework[adapters]" in str(_e), str(_e)
# contracts leaf present; NO capability/provider/app bundled or pulled
assert importlib.util.find_spec("ugence_governance_contracts") is not None
for mod in ("tap_provider", "actiongate_provider", "ai_hiring", "domains",
            "applications", "ugence_decision_authority", "ugence_console_api"):
    assert importlib.util.find_spec(mod) is None, ("unexpected package: " + mod)
print("CORE-ONLY (no Decision Authority) VERIFICATION OK")
'''

ADAPTERS_CHECK = r'''
import sys
import ugence_governance_provider_framework as gpf
assert "site-packages" in gpf.__file__, gpf.__file__
assert not any("/symbolu" in p for p in sys.path), sys.path
from ugence_governance_provider_framework import api
assert len(api.__all__) == 48, len(api.__all__)
from ugence_governance_provider_framework.api import (
    ProviderRegistry, resolve, ResolutionRequest,
    ActionGovernanceControlPlaneAdapter, ExternalExecutionAdapter,
    AssertionAssessmentIntegration)
from ugence_governance_provider_framework.metadata import ProviderKind
from ugence_governance_provider_framework.reference import DeterministicActionGovernanceProvider
reg = ProviderRegistry()
reg.register(DeterministicActionGovernanceProvider().descriptor())
prov, rec = resolve(reg, ResolutionRequest(kind=ProviderKind.ACTION_GOVERNANCE))
assert prov.descriptor().provider_id == "deterministic-action", prov
# kernel-bound adapter constructs against the installed decision_governance facade
import decision_governance.api  # noqa
print("CANONICAL[adapters] FULL-API VERIFICATION OK")
'''

LEGACY_CHECK = r'''
import sys
import governance_providers as gp
import ugence_governance_provider_framework as canon
assert gp.__version__ == "0.1.0", gp.__version__
assert not any("/symbolu" in p for p in sys.path), sys.path
# legacy deep imports resolve to the SAME objects as the canonical package
from governance_providers.api import ProviderRegistry as LReg
from ugence_governance_provider_framework.api import ProviderRegistry as CReg
assert LReg is CReg
from governance_providers.contracts.action import ActionGovernanceOutcome
from governance_providers.reference import DeterministicAssertionProvider
from governance_providers.version import CONTRACT_VERSION
assert CONTRACT_VERSION == "1.0.0"
import governance_providers.conformance, governance_providers.adapters  # noqa
assert sys.modules["governance_providers.registry"] is \
       sys.modules["ugence_governance_provider_framework.registry"]
print("LEGACY-NAMESPACE (dgm-provider-framework) VERIFICATION OK")
'''

TAP_CHECK = r'''
import sys
import tap_provider
from tap_provider.api import build_tap_provider  # noqa
# runs against the INSTALLED canonical framework
import ugence_governance_provider_framework.api as gpfapi
assert "site-packages" in gpfapi.__file__, gpfapi.__file__
import governance_providers.api as legacy
assert legacy.ProviderRegistry is gpfapi.ProviderRegistry
prov = build_tap_provider()
d = prov.descriptor()
assert d.kind.name == "ASSERTION_GOVERNANCE", d.kind
print("TAP-PROVIDER-ON-INSTALLED-FRAMEWORK VERIFICATION OK")
'''

ACTIONGATE_CHECK = r'''
import sys
import actiongate_provider
from actiongate_provider.api import build_actiongate_provider  # noqa
import ugence_governance_provider_framework.api as gpfapi
assert "site-packages" in gpfapi.__file__, gpfapi.__file__
prov = build_actiongate_provider()
d = prov.descriptor()
assert d.kind.name == "ACTION_GOVERNANCE", d.kind
print("ACTIONGATE-PROVIDER-ON-INSTALLED-FRAMEWORK VERIFICATION OK")
'''


def _run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, check=True, **kw)


def _latest(path: Path, pattern: str) -> Path:
    files = sorted(path.glob(pattern))
    if not files:
        raise FileNotFoundError(f"no {pattern} in {path}")
    return files[-1]


def _wheel_tops(wheel: Path) -> set[str]:
    with zipfile.ZipFile(wheel) as z:
        return {n.split("/", 1)[0] for n in z.namelist() if "/" in n}


def _new_venv(td: Path, name: str) -> Path:
    env = td / name
    venv.create(env, with_pip=True, clear=True, system_site_packages=False)
    return env / "bin" / "python"


def main() -> int:
    findlinks = PKG / "_dist_wheels"
    if findlinks.exists():
        shutil.rmtree(findlinks)
    findlinks.mkdir()

    print("[1] build local wheels (canonical + contracts + kernel + compat + providers)")
    for src in dict.fromkeys(SOURCES.values()):
        _run([sys.executable, "-m", "build", "--wheel", str(src), "-o", str(findlinks)])

    canon = _latest(findlinks, "ugence_governance_provider_framework-*.whl")
    print(f"    canonical wheel: {canon.name}")

    print("[2] canonical wheel bundles only its namespace, no tests, no providers")
    tops = _wheel_tops(canon)
    foreign = {t for t in tops
               if not (t == "ugence_governance_provider_framework" or t.endswith(".dist-info"))}
    assert not foreign, f"canonical wheel bundles foreign packages: {sorted(foreign)}"
    with zipfile.ZipFile(canon) as z:
        names = z.namelist()
    assert not any("/tests/" in n for n in names), "canonical wheel bundles tests"
    for bad in ("tap_provider", "actiongate_provider", "ugence_governance_contracts",
                "decision_governance", "ai_hiring"):
        assert not any(n.startswith(bad + "/") for n in names), f"wheel bundles {bad}"
    print("    ok: only ugence_governance_provider_framework/ + dist-info")

    with tempfile.TemporaryDirectory() as _td:
        td = Path(_td)

        print("[3] SCENARIO 1+3: canonical wheel only (core, no Decision Authority)")
        py = _new_venv(td, "core")
        _run([str(py), "-m", "pip", "install", "--quiet", "--find-links", str(findlinks),
              "ugence-governance-provider-framework"])
        _run([str(py), "-c", CORE_CHECK], cwd=str(td))

        print("[4] SCENARIO 4: canonical wheel[adapters] (full public API)")
        py = _new_venv(td, "adapters")
        _run([str(py), "-m", "pip", "install", "--quiet", "--find-links", str(findlinks),
              "ugence-governance-provider-framework[adapters]"])
        _run([str(py), "-c", ADAPTERS_CHECK], cwd=str(td))

        print("[5] SCENARIO 2: legacy wheel (dgm-provider-framework) + canonical dep")
        py = _new_venv(td, "legacy")
        _run([str(py), "-m", "pip", "install", "--quiet", "--find-links", str(findlinks),
              "dgm-provider-framework"])
        _run([str(py), "-c", LEGACY_CHECK], cwd=str(td))

        print("[6] SCENARIO 5: TAP provider on the installed canonical framework")
        py = _new_venv(td, "tap")
        _run([str(py), "-m", "pip", "install", "--quiet", "--find-links", str(findlinks),
              "dgm-tap-provider"])
        _run([str(py), "-c", TAP_CHECK], cwd=str(td))

        print("[7] SCENARIO 6: ActionGate provider on the installed canonical framework")
        py = _new_venv(td, "actiongate")
        _run([str(py), "-m", "pip", "install", "--quiet", "--find-links", str(findlinks),
              "dgm-actiongate-provider"])
        _run([str(py), "-c", ACTIONGATE_CHECK], cwd=str(td))

    shutil.rmtree(findlinks, ignore_errors=True)
    print("\nINDEPENDENT GOVERNANCE-PROVIDER-FRAMEWORK DISTRIBUTION VERIFIED ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
