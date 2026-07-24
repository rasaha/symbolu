# Final Recommendation — Should Assertion Governance Be an Independent Layer?

*Phase 11. One question, answered from the evidence. Optimistic conclusions are avoided; the
verdict is bounded by the limitations.*

## Verdict: **ONLY FOR HIGH-RISK DOMAINS — and as a thin composition, not a novel engine.**

## The three-part evidence chain

1. **Beyond single existing techniques: value is real and safety-critical.** Confidence (0.31),
   grounding (0.38), entailment (0.69), and authority (0.37) all fail the delivery decision, most
   with dangerous unsupported-escape rates. A governance step that combines evidence support,
   claim strength, and risk reaches 0.97–1.00 agreement with 0.00 escape. On the primary research
   question — *does an assertion-governance layer add measurable value beyond existing techniques?*
   — the answer is **yes, versus any single technique.**

2. **Beyond a trivial composition of existing signals: no.** A grounding+entailment step **plus a
   risk rule** (Baseline G_risk) reproduces the ground truth **exactly (1.00)** and **strictly
   dominates the dedicated AGE engine** (beats it on 6 items, loses on 0). The delivery decision
   **decomposes** into existing signals + a risk overlay; a bespoke engine is not required and here
   is slightly worse.

3. **The value is risk-concentrated.** Grounding+entailment already scores **1.00 on low-risk**
   items; the entire lift of a governance layer is on **high-risk** items (0.59 → ~1.00), where the
   risk-sensitive escalation and the safety-critical zero-escape matter.

## Why not the other verdicts

- **Not "YES" (a full independent engine).** The dedicated engine did not beat a trivial risk-
  augmented composition of existing signals. Building a heavyweight standalone engine is not
  justified by this evidence.
- **Not "NO".** It does add real, safety-relevant value over every single existing technique —
  discarding it entirely would reintroduce unsupported-escape and risk-blind delivery in exactly
  the domains that matter.
- **Partly "NOT ENOUGH EVIDENCE" for the real-world case.** The synthetic corpus makes the
  decomposition clean by construction; noisy real signals + human labels could shift the balance.
  The high-risk recommendation is robust here; the "no novel engine needed" claim is corpus-
  specific and should be re-tested on real data before being treated as settled.

## What this means architecturally

Assertion Governance should exist as a **thin, risk-aware composition layer** at the delivery
boundary — specifically:

- **inputs:** a grounding/support score + an entailment relation (reuse existing components) + risk
  class;
- **decision:** the risk-augmented composition (G_risk-style), not a bespoke engine;
- **transform:** the QUALIFY rewrite (a genuine capability no signal provides);
- **scope:** activated for **high-risk domains**; in low-risk domains, grounding+entailment alone
  suffices and the layer can be skipped to save latency + human burden.

This aligns with the Shadow Pilot's finding that an assertion-governance boundary was *missing* —
but the correct fix is a thin composition over existing signals, **not** the elaborate engine one
might assume, and **not** the TAP authority-resolution proxy (which scored 0.37).

## Falsification outcome

- Preregistered rule "AGE SUPPORTED if it exceeds every baseline by >0.05": **met vs existing
  techniques** (A–G), **not met vs G_risk** (the anti-circularity control), which was the decisive
  comparison. Reported honestly: the *function* is supported; the *dedicated engine* is not.
- The negative finding — a dedicated engine underperforms a trivial risk-augmented composition — is
  stated plainly, per the scientific-discipline requirement.

## One-line answer

**Assertion Governance deserves to exist as a layer only in high-risk domains, and only as a thin
composition of existing grounding+entailment signals with a risk rule and a qualification
transform — not as a novel standalone engine.**
