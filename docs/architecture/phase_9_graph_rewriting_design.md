# Phase-9 Graph Rewriting Design Specification

**Document Version:** 1.0
**Document Status:** DESIGN-ONLY (Pre-Implementation)
**Effective Date:** 2025-12-15
**Enforcement:** None (design phase)

---

## Executive Summary

Graph rewriting in this system must operate as a **structural simplification and canonicalization engine**, not a generative or interpretive mechanism. The appropriate model is closer to term-rewriting systems and compiler optimization passes than to any attention-based or probabilistic framework. Rewriting must be **confluence-guaranteed** (all rewrite paths reach the same normal form), **termination-guaranteed** (by construction, not timeout), and **fully reversible** (each step invertible). The core danger is not computational but **ontological**: rewriting that appears structural but secretly introduces semantic judgment. Safety requires treating rewrite rules as mathematical identities, not heuristics.

---

## 1. Conceptual Framing

### 1.1 Compatible Paradigms

**Term-rewriting systems** are the most compatible model. In term-rewriting, transformations are defined by pattern-matching on structure, not by evaluating meaning. A rewrite rule of the form `pattern → replacement` fires when the pattern matches, regardless of what the pattern "represents." This is exactly what Phase-9 needs: structural recognition triggering structural transformation.

**Compiler optimization passes** are also compatible, specifically those that perform:
- Dead code elimination (removing unreachable substructures)
- Common subexpression elimination (identifying structural duplicates)
- Canonicalization (reordering to a normal form)

These are deterministic, reversible (in principle), and operate purely on syntactic structure.

**Category-theoretic morphisms** provide a useful framing for proving properties. If we view the graph as an object in a category, rewrites become morphisms. Properties like confluence and termination can be stated in terms of commuting diagrams. This is not an implementation suggestion—it is a proof framework.

### 1.2 Dangerous Paradigms

**Cellular automata** are partially dangerous. While deterministic, their local-rule / global-emergence pattern can produce behaviors that are computationally irreducible—meaning the only way to know the result is to run the system. This violates auditability. Acceptable only if rules are proven to terminate in bounded steps.

**Constraint satisfaction rewriting** is dangerous if constraints are evaluated by search or optimization. Any form of "find the best solution" introduces implicit scoring, which is a probability analog. Acceptable only if constraints are structural (e.g., "no node may have degree > k") and checked by enumeration, not search.

**Attention mechanisms** and **transformer-like patterns** are categorically forbidden. These compute weighted combinations, which is probability by another name. Even "soft" attention that claims to be deterministic still introduces continuous weighting, which violates the binary-relation invariant.

---

## 2. Rewrite Triggers

Rewrites should fire on **structural recognition**, not evaluation. The following are acceptable triggers:

### 2.1 Pattern Equivalence

Two subgraphs that are structurally isomorphic (same shape, same edge types) can be collapsed to a single representative. The trigger is a successful isomorphism check, which is deterministic.

### 2.2 Redundant Subgraphs

A subgraph that appears multiple times with identical connectivity can be deduplicated. The trigger is detection of identical structure, not "importance."

### 2.3 Boundary Saturation

When a boundary region (as defined by Phase-8 emergence sentinel) has no further growth potential—all adjacent positions are either filled or forbidden—it becomes a candidate for freezing or compression.

### 2.4 Fold Completeness

When Phase-7 folding has marked a region as fully folded (no further folds possible), that region can be treated as a unit for higher-order rewrites.

### 2.5 Deterministic Symmetry

When a subgraph exhibits internal symmetry (automorphism group is non-trivial), it can be rewritten to a canonical orientation. The trigger is detection of the symmetry, not judgment about which orientation is "better."

### 2.6 Forbidden Triggers

| Forbidden Pattern | Reason |
|-------------------|--------|
| "This subgraph is more important than that one" | Introduces implicit scoring |
| "This pattern appears frequently, so prioritize it" | Statistical reasoning |
| "This region is more central to the graph" | Centrality is a continuous measure |
| Any trigger requiring comparison of magnitudes or scores | Violates binary-relation invariant |

---

## 3. Rewrite Types

### 3.1 Collapse

**Definition**: Merge multiple nodes/edges into fewer, preserving connectivity.

| Aspect | Detail |
|--------|--------|
| **Preserves** | Reachability, edge-type composition |
| **Risks** | May accidentally lose structural detail needed downstream. Must be reversible. |

### 3.2 Expansion

**Definition**: Replace a compressed node with its expanded subgraph.

| Aspect | Detail |
|--------|--------|
| **Preserves** | Must be exact inverse of collapse |
| **Risks** | If expansion rules differ from collapse rules, reversibility breaks. Must be defined as a symmetric pair. |

### 3.3 Canonicalization

