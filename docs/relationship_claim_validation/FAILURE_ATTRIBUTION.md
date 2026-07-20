# Failure Attribution (v0.1)

Where each ablation fails, and to which missing component the failure attributes.
From the deterministic run.

> Scope: synthetic, self-contained; failures are of the *mechanism decomposition*,
> not real-world behavior.

---

## 1. Baseline (V0) failures

V0 retains everything → **28 false acceptances** (fp): 8 contradicted, 8
unsupported, 8 insufficient, 4 unknown-conflict claims are all kept. Attribution:
no claim-truth layer — the exact assumption this experiment tests.

## 2. Deterministic-only (V1) failures

V1 → **20 false removals** (fn), recall 0.0. Attribution: deterministic checks
cannot affirm semantic support, so every claim that is not structurally invalid is
abstained. Failure attributes to the **absence of any judge**.

## 3. Advocate-only (V2) failures

V2 → **12 false acceptances** (fp). Attribution: no challenger. The advocate
confirms the relation is asserted but never looks for contradicting or reverse
evidence, so it accepts the 8 explicitly-contradicted claims and the 4
direction-conflict claims. Failure attributes to the **absence of Judge B**.

## 4. Advocate+challenger (V3) failures

V3 → **4 false acceptances** (fp). Attribution: no adjudicator. When the advocate
and challenger both fire explicitly on the same predicate (direction), V3 resolves
in the advocate's favor and retains the claim. Failure attributes to the **absence
of Judge C**.

## 5. Full system (V4)

V4 → **0 false acceptances, 0 false removals** on this corpus. No residual failures
were produced. This is **by construction** (the deterministic judges implement the
grounding logic the gold encodes); it is **not** a claim that the mechanism has no
failure modes on real data. Likely real-world failure modes — not exercised here —
include: paraphrastic relations the rule matcher misses, implicit direction,
multi-hop supersession, and adversarial citation. These are future work.

## 6. Attribution summary

| Missing component | Symptom | Ablation exposing it |
|---|---|---|
| claim-truth layer | mass false acceptance | V0 |
| any judge | recall collapse (over-abstention) | V1 |
| challenger (B) | contradictions accepted | V2 |
| adjudicator (C) | equally-explicit conflicts accepted | V3 |

Each component removes a **distinct, non-overlapping** failure class — the core
finding of the ablation.
