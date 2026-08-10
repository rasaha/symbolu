# Shortcut-path isolation plan

**Working hypothesis:** needle survives through a diffuse, address-independent slot-read pathway.

The Stage-1 frozen ablations already **support** this and **distinguish** it from a window shortcut:
retrieval collapses under slots-off (slots are used) but survives randomized-addressing (correct
addressing is not required). That rules out a pure local-window / token-duplication / position-only
path (those would not collapse under slots-off).

This phase reuses the **frozen** `slots_off` and `randomized_address` ablations (unchanged, not used
as training signals) at checkpoints 300/600/1200, and adds only **non-training** diagnostic ablations,
defined before training and applied identically to all arms, to separate the remaining alternatives:

- local-window-reduction eval (does needle survive with a shrunk window?)
- value-token-dedup eval (does needle survive when duplicate value tokens are removed?)
- positional / address-token controls

**Conservative wording:** the evidence is *consistent with* / *supports* a diffuse
address-independent slot read; it *does not distinguish* every alternative and *remains unresolved*
until the added diagnostics run. No definitive mechanistic-proof language is used. These diagnostics
are **not** optimization targets in this phase, and none is run here (preregistration only).
