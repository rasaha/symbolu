"""Product composition roots (H6 §7) — dev and demo, deterministic only.

Two named composition roots assemble the *already-shipped* H1–H4 hiring services
and the frozen kernel decision services into a runnable in-memory product. Both
reuse the validated assembly in :mod:`ugence_ai_hiring.validation.composition`; this
module adds **no** new services, states, or authorities — it only names the
supported product configurations and wraps the env in a small facade.

- :func:`build_dev_platform` — developer wiring: your own config/tenant/reviewers.
- :func:`build_demo_platform` — the fixed configuration used by the safe demo.

Both are deterministic-simulation only. The typed config (:mod:`.config`) has
already fail-closed on any production mode before either function runs.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..validation.composition import ValidationEnv, build_validation_env
from ..validation.lifecycle import CaseRun, CaseSpec, run_lifecycle
from .config import ExecutionMode, ProductConfig


@dataclass
class HiringProduct:
    """A runnable, deterministic hiring product bound to one validated config.

    Thin facade over the assembled :class:`ValidationEnv`. It exposes the two
    operations a demo or pilot harness needs — run a governed case end to end,
    and reconstruct the accountable record — without leaking the internal
    service graph.
    """

    config: ProductConfig
    env: ValidationEnv

    def run_case(self, spec: CaseSpec) -> CaseRun:
        """Drive one case through the full governed lifecycle (deterministic)."""
        return run_lifecycle(self.env, spec)

    def reconstruct(self, action_proposal_id: str):
        """Reconstruct the end-to-end accountable chain for an executed action."""
        return self.env.action_reconstruction.reconstruct(
            self.env.ai(), action_proposal_id
        )


def _build(config: ProductConfig) -> HiringProduct:
    # Belt-and-suspenders: the config already fail-closed, but re-assert the mode
    # here so no caller can hand-construct a HiringProduct around a production env.
    if config.execution_mode is not ExecutionMode.DETERMINISTIC_SIMULATION:
        raise ValueError(  # pragma: no cover - unreachable given config validation
            "only DETERMINISTIC_SIMULATION is supported by this package"
        )
    env = build_validation_env(
        tenant=config.tenant,
        max_retries=config.max_retries,
        extra_humans=config.extra_reviewers,
    )
    return HiringProduct(config=config, env=env)


def build_dev_platform(config: ProductConfig | None = None) -> HiringProduct:
    """Compose a development product from a (validated) config, deterministic only."""
    return _build(config or ProductConfig())


#: The single fixed configuration the safe demo runs under.
DEMO_CONFIG = ProductConfig(
    tenant="demo-tenant",
    execution_mode=ExecutionMode.DETERMINISTIC_SIMULATION,
    max_retries=2,
    redact_pii=True,
    extra_reviewers=(),
)


def build_demo_platform() -> HiringProduct:
    """Compose the product under the fixed, safe :data:`DEMO_CONFIG`."""
    return _build(DEMO_CONFIG)
