# Platform v1.0 — Canonical Architecture Invariants (F1–F20)

These twenty invariants are **frozen**. Each is certified by an authoritative test
(no test is duplicated); the freeze verifier additionally runs a fast independent
check for the behaviourally-critical ones. See `platform_freeze/invariants.py` for
the machine-readable register and `python -m platform_freeze.verify` for status.

| ID | Invariant | Certified by |
|---|---|---|
| F1 | DGM owns governance lifecycle records. | enterprise_validation_pilot scenario suite |
| F2 | AI recommendations are advisory and non-binding. | ai_hiring decision-boundary tests |
| F3 | AI is never recorded as human decision authority. | ai_hiring decision-boundary tests |
| F4 | Assertion governance evaluates claims and evidence. | tap_provider conformance |
| F5 | Action governance authorizes proposed actions. | actiongate_provider conformance |
| F6 | Assertion governance does not authorize execution. | tap_provider dependency-boundary tests |
| F7 | Action governance does not determine assertion truth. | actiongate_provider dependency-boundary tests |
| F8 | External execution remains separate from authorization. | pilot scenario suite |
| F9 | DENIED actions never dispatch. | pilot I3 (direct check) |
| F10 | INDETERMINATE authorization never dispatches. | pilot I4 (direct check) |
| F11 | UNSUPPORTED assertions never become supported downstream without new evidence/authority. | benchmark I1 (direct check) |
| F12 | Provider infrastructure failure never produces support or authorization. | tap/actiongate mapping tests (direct check) |
| F13 | Constraints are enforced before dispatch. | pilot Task-107 tests (direct check) |
| F14 | Obligations are verified separately from execution success. | pilot I9 (direct check) |
| F15 | Human approval cannot be fabricated by a provider. | pilot I14 |
| F16 | Providers interact through neutral framework contracts. | */dependency-boundary tests (direct check) |
| F17 | Providers of the same or different families do not invoke one another. | heterogeneity H14–H16 (direct check) |
| F18 | Provider resolution is deterministic and auditable. | heterogeneity H1 (direct check) |
| F19 | Fallback cannot be used for governance shopping. | heterogeneity H5–H8 (direct check) |
| F20 | Frozen package dependency direction remains acyclic. | platform_freeze dependency check (direct check) |

## Change rule

Any change that would alter an invariant's *meaning* is a **MAJOR** change and
requires explicit platform unfreeze (see `VERSIONING_POLICY.md`). Adding a new
invariant or a stronger certifying test is **MINOR**. Correcting a test that
already certifies an invariant is **PATCH**.
