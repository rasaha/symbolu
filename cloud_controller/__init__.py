"""COMPATIBILITY-ONLY legacy namespace for the Cloud Scaling Controller.

Advisory canonical package: ``ugence_cloud_scaling_controller`` (distribution
``ugence-cloud-scaling-controller``, under
``packages/capabilities/cloud-scaling-controller/src``).

Monorepo-only operations namespace: ``cloud_scaling_operations`` (execution,
approval, orchestration, live telemetry, live-shadow runners — NOT distributed).

The Cloud Scaling code no longer lives here. This module makes the legacy dotted
names resolve to the *same object* in whichever target now owns them, so existing
``import cloud_controller...`` / ``from cloud_controller... import ...`` statements
keep working unchanged:

  * Advisory submodules (controller, config, core.*, signals.*, shadow readers,
    replay.*, offline observability, recommend.confidence/safety, explain.*) →
    ``ugence_cloud_scaling_controller.<sub>``.
  * Operational submodules (action.*, orchestrator, main, recommend.engine/approval/
    webhook, observability.metrics_server/exporter/otel_exporter, shadow.runner,
    shadow.live_efficiency) → ``cloud_scaling_operations.<sub>``.

The operational legacy imports are **MONOREPO-ONLY**, are **NOT part of the
``ugence-cloud-scaling-controller`` distribution**, and are **NOT a stable
distributed API** (see ``docs/LEGACY_IMPORT_MIGRATION.md``). In a wheel-only install
they do not resolve — only the advisory namespace ships.

**No scaling algorithm, configuration, execution, or observability implementation
lives here.** This is a thin routing shim for a documented compatibility period.
"""

from __future__ import annotations

import importlib as _importlib
import sys as _sys

_CANON = "ugence_cloud_scaling_controller"
_OPS = "ugence_cloud_scaling_operations"
_LEGACY = "cloud_controller"

# Legacy submodule dotted-name prefixes that now live in the OPERATIONS namespace.
# Everything else routes to the advisory canonical package.
_OPS_PREFIXES = (
    "action",
    "orchestrator",
    "main",
    "recommend.engine",
    "recommend.approval",
    "recommend.webhook",
    "observability.metrics_server",
    "observability.exporter",
    "observability.otel_exporter",
    "shadow.runner",
    "shadow.live_efficiency",
)


def _is_ops(sub: str) -> bool:
    return any(sub == p or sub.startswith(p + ".") for p in _OPS_PREFIXES)


def _ensure_importable(dist_name: str, *rel_dir_parts: str) -> None:
    """Source-checkout bootstrap: add a directory to ``sys.path`` if ``dist_name`` is
    not already importable. No-op when installed as a wheel."""
    import importlib.util

    if importlib.util.find_spec(dist_name) is not None:
        return
    import pathlib

    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        cand = parent.joinpath(*rel_dir_parts)
        marker = cand / dist_name / "__init__.py"
        if marker.exists():
            if str(cand) not in _sys.path:
                _sys.path.insert(0, str(cand))
            return


_ensure_importable(_CANON, "packages", "capabilities", "cloud-scaling-controller", "src")
# Operations now live in the independent ugence-cloud-scaling-operations package.
_ensure_importable(_OPS, "packages", "capabilities", "cloud-scaling-operations", "src")


class _CloudControllerFinder:
    """Redirect ``cloud_controller.<sub>`` to advisory or operations targets."""

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
    def exec_module(cls, module):  # already initialized by _load
        return None

    @classmethod
    def _load(cls, fullname):
        if fullname in _sys.modules:
            return _sys.modules[fullname]
        sub = fullname[len(_LEGACY) + 1:]  # e.g. "action.k8s_actuator" or "controller"
        root = _OPS if _is_ops(sub) else _CANON
        real = _importlib.import_module(f"{root}.{sub}")
        _sys.modules[fullname] = real  # identity: same object as the target
        return real


if not any(f is _CloudControllerFinder for f in _sys.meta_path):
    _sys.meta_path.insert(0, _CloudControllerFinder)

# Curated top-level re-export (identity preserved) — mirror the advisory package's
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
