# COMPETING_OPERATIVE_ARCHITECTURE — Competing Operative Resolution Experiment v0.1

## Pipeline
```
frozen proposal generation (v0.1)
        ↓
frozen Proposal Validation Layer (v0.2)
        ↓
frozen governing-set computation
        ↓
frozen G3 operative-source selection (Governance Semantics v0.1)
        ↓
Experimental Competing Operative Resolution Layer   ← the only new component
        ↓
governance decision OR precise governance abstention
        ↓
frozen packet interface (via the documented v0.4 adapter)
```

## Ownership
| stage | implementation | owner |
|---|---|---|
| proposal / validation / graph | v0.1 + v0.2 (unchanged) | frozen |
| governing set | frozen governance (unchanged) | frozen |
| operative-source selection | v0.4 G3 (unchanged) | frozen (this experiment) |
| competing-operative resolution | `competing_operative.py` (new) | **experimental** |
| packet realization | `GraphTraversalResolver._derive` via v0.4 adapter (unchanged) | frozen |

## How the boundary is enforced structurally
- `resolve_relationships` and `resolve_governance` delegate to the v0.4 G3 resolver →
  discovery, classification, validation, governing set, and Mode G are bit-identical.
- `_derive` delegates to the frozen packet builder → Mode P bit-identical.
- The layer runs only in the full `resolve()` pipeline, AFTER G3 has chosen the operative
  source. It can only ADD a precise governance-stage abstention; when it does not abstain,
  the G3 decision passes through unchanged. With C0 it is bypassed entirely (== G3).

## What the layer receives and returns
Input: the validated graph, the frozen governing set, the G3-selected operative node, and
the v0.2 confidence vector. Output: an explicit `OperativeSet` (typed candidates, scope,
competitions with per-predicate results and a category, and — only for a genuine
unresolved conflict — an abstention with a reason code and detail).

## Adapter (unchanged from v0.4)
When the layer answers, the v0.4 adapter translates the G3 operative choice into the
frozen single-primary packet contract (operative first; competing authority edges hidden
from the packet-input graph). When the layer abstains, a `GovernanceResolution(abstain=
True, reason=<code>)` is returned and the frozen packet yields `unknown`. The packet is
never modified; cardinality limits are reported, not worked around silently.
