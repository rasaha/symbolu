# ACP Compatibility Strategy

Applicable **only if** the project later decides to package ACP (not recommended now). This documents the
compatibility approach so a future migration preserves consumers without duplication.

## Existing import paths to preserve

Real product consumers (`cer_v0_1/2/3`) do **not** import a clean top-level API. They **deep-import**:

- `symbolu_robotics.autonomous_control_plane.cloud.adapter` → `CloudShadowAdapter`
- `…cloud.composition` → `AuthorizationVerdict`, `CombinedOutcome`, `CompositionResult`, `compose`
- `…cloud.outcomes` → `CloudRecommendation`
- `…cloud.envelopes` → `CloudWorldState`, `CloudValidity`, `CloudActionCandidate`
- `robotics_reliability_bench/acp_*` also import the top-level package and `…safety_adapters.*`

They rely on **exact enum identity** (`is` / isinstance) and enum **`.value` string** serialization, and on
the `CloudWorldState`/`CloudActionCandidate` dataclass field schema.

## Required mechanism

| Requirement | Approach |
|---|---|
| Preserve legacy deep-import paths | Logic-free re-export modules at the legacy paths (`…cloud.composition`, etc.) that import from the canonical `ugence_action_clearance…` and re-export the same objects |
| Preserve **object identity** | `sys.modules` aliasing so the canonical module *is* the legacy module (the model-selection / decision-authority pattern), guaranteeing `is`/isinstance and enum identity |
| No duplicated source | The shim contains **no logic**, only imports/`__all__` |
| No silent divergence | No fallback imports that could select a different implementation |

## Techniques to avoid (explicitly)

- **Meta-path import hooks** — brittle, invisible; forbidden.
- **Duplicated source** — two copies of the clearance logic; forbidden.
- **Runtime monkey-patching** — forbidden.
- **Fallback imports** that silently pick a different implementation depending on environment — forbidden.
- **Filesystem walking in installed wheels** — only acceptable for *repository-only* compatibility, never in
  a distributed wheel.

## Object-identity note

`cer_v0_*` compose ActionGate + ACP by comparing `CombinedOutcome` / `AuthorizationVerdict` enum members and
by isinstance-checking `CloudWorldState`. Any migration **must** keep these as the *same* objects (via
`sys.modules` aliasing), not re-declared equivalents, or the composition invariants and conformance tests
break.

## Standalone-distribution boundary

The canonical wheel must build and run in a **clean virtual environment with no monorepo path** (the
model-selection / GPF / decision-authority `verify_*_distribution.py` pattern). The legacy re-export shims are
a **repository-only** compatibility layer; they are **not** shipped in the standalone wheel, and the wheel
must not depend on any monorepo path to resolve them. Consumers that migrate to `ugence_action_clearance`
directly get the clean surface; the shim exists only to avoid breaking in-repo deep imports during the
transition.

## Staged consumer migration

Because there are only 3 product subsystems (13 files), a staged migration is feasible: introduce the
canonical package + shim (identity-preserving), then migrate `cer_v0_1 → v0_2 → v0_3` onto the curated API,
retaining the shim until all deep imports are gone, then deprecate the shim (removal target at a major
version, as decision-authority does).
