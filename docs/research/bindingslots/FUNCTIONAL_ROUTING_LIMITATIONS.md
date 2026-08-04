# Functional-routing — limitations

## Supported claim

Under the frozen synthetic retrieval protocol, on five fresh seeds (18–22): the address-specific
scaffold objectives (O1 correct-slot probability, O2 read-logit margin) and the gradual curriculum
handoff (H3) **did not** produce causally clean, retained slot routing. O1/O2 increased raw needle
formation to 5/5 but via an address-independent pathway (survives randomized addressing), and the
correct-slot routing they build during the scaffold **decays after withdrawal**. `ROUTING_PURITY_NOT_RESOLVED`.

## Explicit non-claims

This does **not** show:

- that clean address-dependent routing is unattainable (only that the tested within-window objectives
  do not *retain* it);
- that O1/O2 are useless (they reliably build correct-slot routing *during* the scaffold; the failure
  is persistence);
- any general LM benefit, natural-language transfer, production readiness, long-horizon retention,
  transfer across slot count / sequence length / model scale, KDA superiority, or speed/memory benefit.

O1/O2's 5/5 raw formation is **not** reframed as success.

## Standing limitations

- **Single-trajectory mechanistic reads on five seeds.** "Routing decays after withdrawal; needle is
  carried by a diffuse address-independent read" is well-supported by the prob trajectories + the
  randomized-address ablation, but the precise cause of the diffuse-read attractor is not established.
- **Focused scope.** Only R0/O1/O2/H3 were run; the persistence-oriented levers (O1R residual, H2
  functional teacher, H1 routing consolidation) and the C1 combination — the arms the mechanism points
  to — were **deferred**, and no Stage-2 development holdout was run. A negative screen of within-window
  objectives does not falsify the persistence levers.
- **Synthetic protocol, one architecture, one distance suite.**
- **Metric caveat.** "Wins vs R0" on needle saturates when both form; the decisive criteria are
  clean-stable count and the causal gate, which is how the verdict was reached.

## Scope guardrails (held)

No Phase / KDA / MLA / quadratic / N×N / new architecture / new inference-time op. Training used only
captured slot-address vectors (no answer label, evaluator outcome, or frozen randomized-address signal
— verified). `interventions.py`/`stabilize.py` disk hashes preserved; frozen `abc.json` unchanged.
