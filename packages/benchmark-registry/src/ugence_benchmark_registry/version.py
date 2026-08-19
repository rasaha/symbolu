"""The distribution version of ``ugence-benchmark-registry``.

Kept in its own module — the convention used by ``ugence-agent-runtime``,
``governed-value``, ``ugence-actiongate-provider``, ``ugence-tap-provider`` and
the integration packages — so ``pyproject.toml``'s dynamic ``version`` attribute
and ``public_api.json`` read one literal.

``0.1.0`` is BR-1's first version: the structural Benchmark Registry contract
layer of ADR §30. There is no registry, no resolver and no service at this
version; BR-2 is a separate, separately-reviewed milestone.

No ``CONTRACT_VERSION`` constant is minted. That is the *provider* convention in
this repository (``ugence-tap-provider``, ``ugence-actiongate-provider``, the
provider framework); the contract-shape packages —
``ugence-governance-contracts``, ``ugence-uvi-policy-contracts``,
``ugence-policy-authority``, ``ugence-trusted-evidence-authority`` — carry only
``__version__``. The versioning that is load-bearing here is the
canonicalization rule-set version bound into every digest
(:data:`~ugence_benchmark_registry.contracts.canonical.BENCHMARK_REGISTRY_CANONICALIZATION_VERSION`).
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
