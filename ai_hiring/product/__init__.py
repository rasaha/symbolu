"""AI Hiring — curated product surface (H6 §5).

This is the **stable, supported public API** of the AI Hiring product: the small
set of names an integrator or demo harness should import. Everything reachable
here is a re-export of already-shipped, frozen-API-consuming code — this package
introduces **no** new governance, decision, authorization, or execution
semantics. It only packages the completed H0–H5 implementation into a coherent,
demonstrable product.

Stability: **pre-1.0** (see :data:`PRODUCT_VERSION` / :func:`version_info`). The
API is stable enough to pilot; the ``0.`` prefix reserves the right to change it
before 1.0, and nothing here is certified for production hiring decisions.

Public names (and only these constitute the supported surface):

Composition & runtime
    - :class:`HiringProduct`, :func:`build_dev_platform`, :func:`build_demo_platform`

Configuration (fail-closed)
    - :class:`ProductConfig`, :func:`load_config`, :class:`ExecutionMode`
    - :class:`ProductConfigError` and its subclasses

Demo
    - :func:`run_demo`, :class:`DemoResult`, :func:`canonical_cohort`

Accountability
    - :func:`build_accountability_report`, :class:`AccountabilityReport`

Version
    - :data:`PRODUCT_VERSION`, :data:`PLATFORM_BASELINE`, :func:`version_info`

The case-shaping type :class:`~ai_hiring.validation.lifecycle.CaseSpec` is
re-exported for convenience so callers can drive :meth:`HiringProduct.run_case`
without importing from the validation package.
"""

from __future__ import annotations

from ..validation.lifecycle import CaseRun, CaseSpec
from .accountability import AccountabilityReport, build_accountability_report
from .composition import (
    DEMO_CONFIG,
    HiringProduct,
    build_demo_platform,
    build_dev_platform,
)
from .config import (
    ExecutionMode,
    InvalidConfigValueError,
    ProductConfig,
    ProductConfigError,
    UnknownConfigKeyError,
    UnsupportedExecutionModeError,
    load_config,
)
from .demo import DemoResult, canonical_cohort, run_demo
from .version import (
    PLATFORM_BASELINE,
    PRODUCT_VERSION,
    STABILITY,
    VersionInfo,
    version_info,
)

__all__ = [
    # composition & runtime
    "HiringProduct",
    "build_dev_platform",
    "build_demo_platform",
    "DEMO_CONFIG",
    # config
    "ProductConfig",
    "load_config",
    "ExecutionMode",
    "ProductConfigError",
    "UnknownConfigKeyError",
    "InvalidConfigValueError",
    "UnsupportedExecutionModeError",
    # demo
    "run_demo",
    "DemoResult",
    "canonical_cohort",
    # case shaping
    "CaseSpec",
    "CaseRun",
    # accountability
    "build_accountability_report",
    "AccountabilityReport",
    # version
    "PRODUCT_VERSION",
    "PLATFORM_BASELINE",
    "STABILITY",
    "VersionInfo",
    "version_info",
]
