"""Isolated compromised-agent experiment for the Action Gateway architecture.

Four enforced protection domains (agent / gateway / broker / Kubernetes) using
Linux network namespaces + separate Unix users + mTLS + Ed25519 asymmetric
authorization + a durable SQLite replay store + optimistic-concurrency writes + a
separately-keyed audit ledger. Determines mechanically whether a fully compromised
agent can cause any unauthorized protected-state mutation.

Reuses action_gate_ref / action_gateway / action_gateway_mcp / action_gateway_k8s.
No AI/BCVF/USE/SCC. See README / THREAT_MODEL / RED_TEAM_RESULTS.
"""

from __future__ import annotations

__version__ = "0.1.0-iso"

from . import crypto, layout  # noqa: F401
