# Ground-Truth Protocol (Phase 6)

*How the reference outcome is established. The reference must **not** come from the frozen minimal policy
alone — it comes from independent real reviewers, adjudicated. This protocol is complete and ready; in the
absence of real reviewers it produces no labels.*

## Principle

The policy is the thing under test, so it cannot be its own ground truth. The reference obligation for
each final artifact is the **independent judgment of real reviewers**, adjudicated where they disagree.
The minimal policy's decision is one input to the comparison, never the reference.

## Independent labelling

- **Reviewer A**, **Reviewer B**, and (optionally) **Reviewer C** each label every final artifact
  **independently and blind**: before seeing the system outcome, any other reviewer's outcome, or any
  prior rubric label.
- A separate **adjudicator** (independent of A/B/C on the artifacts they adjudicate) resolves
  disagreements.

## Labels each reviewer assigns

For every artifact: factual or non-factual; risk tier; claim type; source role; source authority;
actionability; temporal sensitivity; **minimum evidence obligation (E0–ER)**; whether available evidence
**satisfies** the obligation; whether **allow would be safe**; whether **qualification** is needed;
whether **human review** is required; whether an **action** is present; and the **acceptable native
ActionGate outcome** where applicable.

## Adjudication

Where reviewers disagree, the adjudicator forms the reference by:

- adopting the agreed label where A/B/(C) concur;
- resolving conflicts conservatively (toward the higher obligation / withhold) on **safety-relevant**
  disagreements;
- recording **unresolved disagreement** rather than forcing a consensus where the disagreement is
  irreducible domain ambiguity.

High-risk disagreement is never resolved toward the lower obligation.

## What is recorded

- Each reviewer's independent label (blind, Stage A).
- The adjudicated reference (or `UNRESOLVED`).
- Agreement statistics (Phase 10 metrics): acceptable-obligation, exact, risk, source-authority,
  clean-allow, evidence-satisfaction, qualification, review-required, native-ActionGate agreement.
- Disagreement classification (Phase 11 taxonomy).

## Separation from the policy

The reference is built from human labels only. The frozen policy's output is compared **against** it,
never mixed **into** it. This is the guarantee that human validation, if produced, is genuine and not a
restatement of the policy.

## Status in this environment

No real reviewers → **no independent labels, no adjudicated reference, no agreement statistics.** The
protocol is complete and executable the moment real reviewers are engaged; until then the ground truth is
**absent**, and the track returns NOT ENOUGH HUMAN EVIDENCE rather than substituting a rubric.
