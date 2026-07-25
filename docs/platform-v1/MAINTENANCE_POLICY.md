# Platform v1.0 — Maintenance Policy

## Principle

The platform is frozen. Maintenance keeps it correct and secure **without
architectural drift**. Application work (AI Hiring) proceeds on top of the frozen
public APIs and never edits the frozen trees.

## Workflow

1. Make the change on a branch.
2. Run `python -m platform_freeze.classify_change --base <freeze-commit> --head HEAD`.
3. Act on the proposed class:
   - **PATCH** — merge after normal review + green tests.
   - **MINOR** — requires compatibility review (`COMPATIBILITY_POLICY.md`);
     regenerate the freeze manifest; bump the platform minor.
   - **MAJOR / UNCLASSIFIED** — **blocked**. Requires explicit architectural review
     and, for MAJOR, a platform unfreeze (advance the major, re-baseline).
   - **APPLICATION_LOCAL** — merge under application review; the platform freeze is
     unaffected.
4. Run `python -m platform_freeze.verify` — must PASS.
5. Preserve all baseline tests.

## What must never regress silently

Fail-safe behaviour (F9–F15), provider isolation (F16/F17), deterministic
auditable resolution (F18/F19), dependency direction (F20), execution separation
(F6/F8), and the human/AI authority boundary (F2/F3). The verifier's direct checks
and the referenced authoritative tests guard these.

## Freeze tooling is out-of-band

`platform_freeze/` is repository/release tooling, distributed as
`dgm-platform-freeze-tooling`. It is **not** a runtime dependency and the frozen
platform packages never import it.
