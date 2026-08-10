# TAP — Repair Model v0.1

Defines repair mechanisms. **Repairs must be localized** to the layer that owns the
defect. Architecture-only.

> Boundary: `12_RESEARCH_BOUNDARIES.md`.

---

## 1. Principle

A defect detected at any layer is repaired **within that layer's responsibility**, or
escalated — never patched by a downstream layer reaching back into an upstream one.
Repairs are recorded in `provenance.repair_history` (append-only, `04_…`); a repair is
a new provenance entry, not an edit.

## 2. Localized repair per layer

| Layer | Repair (localized) | Not allowed |
|---|---|---|
| **Layer 1 relationship** | re-examine evidence for a rejected/uncertain relationship; adjust direction/scope on new spans | inventing a relationship with no span support |
| **Layer 2 governance** | re-resolve operative source / exception with additional governance metadata | creating or deleting a relationship (Layer 1 owns those) |
| **Layer 3 packet** | add a missing material span; trim a non-minimal one | generating natural language |
| **Layer 4 claim** | narrow a `PARTIALLY_SUPPORTED` claim to its supported scope; re-cite; drop an unsupported claim | fabricating support; overriding a deterministic contradiction |
| **Layer 5 response** | add a missing citation/qualification; remove an unsupported addition; de-generalize | asserting a claim Layer 4 did not validate |

## 3. Repair vs abstention

- **Repair** is attempted when the defect is *correctable within the layer* (e.g. a
  claim can be narrowed to its supported scope).
- **Abstention** (`09_…`) is the outcome when repair cannot make the item truthful
  (e.g. contradicted evidence, or irreducibly missing evidence).
- Repair is bounded: a fixed maximum number of localized repair attempts, then
  abstain/escalate. Unbounded repair loops are forbidden.

## 4. Repair provenance

Each repair appends: `{ layer, defect, action, evidence_refs, before_status,
after_status }`. The end-to-end trail therefore shows not just the final decision but
how it was reached — necessary for falsifiability and for attributing residual errors.

## 5. Reference instantiation

The synthetic Layer-4 prototype implements the *narrow* action (`PARTIALLY_SUPPORTED`
→ retain narrowed) and the *abstain*/*remove* actions, which are the Layer-4 repair
outcomes. A general cross-layer repair loop is future work (`11_…`). No repair
mechanism for Layers 1/2/3/5 exists in this repository yet.
