# Amendment — the wave 3 "enterprise integration hub" row is closed as mis-scoped

**Status:** ratified 2026-09-05 by the repository owner. Amends the disposition of
one row in `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md` (`:59`). It
amends no package ADR, port, test or manifest, and creates no package.

## The ruling

**The row is closed. The work it named is a cloud-scaling ladder phase.**

The v1 gap behind "enterprise integration hub" is a **Kubernetes `ScalingBackend`
implementation** behind a seam that already exists and already has an owner
(`packages/capabilities/cloud-scaling-operations`). It is sequenced by the ladder,
not by wave 3, and it needs no new package.

## Why the row was mis-scoped

| Finding | Where |
|---|---|
| The row was already ratified as **folded into an existing milestone**, not a new package `[V]` | `ADR_UGENCE_GOVERNANCE_GAP_SEQUENCING_RATIFICATION.md:23`, `:59` |
| Roadmap §3 defines the "connector framework" as two things — runtime adapters **and** execution-target adapters `[V]` | `Project_documentation/repository/ugence_platform/UGENCE_PRODUCTIZATION_ROADMAP.md:87` |
| §4 puts **one governed execution-target connector (Kubernetes)** in v1, deferring only *additional systems-of-record* connectors and multi-cloud targets beyond Kubernetes `[V]` | ibid. `:95`, `:98`, `:100` |
| The production mutation path is complete **up to an injected seam**: "Backends are injected (duck-typed); deterministic fakes drive SIMULATION and tests" `[V]` | `packages/capabilities/cloud-scaling-operations/src/ugence_cloud_scaling_operations/executors.py:1-8` |
| Repo-wide there are exactly **two** backend classes: the `ScalingBackend` Protocol and `FakeScalingBackend`. **No real backend exists anywhere** `[V]` | ibid. `:39`, `:50` |
| So `cloud-scaling-bounded-execution` is truthful in calling itself "the only path from a credential grant to the executor" — that path currently terminates in a fake `[V]` | `packages/integration/cloud-scaling-bounded-execution/README.md:7-11` |
| One real inbound client ships: a Prometheus HTTP poller `[V]` | `packages/capabilities/cloud-scaling-controller/src/ugence_cloud_scaling_controller/signals/prometheus.py:1-8` |
| One inbound payload path ships, with **no outbound call in it**: GitHub webhook verification and normalization `[V]` | `products/code-governance/src/ugence_code_governance/github/` |
| In `packages/`, `kubernetes` appears almost only inside boundary tests that **forbid** importing it — 21 such files, every one of them listing it as prohibited `[V]` | `grep -rl -i kubernetes --include=test_import_boundary.py --include=test_boundaries.py packages/` |

A hub package would insert a layer between an executor and its injected backend
for no governance reason, and would take a noun every package that mentions
connectors already disclaims — which the sequencing ADR's one prohibition
(`:85-86`) exists to prevent.

## What this changes, and what it does not

Closing the row **removes nothing and unblocks nothing**. The Kubernetes backend
remains unwritten; it simply belongs to the ladder's sequence, alongside 5C, 5D and
5X, rather than to a wave 3 row. Wave 3 is now complete: G4's contracts, the
incident-response package, and the control-plane root, all merged.

## Still open

**`[R]` Do the Prometheus poller and the GitHub webhook receiver satisfy §4's "two
runtime connectors"?** Not ruled on here. If they do, v1's runtime-connector line
is already met and only the execution-target adapter is outstanding.

**`[G]` Nothing in this repository defines "runtime connector" or "execution-target
adapter" beyond the single §3 line.** The terms carry v1 scope but no definition,
so the question above cannot be settled from the repository alone — which is the
reason it is recorded rather than answered.