**Definition**: Reorder nodes/edges to a standard form (e.g., lexicographic by some structural key).

| Aspect | Detail |
|--------|--------|
| **Preserves** | Isomorphism class—the canonical form is unique per equivalence class |
| **Risks** | The ordering criterion must be purely structural. Any ordering based on "meaning" or "importance" violates invariants. |

### 3.4 Normalization

**Definition**: Apply all applicable rules until no more apply (compute normal form).

| Aspect | Detail |
|--------|--------|
| **Preserves** | The normal form is unique if the system is confluent |
| **Risks** | If the system is not confluent, different application orders yield different results. Confluence must be proven, not assumed. |

### 3.5 Partitioning

**Definition**: Divide a graph into non-overlapping regions based on structural criteria.

| Aspect | Detail |
|--------|--------|
| **Preserves** | Total coverage (union of partitions = original graph) |
| **Risks** | Partition boundaries must be deterministic. Any "soft" boundary (e.g., "nodes with high connectivity go here") introduces implicit scoring. |

### 3.6 Reflection

**Definition**: Produce a mirrored or inverted copy of a subgraph.

| Aspect | Detail |
|--------|--------|
| **Preserves** | Shape invariants under the reflection operation |
| **Risks** | Must define what "reflection" means structurally. If edges are directed, reflection must handle direction consistently. |

### 3.7 Quotient

**Definition**: Replace a subgraph with a representative of its equivalence class.

| Aspect | Detail |
|--------|--------|
| **Preserves** | Equivalence class membership |
| **Risks** | The equivalence relation must be decidable and explicit. No "similarity" measures allowed. |

---

## 4. Safety Boundaries

### 4.1 Hard Termination Conditions

Termination must be **guaranteed by construction**, not by counting iterations.

**Approach 1: Strictly Decreasing Measure**

Define a well-founded measure on graphs (e.g., total node count, total edge count, sum of depths). Require that every rewrite rule strictly decreases this measure. Since well-founded orders have no infinite descending chains, termination is guaranteed.

**Approach 2: Stratified Rules**

Assign each rewrite rule to a stratum (level). Rules at stratum N can only fire after all rules at stratum N-1 have reached fixpoint. Each stratum has finitely many applicable rules. Total termination follows.

**Approach 3: Resource Consumption**

Treat rewrites as consuming a finite structural resource (e.g., "collapse tokens"). When the resource is exhausted, no further rewrites of that type can occur. The initial resource is bounded by input size.

### 4.2 Structural Monotonicity

Define properties that must never increase:
- Total number of nodes (for collapsing phases)
- Maximum path length between any two nodes
- Total edge count

Or properties that must never decrease:
- Connectivity (no rewrite may disconnect a connected component)
- Coverage (every original structural unit must remain represented)

### 4.3 Proof-of-No-Mutation

Before any rewrite fires, the system must be able to certify:

1. The input subgraph matches the rule's pattern exactly
2. The output subgraph is constructible from the rule's replacement exactly
3. The rewrite decreases the termination measure
4. The rewrite preserves all stated invariants

This is not a runtime check—it is a property of the rule set itself, proven once at design time.

### 4.4 Infinite Loop Impossibility

| Cause | Prevention |
|-------|------------|
| Non-terminating rule chains (A→B→C→A) | Well-founded termination measure (breaks all chains) |
| Rules that increase what they should decrease | Each rule proven to decrease the measure (breaks increases) |
| Non-confluent rules that fight each other | Confluence proof (breaks fights) |

---

## 5. Determinism & Auditability

### 5.1 Replay

Every rewrite must be specifiable as a tuple: (rule identifier, match location, substitution). Given the same input graph and the same sequence of tuples, the same output graph must result. This is replay.

### 5.2 Reversal

Every rewrite rule must have a declared inverse. Collapse has Expansion. Canonicalization has an identity inverse (canonicalizing an already-canonical form is idempotent). Applying the inverse sequence in reverse order must recover the original graph.

### 5.3 Step-by-Step Audit

The sequence of rewrite tuples constitutes an audit trail. An auditor can:

1. Start from the original graph
2. Apply each rewrite in order
3. Verify the intermediate graph matches expectations
4. Conclude at the final graph

This is not logging—it is the definition of what the system does. The tuple sequence *is* the computation.

### 5.4 Cross-Run Identity

Given identical inputs, the system must produce identical outputs. This requires:

- Deterministic rule selection (no "pick a random applicable rule")
- Deterministic match ordering (if multiple matches, always choose the same one)
- Deterministic substitution (no free variables resolved by choice)

The standard technique is to define a total order on matches (e.g., lexicographic by node ID) and always select the least match.

---

## 6. Creative Improvements (Bounded)

### 6.1 Stratified Quotient Lattice

