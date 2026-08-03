"""Ugence Policy Workflow Compiler.

A deterministic tooling product that compiles a reviewed, structured governance
policy pack into a governed-workflow IR plus an assurance package — wired across
existing Ugence capability public contracts, gated on human approval, and
content-addressed. It is tooling, not a governance authority: it makes no binding
decision, approves nothing, authorizes no action, and runs nothing.

The single supported import surface is :mod:`ugence_policy_workflow_compiler.api`.
"""

from __future__ import annotations

from .version import (
    CANONICAL_NAMESPACE,
    DISTRIBUTION_NAME,
    DISTRIBUTION_VERSION,
    PRODUCT_NAME,
    PRODUCT_VERSION,
    VersionInfo,
    version_info,
)

__version__ = DISTRIBUTION_VERSION

__all__ = [
    "__version__",
    "DISTRIBUTION_NAME",
    "DISTRIBUTION_VERSION",
    "PRODUCT_NAME",
    "PRODUCT_VERSION",
    "CANONICAL_NAMESPACE",
    "VersionInfo",
    "version_info",
]
