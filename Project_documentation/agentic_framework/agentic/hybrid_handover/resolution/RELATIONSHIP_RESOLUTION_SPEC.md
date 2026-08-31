# RELATIONSHIP_RESOLUTION_SPEC — SEEB Resolution Layer

**Phase:** second research layer. SEEB v1.0.0, its validators, metrics, routing,
reports, the baseline extractors, and the Hybrid Handover protocol are all frozen
and unmodified. This layer is additive infrastructure and reads them only.

All corpora are synthetic.

## Purpose
The oracle experiment proved retrieval is saturated on SEEB v1: maximal evidence
retrieval solves none of the seven remaining cases; the failures occur *after*
retrieval. This layer measures **relationship reasoning independently of
retrieval**: given identical evidence, which strategies correctly determine the
governing evidence?

## The four separated responsibilities
```
1. Evidence Extraction     → evidence spans            (upstream: SEEB / baselines)
2. Relationship Resolution → typed graph over spans    (THIS layer, stage 2)
3. Governance Resolution   → which nodes govern / abstain (stage 3)
4. Packet Construction     → final answer/packet        (stage 4)
```
Keeping these independent lets any failure be attributed to exactly one stage
(FAILURE_ATTRIBUTION.md).

## Stage 2 — Relationship Resolution
Input: `list[EvidenceSpan]` + question. Output: `ResolvedEvidenceGraph` (typed
nodes + typed edges). Interface: `RelationshipResolverProtocol.resolve_relationships`.

Node types: `Clause, Definition, Exception, Policy, Table, Version, Document,
Section`. Edge types: `defines, references, overrides, supersedes, governs_over,
exception_to, conflicts_with, same_as, effective_after, effective_before, amends,
contains`. Format: RESOLUTION_GRAPH_FORMAT.md.

## Evidence modes (identical evidence across resolvers)
- **Mode A — Oracle**: every sentence (retrieval upper bound).
- **Mode B — BM25**: current strongest conventional retrieval.
- **Mode C — Candidate**: interface only; any `ExtractorProtocol` supplies evidence.

On SEEB v1's short corpora Mode A and Mode B produce identical resolver outcomes
(retrieval is saturated), so relationship reasoning is cleanly isolated.

## Ground truth
Authored in `gold.py` (not in SEEB): per case, the typed relationship graph, the
governing evidence, the correct abstention, and capability tags. Resolvers are
scored against this gold; SEEB's own ground truth is untouched.

## What this layer measures vs does not
- Measures: relationship-edge quality, governance/outcome accuracy per capability,
  single-stage failure attribution (RESOLVER_METRICS.md).
- Does NOT redefine SEEB pipeline metrics; it reports them unchanged via the frozen
  aggregator (pipeline_bridge.py), read as *relative resolver deltas*.

## How future resolvers are compared
A HybridPhaseTransformer or SymbolU resolver implements the same two protocols
and is measured under identical evidence modes, gold, and metrics — see
RESOLVER_BASELINES.md "How future resolvers plug in".
