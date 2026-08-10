# GOVERNANCE_SEMANTICS_ARCHITECTURE — Governance Semantics Experiment v0.1

## Pipeline
```
frozen proposal generation (v0.1)
        ↓
frozen Proposal Validation Layer (v0.2)
        ↓
validated relationship graph
        ↓
Experimental Governance Semantics Layer   ← the only new component
        ↓
adapter (documented, lossy)
        ↓
frozen packet-realization interface
```

## Component ownership
| stage | implementation | owner |
|---|---|---|
| proposal generation | v0.1 (unchanged) | frozen |
| proposal validation | v0.2 (unchanged) | frozen |
| relationship graph | v0.2 output (unchanged) | frozen |
| governance semantics | `governance_semantics.py` (new) | **experimental** |
| adapter | `governance_semantics.adapt` (new) | **experimental** |
| packet realization | `GraphTraversalResolver._derive` (unchanged) | frozen |

## How the boundary is enforced structurally
- `resolve_relationships` delegates to v0.2 verbatim → discovery + classification are
  bit-identical (the layer never sees or edits the discovery graph's membership).
- `_derive` delegates to the frozen packet builder verbatim → packet Mode P is
  bit-identical (the harness injects gold governance and calls `_derive`).
- The layer reports the **frozen governing set** (frozen governance is reused to compute
  it) → governance Mode G is bit-identical to the G0 control.
- The only behavioral change is (a) which governing node is OPERATIVE (what the packet
  reads) and (b) governance-stage abstention. Both affect only the full pipeline's
  answer, i.e. selective accuracy / coverage.

## The adapter (precise contract)
Input: the validated graph + the layer's `GovernanceResult`.
Output: `(gov_graph, GovernanceResolution)` in the exact shape the frozen `_derive`
expects.

It performs exactly two translations and nothing else:
1. **Operative ordering** — the operative node is placed first in the governing list and
   first in the graph node order, so the frozen packet's `primary` rule (first governing
   node that sources a governance edge, else first governing node) selects it.
2. **Competing-authority suppression** — governance-source edges (`supersedes`/
   `overrides`/`governs_over`) whose source is a *different* governing node are withheld
   from the packet-input graph, so the frozen `srcs` set is ⊆ {operative}. This realizes
   "operative ≠ authority" within a contract that only accepts one primary node.

The adapter does **not**: infer relationships, modify evidence, introduce answer text,
add policy rules, or independently select the final answer (the frozen packet still
derives tfc/notice/penalty from the operative node's own attributes).

### Documented information loss
The frozen packet contract accepts a single primary node and derives one answer. It
cannot represent (i) "the authority-establishing node differs from the answer-bearing
node" except by the suppression trick above, or (ii) multiple simultaneous cumulative
operatives beyond the penalty channel the frozen packet already supports. Where the
layer's semantics cannot be represented safely, it abstains at the governance stage
rather than emit a lossy answer (see GOVERNANCE_ABSTENTION_SPEC.md).
