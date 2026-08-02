"""Governance Provider Framework — pluggable governance capabilities for DGM.

An application-layer framework that lets specialized governance capabilities plug
into DGM as interchangeable peer providers, without any dependency from the
kernel to a vendor implementation. Three distinct, non-interchangeable families:
assertion governance (future TAP), action governance (future ActionGate), and
external execution.

Dependency direction: applications → governance_providers → decision_governance.api.
The kernel never imports this framework. Import the public surface from
``governance_providers.api``.
"""
from __future__ import annotations


def _ensure_governance_contracts_importable() -> None:
    """Source-checkout compatibility: the neutral contracts were extracted to the
    canonical leaf package ``ugence_governance_contracts`` (this framework's
    ``errors``/``lifecycle``/``metadata``/``contracts`` modules are now re-export
    shims that import it). When the package is installed as a wheel it is already
    importable and this is a no-op; only in an uninstalled source checkout does
    this put ``packages/governance-contracts/src`` on ``sys.path``. No other effect.
    """
    import importlib.util

    if importlib.util.find_spec("ugence_governance_contracts") is not None:
        return
    import pathlib
    import sys

    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "packages" / "governance-contracts" / "src"
        if (cand / "ugence_governance_contracts" / "__init__.py").exists():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            return


_ensure_governance_contracts_importable()

from .version import __version__

__all__ = ["__version__"]
