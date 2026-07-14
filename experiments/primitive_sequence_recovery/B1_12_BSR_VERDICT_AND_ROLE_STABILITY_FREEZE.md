# B1.12 BSR — Verdict, Role-Stability & Operative-Taxonomy Freeze (pre-run amendment)

**Docs-only amendment, frozen BEFORE any model call and outcome-blind.** It operationalizes — and does **not**
modify — the controlling preregistration `VARNA_SYMBOLIC_RESONANCE_PREREG_V1.md`, which froze the component BSR
scale (100/75/50/25/0) and the relationship-type principle but did **not** freeze numeric word-level verdict
thresholds, a role-dependence rule, or the exact operative relationship set for the multi-LLM crossover. Those are
frozen here, ahead of execution, so no cutoff is derived after seeing outputs. `EXPLORATORY / DEVELOPMENT_ONLY /
NOT_CONFIRMATORY_EVIDENCE`.

## 1. Operative relationship taxonomy (frozen for this run)

The controlling prereg §4 froze **8** types. The crossover run instruction names **10** (adding *constitutive
property* and *generation*). To avoid inventing types mid-run, the operative set for this run is frozen here as the
**explicit 10** (the prereg's 8 plus the 2 named in the run instruction). Any type outside this set is an
`invented_relationship` and is rejected/retried.

`embodiment · constitutive_property · characteristic_expression · implication · natural_consequence · generation ·
opposition · resolution · regulation · containment`

**Compatibility groups** (for mechanical relationship agreement — two types are *compatible* iff in the same
group, else *incompatible*):
- **IS/HAS:** embodiment, constitutive_property, characteristic_expression
- **LEADS-TO:** implication, natural_consequence, generation
- **AGAINST:** opposition, resolution
- **GOVERNS/HOLDS:** regulation, containment

## 2. Component BSR scale (restated from the controlling prereg — unchanged)

`100` directly/characteristically accounted for · `75` strongly implied · `50` plausible, needs interpretation ·
`25` needs substantial qualification / an external actor · `0` cannot be supported without added meaning. Only
these five values; the combined score never repairs a weak component.

## 3. Word-level verdict thresholds (frozen)

Computed **mechanically** from the per-occurrence BSR scores (mean, min). Combined reconciliation is explanatory
only and never changes the verdict.

| Verdict | Rule |
|---|---|
| `STRONG_RESONANCE` | mean ≥ 75 **and** min ≥ 50 |
| `MODERATE_RESONANCE` | 50 ≤ mean < 75 (and not STRONG) |
| `WEAK_RESONANCE` | 30 ≤ mean < 50 |
| `MINIMAL_RESONANCE` | 15 ≤ mean < 30 |
| `NO_RESONANCE` | mean < 15 |

- **`HOLISTIC_ONLY_RESONANCE`** flag: set when combined_reconciliation ≥ 75 **and** mean < 50. Reported; **does
  not** promote the verdict (per the prereg's "combined never overwrites components").
- **`INDETERMINATE`** is a **cross-run** label only (§5 no-forced-consensus): a *word* is INDETERMINATE when the
  two runs materially disagree (verdict differs by ≥2 bands, or a ≥50-point mean gap). It is never assigned within
  a single run.

## 4. Role-dependence rule (frozen verbatim from the run instruction)

- **`ROLE_STABLE`** — exact word-verdict agreement ≥ 80% **and** within-one-step component agreement ≥ 80% **and**
  ≤ 2 material profile disagreements **and** no systematic direction favoring one scorer.
- **`MINOR_ROLE_DEPENDENCE`** — exact word-verdict agreement 60–<80%, **or** within-one-step component agreement
  60–<80%, with no catastrophic pattern.
- **`SIGNIFICANT_ROLE_DEPENDENCE`** — exact word-verdict agreement <60%, **or** within-one-step component agreement
  <60%, **or** a major systematic scorer/role effect.
- **`RUN_INVALID`** — input mismatch, model substitution, cross-run leakage, output corruption, or frozen-rule
  violation.

"Within-one-step" = |score_A − score_B| ≤ 25. "Material profile disagreement" = profile similarity < 0.30
(token-Jaccard on content words). "Systematic direction" = signed mean score difference |A−B| ≥ 15 across all
components.

## 5. No forced consensus (frozen)

The two runs are **not** averaged into one authoritative score. Both judgments are retained. Material
disagreements are reported and the word is labeled **evaluator-sensitive**; `INDETERMINATE` is used only per §3.
No third judge is added in this run.

## Guardrails
Docs-only, frozen before execution. The controlling preregistration, parser, mappings, frozen word list, and all
prior artifacts are unchanged. These thresholds/rules are fixed now and must not be altered after results are
seen. Structure, not validated meaning.
