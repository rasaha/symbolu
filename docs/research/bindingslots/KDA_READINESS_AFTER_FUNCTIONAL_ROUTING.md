# KDA readiness after functional-routing Stage-1

## Mechanical inputs

- Primary verdict: **`ROUTING_PURITY_NOT_RESOLVED`**
- Selected candidate: **none**

## Decision

**`KDA_READINESS = KDA_VALIDATION_BLOCKED`.**

No intervention produced causally clean, retained slot routing on the Stage-1 seeds. The
address-specific objectives (O1/O2) improved raw needle formation to 5/5 but the retrieval is
address-independent (survives randomized addressing) and the correct-slot routing decays after
scaffold withdrawal; the gradual handoff (H3) fixed neither purity nor collapse.
`READY_FOR_KDA_VALIDATION` is never emitted, and readiness does not advance to
`KDA_VALIDATION_BLOCKED_PENDING_INDEPENDENT_CONFIRMATION` (which requires a selected candidate).

This result is **not softened**. O1/O2's 5/5 raw formation is **not** success — it is an
address-independent shortcut, the opposite of the phase's goal.

## What is and isn't authorized

- **Not authorized:** any KDA / Phase / MLA / architecture work; promoting or packaging the slot
  system.
- **Authorized:** the next preregistered isolation/retention phase (below), designed — not begun — in
  this PR.

## Exact next phase

Per the preregistered stop condition for `ROUTING_PURITY_NOT_RESOLVED`: **BindingSlots Shortcut-Path
Isolation** — determine whether the surviving retrieval flows through local-window leakage,
value-token duplication, content shortcuts, or (as this phase's ablations already indicate) a
non-address-specific diffuse slot-read pathway. The Stage-1 ablations already point strongly to the
**diffuse slot-read** pathway (collapses under slots-off, survives randomized-addressing), so the
isolation phase should confirm that and then test the **deferred retention/consolidation levers**
(standing residual address term O1R, functional teacher H2, routing-parameter consolidation H1, and
their combination C1) that target *persistence of address-dependence through withdrawal* — the crux
this screen localized. None of these is started here.

See `NEXT_CONFIRMATION_PROTOCOL.md`.