Build a lattice of equivalence classes, where each level represents a coarser quotient of the graph. Rewrites can move between levels, but only in one direction per phase. This allows controlled abstraction without losing the ability to recover detail.

### 6.2 Symmetry-Preserving Compression

When a subgraph has non-trivial automorphisms, represent it by its orbit structure rather than explicit nodes. This is a form of compression that exploits symmetry. Decompression is deterministic (enumerate the orbit).

### 6.3 Boundary Algebra

Define a formal algebra on boundary regions (as identified by Phase-8). Rewrites can manipulate boundaries using algebraic operations (union, intersection, complement) rather than node-by-node manipulation. This is higher-level but still structural.

### 6.4 Proof-Carrying Rewrites

Each rewrite carries a machine-checkable proof that it preserves stated invariants. The proof is generated at rule-design time and verified at rule-application time. This shifts trust from "the designer was careful" to "the proof checker is correct."

### 6.5 Reversible Encoding

Use a reversible encoding scheme (like those in reversible computing) where the output graph plus a small "history token" can reconstruct the input graph. This makes reversal first-class rather than an afterthought.

### 6.6 Fixed-Point Characterization

Instead of defining rewriting procedurally, characterize the desired normal form as the unique fixed point of a structural equation. Rewriting becomes "find the fixed point" rather than "apply rules until done." Fixed-point existence and uniqueness must be proven.

---

## 7. Red Flags

### 7.1 Transformer-Like Drift

| Warning Sign | Why It's Dangerous |
|--------------|-------------------|
| Any mention of "attention" or "focus" | Implies weighted selection |
| Weighting schemes, even if called "structural weights" | Continuous values violate binary invariant |
| Operations that combine multiple inputs into a weighted sum | This is exactly what transformers do |
| "Soft" matching where partial matches contribute partially | Introduces implicit probability |

### 7.2 Hidden Probabilistic Reasoning

| Warning Sign | Why It's Dangerous |
|--------------|-------------------|
| Scores, rankings, or orderings based on magnitude rather than structure | Magnitude comparison is proto-probabilistic |
| "Likelihood" or "confidence" language | Direct probability vocabulary |
| Any operation whose output depends on frequencies in the input | Statistical reasoning |
| Sampling or randomization, even if seeded | Non-determinism |

### 7.3 Semantic Leakage

| Warning Sign | Why It's Dangerous |
|--------------|-------------------|
| Rules that fire based on what a subgraph "means" | Requires interpretation |
| External dictionaries or knowledge bases | External semantics |
| Natural language in rule definitions | Language carries meaning |
| Appeals to "common sense" or "typical usage" | World knowledge |

### 7.4 Uncontrolled Emergence

| Warning Sign | Why It's Dangerous |
|--------------|-------------------|
| Rules whose composition produces unpredictable global behavior | Violates auditability |
| "Let the system discover" language | Implies emergent semantics |
| Phase transitions or critical phenomena | Non-linear, hard to bound |
| Computationally irreducible dynamics | Cannot predict without running |

### 7.5 Subtle Signs

- Explanations that require understanding intent to follow
- Justifications based on "this usually works well"
- Rules that are hard to invert
- Termination proofs that rely on probabilistic arguments
- Confluence proofs that rely on "in practice" observations

---

## 8. Implementation Decision

The safest posture is to view Phase-9 as **optional**. If the graphs produced by Phase-7 are already in a useful form, rewriting may add complexity without benefit. The burden of proof is on Phase-9 to demonstrate that it provides value while preserving all invariants.

| Criterion | Required Standard |
|-----------|------------------|
| Justification | "This is necessary because X cannot be achieved otherwise" |
| Safety | "Here is the proof of safety" |
| NOT Acceptable | "We could add this" |

---

## Appendix A: System Invariants (Reference)

Phase-9 must preserve all existing pipeline invariants:

| Invariant | Description |
|-----------|-------------|
| `NO_PROBABILITY` | No probabilistic reasoning or statistical measures |
| `NO_LEARNING` | No parameter updates or model training |
| `NO_SEMANTICS` | No meaning interpretation |
| `NO_INTENT` | No intent inference |
| `NO_LANGUAGE` | No natural language processing |
| `NO_GENERATION` | No unconstrained generation (until controlled projection) |
| `DETERMINISTIC` | Same input always produces same output |
| `REVERSIBLE` | All transformations can be undone |
| `FAIL-CLOSED` | Errors result in rejection, not degraded output |

---

## Appendix B: Related Documents

- `docs/architecture/BOUNDARIES.md` — Core/Substrate and Observer Boundary Contract
- `docs/phases/` — Phase-specific documentation
- `docs/specs/` — Formal specifications

---

**END OF DOCUMENT**
