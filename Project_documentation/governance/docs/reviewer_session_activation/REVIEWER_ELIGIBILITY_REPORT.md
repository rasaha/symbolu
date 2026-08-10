# Reviewer Eligibility Report (Phase 2)

*Activation of the frozen reviewer workflow for a real calibration round. Produced by
`reviewer_session_activation/eligibility.py` against the roster supplied in the request. No reviewer
infrastructure was rebuilt; the frozen apparatus is consumed read-only.*

## Result: ACTIVATION BLOCKED — no real, eligible reviewers supplied

The roster in the request consists entirely of **unfilled template placeholders** (`[R1_ID]`, `[YES/NO]`,
`[SCOPE]`, …). Per the binding rules — *"Do not create fake reviewers," "Do not use test identities as
real reviewers," "Do not infer completion where a field is marked NO or missing," "Do not activate the
session unless both R1 and R2 pass"* — the gate treats every placeholder as **missing**, never as
complete, and refuses to activate.

**Real, eligible reviewer count: 0 of 2 required.**

## Per-reviewer findings

### R1 — FAIL (not real, not eligible)
- `pseudonymous_id`: `[R1_ID]` — **missing / unfilled placeholder**
- `real_reviewer`: asserted `YES`, but **not backed by a filled, non-placeholder ID** → not a real person
- `role`: `[TECHNICAL REVIEWER / …]` — **missing / unfilled placeholder**
- `confidentiality acknowledgment`: `[YES/NO]` — **not complete**
- `conflict-of-interest declaration`: `[YES/NO]` — **not complete**
- `approved access scope`: `[SCOPE]` — **missing**

### R2 — FAIL (not real, not eligible)
- Identical placeholder state to R1 across every field.

### A1 (optional adjudicator) — ABSENT
- `pseudonymous_id`: `[A1_ID OR NONE]` — recorded **absent / not supplied**. An adjudicator is optional;
  its absence does not by itself block the round, but there are no qualified reviewers to adjudicate
  between in any case.

## What the gate did NOT do

- It did **not** infer any acknowledgment, declaration, or identity from a placeholder.
- It did **not** substitute a mock or test identity for a real reviewer.
- It did **not** activate training, qualification, or any calibration review.

## Consequence

With zero real eligible reviewers, the session cannot be activated for a human calibration round. No
training was delivered, no qualification was run, no calibration reviews were collected, and no human
metrics were computed. All human-dependent outcomes remain **NOT EVALUATED**.

To activate, resubmit the roster with, for **both** R1 and R2: a real pseudonymous ID (not a
mock/test-looking one), an assigned valid role, `confidentiality acknowledgment = YES`,
`conflict-of-interest declaration = YES`, and an approved access scope — with `real_reviewer` genuinely
true and backed by that filled ID.
