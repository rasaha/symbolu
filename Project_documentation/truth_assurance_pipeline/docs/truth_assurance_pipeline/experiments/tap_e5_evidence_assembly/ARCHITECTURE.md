# TAP-E5 — Architecture

## 1. Position in the pipeline

```
E1 Intent ─▶ E2 Retrieval ─▶ E3 Relationship ─▶ E4 Governance ─▶ E5 Evidence Assembly ─▶ (E6 Claim Validation)
IntentRecord  RetrievalRecord  RelationshipRecord  GovernanceRecord   EvidencePacket
```

E5 consumes the four upstream records **through their frozen public interfaces only** and
emits exactly one `EvidencePacket`. It imports upstream schemas; it never mutates them and
adds no field to them. There are no dependency cycles: E5 depends on E1–E4, nothing depends
on E5 yet.

## 2. Boundary (what this layer is NOT)

| Concern | Owner | E5 stance |
|---|---|---|
| What did the user ask? | E1 | carries intent id + required metadata |
| Which evidence was retrieved? | E2 | carries required units + provenance; never retrieves |
| What relationship does evidence assert? | E3 | carries supported relationships; never re-extracts |
| Which authority governs? | E4 | carries governance decisions; never re-reasons |
| **Package the minimal complete evidence** | **E5** | **this layer** |
| Is a claim supported? | E6 Claim Validation | out of scope |
| Is the answer faithful? | Response Validation | out of scope |

E5 is a **linker**: it packages what upstream discovered. It performs no retrieval, no LLM
call, no reasoning, no conflict resolution, and no gap filling.

## 3. The EvidencePacket

Immutable, deterministic, provenance-preserving, dependency-preserving, minimal, complete,
and lossless w.r.t. downstream validation. Contents: intent reference; required evidence
units; supported relationships; governance decisions (incl. rejected authorities and
precedence); an explicit dependency graph; every conflict unchanged; every gap unchanged;
carried confidence (never recomputed); and a per-object provenance index. See
[SCHEMA](SCHEMA.md).

## 4. Fourteen-stage deterministic pipeline

Every stage is a pure function of the four records; the engine threads an append-only
`processing_trace`. No randomness, no wall-clock, no network.

1. **validate upstream schemas** — versions + referential consistency; malformed input is
   refused, never repaired (`validator.py`).
2. **import records** — project each record onto packet sub-structures (evidence from E2
   candidates; relationships from E3 assertions; governance from E4 decisions; conflicts from
   E3+E4; gaps from E2+E3+E4).
3. **build dependency graph** — candidate edges: governance → relationship, relationship →
   evidence, governance → intent.
4–6. **collect reachable evidence / relationships / governance** — closure from the
   governance roots, **including rejected authorities, minority evidence, and conflict
   members** (never only the winner).
7–8. **collect conflicts / gaps** — carried unchanged from every origin layer.
9. **deduplicate references** — collapse duplicate object ids and duplicate dependency edges.
10. **dependency-integrity verification** — no dangling edge; acyclic.
11. **provenance verification** — build the provenance index; assert no orphan objects.
12. **packet minimization** — drop transitively-unnecessary evidence and downstream-unused
    metadata; **never** drop supporting/minority evidence, rejected authorities, conflicts,
    gaps, confidence, provenance, or edges.
13. **packet validation** — `packet_validator.py` (see below).
14. **packet freeze** — emit the immutable `EvidencePacket`.

## 5. Minimization contract

Remove only: duplicate references, duplicate dependency paths, transitively-unnecessary
objects (retrieved-but-unreferenced evidence), and metadata unused downstream. Never remove:
supporting evidence, alternative/rejected governing authorities, minority evidence,
conflicts, gaps, confidence, provenance, dependency edges. The packet is the **smallest
packet that preserves downstream semantics**.

## 6. Packet validator

`packet_validator.py` verifies: no dangling references; every relationship grounded in
present evidence; every governance decision supported (or an explicit no-support terminal);
conflicts reference in-packet members; a connected, acyclic dependency graph; no duplicate
object ids; no provenance loss; minimality (no unreferenced evidence, no downstream-unused
raw metadata); and schema round-trip.

## 7. Determinism

Every sort carries a stable id tiebreak; deduplication preserves first-seen order; no output
depends on set/dict iteration order. Verified identical across
`PYTHONHASHSEED ∈ {0,1,7,42,123}`.

## 8. Module map

| Module | Responsibility |
|---|---|
| `schema.py` | `EvidencePacket` + sub-structures; frozen downstream interface |
| `dependency_graph.py` | adjacency, reachability, orphans, cycle detection |
| `assembler.py` | `AssemblyConfig`, A–F baselines, 14-stage engine |
| `packet_validator.py` | structural packet validation |
| `validator.py` | upstream-input coherence (never repairs) |
| `metrics.py` | packet metrics + independent critical failures |
| `harness.py` | E1→E2→E3→E4→E5 driver, dev-only selection, gates, verdict, frozen hash |
| `loader.py` | gold-free public loader |
