"""COMPATIBILITY-ONLY legacy namespace for the Cloud Scaling Controller.

Canonical package: ``ugence_cloud_scaling_controller``
(distribution ``ugence-cloud-scaling-controller``, under
``packages/capabilities/cloud-scaling-controller/src``).

The Cloud Scaling Controller algorithm no longer lives here. Every module was
**moved** (via ``git mv``) into the canonical package. This module makes the legacy
dotted names (``cloud_controller.controller``, ``cloud_controller.core.coherence``,
``cloud_controller.signals.prometheus`` …) resolve to the *same object* in the
canonical package — object identity preserved — so existing
``import cloud_controller...`` / ``from cloud_controller... import ...`` statements
keep working unchanged, with identical behavior, serialization, and errors.

**No scaling algorithm, configuration, or observability implementation lives here.**
This is a thin re-export shim for a documented compatibility period; new code should
import ``ugence_cloud_scaling_controller`` directly (see
``docs/LEGACY_IMPORT_MIGRATION.md``).

Mechanism: a meta-path finder that maps ``cloud_controller.<sub>`` to
``ugence_cloud_scaling_controller.<sub>`` and caches the *same* module object under
the legacy name. This mirrors the ``symbolu`` package's own compatibility finder, so
the chain ``symbolu.cloud_controller.<sub>`` -> ``cloud_controller.<sub>`` ->
``ugence_cloud_scaling_controller.<sub>`` yields one shared object.
"""

from __future__ import annotations

import importlib as _importlib
import sys as _sys

_CANON = "ugence_cloud_scaling_controller"
_LEGACY = "cloud_controller"


def _ensure_canonical_importable() -> None:
    """Source-checkout bootstrap: put the canonical package's ``src`` directory on
    ``sys.path`` only if the canonical package is not already importable. Installed as
    a wheel it is already importable and this is a no-op.
    """
    import importlib.util

    if importlib.util.find_spec(_CANON) is not None:
        return
    import pathlib

    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "packages" / "capabilities" / "cloud-scaling-controller" / "src"
        if (cand / _CANON / "__init__.py").exists():
            if str(cand) not in _sys.path:
                _sys.path.insert(0, str(cand))
            return


_ensure_canonical_importable()


class _CloudControllerFinder:
    """Redirect ``cloud_controller.<sub>`` imports to the canonical package."""

    @classmethod
    def find_spec(cls, fullname, path=None, target=None):
        # Only claim submodules; ``cloud_controller`` itself is this real shim package.
        if fullname.startswith(_LEGACY + "."):
            import importlib.util

            return importlib.util.spec_from_loader(fullname, cls)
        return None

    @classmethod
    def create_module(cls, spec):
        return cls._load(spec.name)

    @classmethod
    def exec_module(cls, module):  # already initialized by _load
        return None

    @classmethod
    def _load(cls, fullname):
        if fullname in _sys.modules:
            return _sys.modules[fullname]
        target = _CANON + fullname[len(_LEGACY):]  # cloud_controller.X -> ugence...X
        real = _importlib.import_module(target)
        _sys.modules[fullname] = real  # identity: same object as canonical
        return real


if not any(f is _CloudControllerFinder for f in _sys.meta_path):
    _sys.meta_path.insert(0, _CloudControllerFinder)

# Curated top-level re-export (identity preserved) — mirror the canonical package's
# small public API so ``from cloud_controller import Controller`` also works.
from ugence_cloud_scaling_controller import (  # noqa: E402,F401
    ActionResult,
    CloudScalingController,
    Controller,
    InfraControllerConfig,
    ScalingObservation,
    ScalingRecommendation,
    __version__,
)

__all__ = [
    "ActionResult",
    "CloudScalingController",
    "Controller",
    "InfraControllerConfig",
    "ScalingObservation",
    "ScalingRecommendation",
    "__version__",
]
