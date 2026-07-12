"""Action Gate reference conformance harness (Stage 1).

Deterministic, dependency-light (Python stdlib only) reference implementation of
the frozen contracts:
  * ACTION_GATE_SPECIFICATION.md
  * ACTION_CANONICALIZATION_AND_HASHING_SPEC.md
  * AGENT_ACTION_ADMISSIBILITY_MVP.md

Reference-only: no network services, no MCP server, no AI, no BCVF/USE/SCC, no
production credential broker, no production key custody. See README.md.
"""

from __future__ import annotations

__version__ = "0.1.0-ref"

from . import (  # noqa: F401
    approval,
    audit,
    canon_profile,
    errors,
    evidence,
    gate,
    hashing,
    jcs,
    policy,
    projection,
    schema,
    signing,
    token,
)
