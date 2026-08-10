# Human-Validation Gap (Phase 1)

*What "human validation" means here, why the prior simulated proxy does not close it, and what this track
will and will not claim in an environment without real reviewers.*

## The gap

The minimal policy is **technically validated** (10/10 frozen criteria: 50% clean allow, 0% over-
qualification, 0 unsafe high-risk/action allows, 0 self-verification escapes, monotonic). It is **not
human-validated**: no real person has independently judged whether its evidence obligations, source-
authority calls, allow/qualify/withhold decisions, and explanations are correct and usable.

The prior track computed an independent dual-rubric **proxy** (agreement ~0.50, policy ≥ gold on 98% of
the review set). That proxy was explicitly labelled **NOT human validation**, and it remains so here. A
deterministic rubric cannot tell us whether a *human* finds the policy's obligations reasonable, its
explanations clear, or its review burden tolerable — which is exactly the question that gates external
use.

## What only real reviewers can answer

- Do independent reviewers assign **similar evidence obligations** (acceptable-obligation agreement)?
- Do they **agree with allow / qualify / withhold / review** decisions?
- Do they **identify unsafe allows** the system missed?
- Can they assess **source authority** reliably?
- Do the **explanations** reduce review time and improve agreement?
- Is the **review burden** (mandatory-review volume) manageable?
- Where disagreement occurs, is it a **policy defect, a guide defect, or irreducible ambiguity**?

None of these can be answered by simulation without smuggling the policy's own logic back into the
"validation" — the circularity the whole series has avoided.

## This environment: no real reviewers

This execution environment has **no real human reviewers**. Therefore, following the governing spec:

1. **Build all preparatory and technical infrastructure** — governance, guide, training/final sets,
   ground-truth protocol, blinded interface, frozen policy runner, orchestrator, metrics, disagreement
   taxonomy, stop conditions, dry run (machinery test only), falsification plan, tests, evaluation
   freeze. These are real, complete, and **ready for real reviewers**.
2. **Do not run the outcome-bearing review** (Phase 16) or produce a human-validation result — there are
   no humans to produce it.
3. **Return `NOT ENOUGH HUMAN EVIDENCE`** for the calibration decision (Phase 20, Option 8) and the pilot
   decision (Phase 21, Option I).
4. **Do not recommend an external customer shadow pilot.**

## What this track will and will not claim

- **Will claim:** a complete, audited, replayable, blinded-review **apparatus** exists and works (proven
  by a clearly-labelled dry run using a *mock* reviewer that is never called validation); the frozen
  policy runs read-only through it; the evaluation is frozen and ready.
- **Will not claim:** any human agreement, any human-validated safety/utility, or any external-pilot
  readiness. The dry-run mock reviewer is a **machinery test**, not evidence about the policy.

## Consequence

The honest terminus of this track — absent real reviewers — is **NOT ENOUGH HUMAN EVIDENCE**: the
infrastructure is ready, but the human evidence that would justify external progression does not exist
and must not be fabricated. This is a success of the method (it refuses to manufacture validation), not a
failure of the policy.
