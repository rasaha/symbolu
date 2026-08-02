# Overview

Context Minimization reduces an **already-assembled** context by **extractive
omission** while preserving a **caller-defined deterministic equivalence
condition**, failing closed whenever equivalence cannot be established.

## Where it sits

```
        upstream component
   (assembles / admits context)
                │
                ▼
   ┌───────────────────────────┐
   │  ugence-context-minimization │   ← this package (stdlib-only leaf)
   │        core (minimize)      │
   └───────────────────────────┘
                │ asks
                ▼
   neutral invariance-oracle protocol   ← InvarianceOracle (you inject)
                │ implemented by
                ▼
   ActionGate integration adapter        ← lives OUTSIDE this package
```

The core minimizes. The oracle decides equivalence (and, in the ActionGate case,
what authorization outcome the reduced context yields) and returns a deterministic
opaque equivalence key. **The minimizer creates no authority.**

## Responsibilities

**Owns:** immutable context/unit models; context and span identity; structural
deduplication; protected-span masks; extractive keep/drop selection; deterministic
budget policies; the neutral invariance-oracle interface; equivalence-key
comparison; span restoration; full-context fallback; minimization results;
provenance and fingerprints; deterministic reason codes; a package error taxonomy;
audit-friendly keep/drop records.

**Does not own:** context admission; evidence admissibility; enterprise policy;
ActionGate authorization; Action Clearance; Decision Authority; TAP; governance
authority; LLM reasoning; summarization/paraphrasing; retrieval; model routing;
Agent Runtime; provider execution; credentials; external systems; agent planning
or memory.

See `PACKAGE_BOUNDARY.md` for the full boundary, `STRUCTURAL_MINIMIZATION.md` and
`ORACLE_VERIFIED_MINIMIZATION.md` for the two modes, and `LIMITATIONS.md` for what
this release does and does not claim.
