"""
Boundary Tests: Core/Observer boundary enforcement tests.

This package contains tests that enforce the boundary between:
- Authoritative modules (PO1-P9, policy): Make binding decisions
- Observer modules (P22, P23, P24): Compute diagnostics only

Invariants enforced:
- INV-B1: No imports from observer modules inside authoritative module roots
- INV-B2: Observer outputs only written to allowed sinks
- INV-B3: Identical authoritative inputs yield identical decision surface outputs
- INV-B4: Boundary scanner integrated with CI (fails on violations)
"""
