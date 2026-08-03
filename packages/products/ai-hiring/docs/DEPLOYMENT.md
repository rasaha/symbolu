# Deployment

## Controlled pilot only

The release classification for this distribution is
`PACKAGE_READY_FOR_CONTROLLED_PILOT`. The package is intended for controlled,
supervised pilot evaluation. `production_certified` is always `False`.

This document does not describe a production deployment, because the package does
not ship production capabilities.

## What ships

- Deterministic, offline, in-memory adapters **only**.
- A pure-Python wheel (`ugence_ai_hiring-0.1.0-py3-none-any.whl`) that is
  bit-for-bit reproducible.

## What does NOT ship

No production adapters are included in the distribution:

- No production HRIS or ATS adapters.
- No offer, payroll, or candidate-contact adapters.
- No database driver, no web framework in the core.

Because only in-memory adapters ship, no downstream enterprise action is executed
and no production system is contacted.

## Determinism

Runs are deterministic: the same inputs produce the same outputs, with no
network access and no external model inference. This supports reproducible pilot
evaluation and auditing.

## Governance posture during a pilot

Even in a controlled pilot, the governance boundaries hold: recommendations are
advisory, binding decisions require an authorized human actor, records stay
separate, and the package prepares/records authorizations without executing
downstream enterprise actions. See [GOVERNANCE_BOUNDARIES.md](GOVERNANCE_BOUNDARIES.md).

## Pre-deployment checks

```bash
python -m ugence_ai_hiring version   # confirm distribution + product metadata
python -m ugence_ai_hiring verify    # assert safety/governance invariants
python -m ugence_ai_hiring demo      # observe the governed flow offline
```

For build and reproducibility details, see [PACKAGING.md](PACKAGING.md). For
what the package intentionally does not do, see
[KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).
