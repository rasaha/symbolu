"""COMPATIBILITY-ONLY legacy namespace for Cloud Scaling Operations.

Canonical package: ``ugence_cloud_scaling_operations`` (distribution
``ugence-cloud-scaling-operations``, under
``packages/capabilities/cloud-scaling-operations/src``).

The operations code was **moved** into the canonical package. This module makes the
legacy dotted names (``cloud_scaling_operations.action.k8s_actuator`` …) resolve to the
*same object* in the canonical package — object identity preserved — so existing
monorepo imports keep working unchanged.

**MONOREPO-ONLY** — not packaged, not on PyPI, not a stable distributed API. In a
wheel-only install only ``ugence_cloud_scaling_operations`` exists. No execution,
actuation, or orchestration logic lives here; this is a thin routing shim.
"""

from __future__ import annotations

import importlib as _importlib
import sys as _sys

_CANON = "ugence_cloud_scaling_operations"
_LEGACY = "cloud_scaling_operations"


def _ensure_canonical_importable() -> None:
    import importlib.util

    if importlib.util.find_spec(_CANON) is not None:
        return
    import pathlib

    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "packages" / "capabilities" / "cloud-scaling-operations" / "src"
        if (cand / _CANON / "__init__.py").exists():
            if str(cand) not in _sys.path:
                _sys.path.insert(0, str(cand))
            return


_ensure_canonical_importable()


class _OpsFinder:
    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        if fullname.startswith(_LEGACY + "."):
            import importlib.util

            return importlib.util.spec_from_loader(fullname, cls)
        return None

    @classmethod
    def create_module(cls, spec):
        return cls._load(spec.name)

    @classmethod
    def exec_module(cls, module):
        return None

    @classmethod
    def _load(cls, fullname):
        if fullname in _sys.modules:
            return _sys.modules[fullname]
        target = _CANON + fullname[len(_LEGACY):]
        real = _importlib.import_module(target)
        _sys.modules[fullname] = real
        return real


if not any(f is _OpsFinder for f in _sys.meta_path):
    _sys.meta_path.insert(0, _OpsFinder)
