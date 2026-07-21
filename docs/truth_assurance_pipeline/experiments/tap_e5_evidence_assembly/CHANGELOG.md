# TAP-E5 — Changelog

## v5 (Evidence Assembly — initial research & falsification phase)

**Added** a self-contained TAP-E5 track under
`truth_assurance_pipeline/tap_e5_evidence_assembly/`. It imports TAP-E1 (`IntentRecord`),
TAP-E2 (`RetrievalRecord`), TAP-E3 (`RelationshipRecord`), and TAP-E4 (`GovernanceRecord`)
through their **frozen public interfaces** and modifies none of them. No dependency cycles.

- `schema.py` — versioned `EvidencePacket` + `PacketIntent` / `PacketEvidence` /
  `PacketRelationship` / `PacketGovernance` / `PacketConflict` / `PacketGap` /
  `DependencyEdge` (the frozen downstream interface).
- `dependency_graph.py` — adjacency, reachability, orphan detection, cycle detection.
- `assembler.py` — the assembly engine, `AssemblyConfig`, A–F baselines, and the 14-stage
  append-only trace.
- `packet_validator.py` — structural packet validation.
- `validator.py` — upstream-input coherence checks (never repairs).
- `metrics.py` — packet metrics + 12 independent critical-failure classes.
- `harness.py` — E1→E2→E3→E4→E5 driver, dev-only selection, 14 preregistered gates, verdict,
  `frozen_components_hash`.
- `loader.py` — gold-free public loader.
- `corpus/` — NEW independent corpus (32 cases / 13 families; eval content-locked; gold
  computed independently of the assembler).
- `experiments/` — `run_experiment.py`, `preregistration.json`, `results_v5.json`,
  `experiment_lock.json`.
- `tests/test_tap_e5.py` — 19 behavioral tests.

**Result:** selected baseline **F** (the simplest satisfying all preregistered gates —
minimization, provenance, and validation require it); all fourteen gates pass on the locked
eval; verdict **`PASS_WITH_LIMITED_CLAIM`**.

**Findings:** naive union (A) duplicates ids and orphans unused evidence; deduplication (B)
still ships unused evidence and no provenance; a winner-only dependency closure (C) drops
rejected authorities and minority evidence, yielding a packet that is *smaller but
incomplete*; full closure (D) restores completeness but has no provenance index; provenance
(E) still leaves downstream-unused metadata and never validates; only the full pipeline (F)
minimizes, preserves everything required, validates, and freezes with zero severe failures.

**Supported claim (narrow):** TAP-E5 deterministically assembles a minimal,
provenance-preserving, dependency-preserving `EvidencePacket` from frozen upstream TAP
records, preserving all information required for downstream claim validation while
introducing no new reasoning, evidence, governance decisions, or factual assertions. It does
**not** validate claims, determine truth, resolve conflicts, fill gaps, retrieve evidence, or
perform governance reasoning.

**Honesty:** synthetic corpus; authored upstream fixtures (assembly is evaluated, not
extraction); independent gold; locked **development** evaluation inspected during iteration
(see LEAKAGE_AUDIT). Mechanism/construction validation only. TAP-E1/E1.1/E2/E3/E4 are
unchanged (byte-identical; 153 tests pass).

**Freeze:** the `EvidencePacket` public interface is frozen as the downstream contract. Next
layer: **TAP-E6 — Claim Validation**, the first layer that evaluates whether a proposed claim
is actually supported by the assembled packet.
