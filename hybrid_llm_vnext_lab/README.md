# Hybrid LLM vNext Lab — Bounded Binding-Slot Incubation

**Status markers (authoritative):**

```
EXPERIMENTAL
NOT_AN_INSTALLABLE_PACKAGE
NOT_A_PRODUCTION_MODEL
NOT_READY_FOR_PACKAGING
```

This root is an **incubation and reproduction laboratory**, created after the Hybrid LLM
algorithm audit (PR #1294, merged) and its binding-slot evidence reconciliation. Its single
purpose in this phase is to **isolate and reproduce the internally-supported bounded
binding-slot subsystem** — the one component that carried the only demonstrated long-range
retrieval improvement in the internal matched experiments — in a clean root with full
provenance, isolated tests, and a faithful reproduction harness.

## What this lab is NOT
- **Not** an installable package. There is no `pyproject.toml`, no wheel build, no
  distribution metadata, no console entry points, no consumer migration shims. Do not add them.
- **Not** the KDA / KDA-MLA architecture. That backbone is a **separate, later** phase and is
  deliberately **not implemented here** (so extraction defects never mix with new-architecture
  defects).
- **Not** Phase. No `PhaseAttentionLayer` / `HybridPhaseTransformer` / `BindingCachePhaseState` /
  `BindingCacheTransformer` / `symbolu.phase_transformer` code or import appears anywhere in
  `src/`. Phase appears only in provenance and historical-comparison text. A boundary test
  enforces this.
- **Not** a validated production capability. See `STATUS.md` for the exact slot maturity.

## What it contains
- `provenance/` — where every incubated component came from (path, commit, git blob hash),
  and the slot-implementation selection with rationale.
- `src/binding_slots/` — the selected working slot code (byte-identical copies) plus a
  dependency-free **stdlib reference** (`slot_reference.py`) that mirrors the discrete slot
  mechanics and is runnable without PyTorch.
- `src/local_baseline/` — a minimal local/window baseline reference used to exercise slots.
- `src/contracts/` — neutral `Protocol` interfaces so slots can later attach to a local, a
  KDA, a KDA-MLA, or a conventional-attention backbone without depending on any of them.
- `src/instrumentation/` — runtime hooks (bounded-state, no-N×N declarative audit,
  utilization, collisions, source/version retention).
- `tests/` — unit / complexity / behavioral / determinism / boundaries. The stdlib-reference
  tests **run here now**; the PyTorch parity/training tests are marked `RESOURCE_BLOCKED`
  (no torch/numpy in this environment) with exact runnable commands.
- `experiments/reproduce_legacy_slots/` — faithful reproduction of the phase_lc A/B/C
  positive slot result (torch; `RESOURCE_BLOCKED` here) with exact original parameters.
- `experiments/multis_seed_slots/` — the ≥5-seed pre-registration that references the merged
  audit acceptance thresholds; runs only **after** reproduction parity passes.

## Environment reality (recorded honestly)
`torch` and `numpy` are **not installed** in the current execution environment. Therefore all
neural training / gradient / tensor-shape execution is classified `RESOURCE_BLOCKED`, with
exact runnable commands and an environment manifest provided. What **does** run here: the
stdlib slot reference and its deterministic algorithmic probes, the declarative no-N×N /
bounded-state audit, the no-Phase import boundary check, provenance/hash validation, and the
merged audit-integrity verifier.

See `STATUS.md` for the current maturity and the gate that must be cleared before anything
moves toward `packages/`.
