# Prerequisite gate — functional-routing development

**Verdict: `BINDINGSLOTS_FUNCTIONAL_ROUTING_PREREQUISITE_VERIFIED`.** Machine-readable:
[`PREREQUISITE_GATE.json`](./PREREQUISITE_GATE.json).

## Live state

- Default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` @ `e496a679`.
- Working branch `claude/bindingslots-confirmatory-replication-d117c1` (env git discipline binds this
  session to the designated branch; this phase lives in its own directory).
- Working tree clean at audit; no existing functional-routing branch/PR.

## Prerequisites

- PR #1300 merged (`5f0cbe45`); PR #1319 merged (`ba665e42`). **R0 = frozen CR1 is fully recovered
  from merged PR #1319.**
- PR #1324 (confirmatory) is **open for review, not merged**. Its verdict is reconstructed from its
  committed curated evidence on this branch: `CONFIRMATORY_REPLICATION_FAILED`,
  `SLOT_FORMATION_NOT_REPLICATED`, `KDA_VALIDATION_BLOCKED`; CR1 3/5, B0 0/5, A+ 0/5; seeds 13/14
  formed-then-collapsed; seed 16 randomized-address impurity; seeds 15/17 clean-retained.

The ChatGPT prompt's literal prerequisite ("PR #1324 merged") does not hold — #1324 is intentionally
unmerged. This does not block development: R0 comes from the merged #1319 and the motivation is
reconstructible from committed evidence. Recorded transparently rather than forcing a merge.

## Integrity

- Frozen `abc.json` `b31989a3…` unchanged; architecture signature `6e8672bd…`.
- Functional-routing pre-registration integrity **23/0**; known-signature reproduction **5/0**;
  lab verifier 81/0; historical-artifact protection 8/0.
- No Phase/KDA/MLA in the frozen implementation.

## Conservative-language check

The committed trajectories show a strong scaffold-era routing state existed; they do **not** establish
the precise cause of later collapse — that is the hypothesis this phase tests.

## Seeds

Used 0–17; Stage-1 **18–22**; Stage-2 reserve 23–27; confirmation reserve 28–32. Seeds 18–32 appear
nowhere as a BindingSlots training seed.
