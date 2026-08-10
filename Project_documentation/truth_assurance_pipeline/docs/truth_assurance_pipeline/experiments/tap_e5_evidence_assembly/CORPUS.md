# TAP-E5 — Corpus

New, independently authored packet corpus: **32 cases / 13 families**, split **dev 16 /
eval 16**. Not reused from any prior layer.

## Construction

Each case is authored as a small governance scenario (evidence units, relationships,
governance decisions, conflicts, gaps) and **compiled into the four frozen upstream records**
via their public schemas:

- a TAP-E2 `RetrievalRecord` — one `EvidenceUnit` + `EvidenceProvenance` + `RankedCandidate`
  per authored evidence, plus E2-origin `RetrievalGap`s;
- a TAP-E3 `RelationshipRecord` — one `RelationshipAssertion` per authored relationship
  (with `SourceProvenance` to its evidence), plus E3 `RelationshipConflict`s / gaps;
- a TAP-E4 `GovernanceRecord` — one `GoverningDecision` per authored decision (with
  `RejectedAuthority`s and `GovProvenance`), plus E4 `GovernanceConflict`s / gaps;
- the `IntentRecord` is produced by the frozen TAP-E1 layer from the case request text.

E5 then assembles these into an `EvidencePacket`.

## Independent gold

For every case the **minimal-complete gold** is computed by `Case.gold()` from the authored
spec, on a **separate code path** from the assembler: required relationships = winner
supporting ∪ rejected-authority relationships ∪ conflict-member relationships; required
evidence = the evidence of those relationships; required governance/conflicts/gaps = all;
removable evidence = retrieved-but-unreferenced units. If the assembler (baseline F) had a
bug, its output would diverge from this independently-authored gold.

## Families (13)

| Family | Exercises |
|---|---|
| single / multiple | basic 1- and n-evidence packets |
| shared_evidence | one unit supporting two relationships (dedup to a single object) |
| unused_evidence | retrieved-but-unreferenced units (pruning / orphan detection) |
| rejected_authority | minority evidence behind rejected authorities (must be kept) |
| multi_governing | two independent governing decisions |
| e3_conflict | value conflict between two relationships (carried, not resolved) |
| e4_conflict | tied governance authorities → `CONFLICTED` (carried, not resolved) |
| multi_gap | gaps from E2, E3, and E4 preserved together |
| nested | governance → relationship → evidence chains with an exception branch |
| independent_trees | two disjoint dependency trees in one packet |
| deep_provenance | mixed regulatory/policy source chains |
| minimal_edge | already-minimal packets (assembly is a near-no-op) |

The corpus deliberately contains the shapes that expose each rung of the A–F ladder: shared/
duplicate references (so deduplication matters), retrieved-but-unused evidence (so pruning
and orphan detection matter), and rejected authorities + conflict members (so a winner-only
closure is provably *incomplete*, not merely smaller).

## Splits and locking

`dev` is used for configuration selection; `eval` is a **content-hash locked development
evaluation** (`eval_inputs_hash = 04b87570…`, `n_eval = 16`) — inspected during iterative
engineering, **not an untouched/blind holdout** (see [LEAKAGE_AUDIT](LEAKAGE_AUDIT.md)). The
public `loader.py` exposes only case shape counts + compiled inputs, never the gold.
