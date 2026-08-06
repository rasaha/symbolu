# Typed-vs-prose result — constant-output & shortcut analysis (Stage 2, parts K & L)

Audit-only descriptive diagnostics. These **do not** alter the locked verdict; they characterize
what the locked primary metric does and does not measure. Computed from the frozen dataset
constructors over large multi-seed cohorts.

## K. Constant-output split audit
Each scenario is built from one fixed structural template; only the identifiers vary (via
`relabel_episode`). Consequently the **graded field's gold value** is constant for several splits:

| Split | Graded field | Gold value across cohort | Constant predictor scores 1.000? | Enters primary? |
|---|---|---|---|---|
| S1 | selected_entity_id | **varies** (fresh relabeled id) | No — must copy the id | **Yes** |
| S2 | selected_entity_id | **varies** | No — must copy the id | **Yes** |
| S3 | relation_supported | always `True` | **Yes** | **Yes** |
| S4 | selected_entity_id | **varies** | No | No |
| S5 | evidence F1 | evidence ref **varies** | No — must select the ref | **Yes** |
| S6 | abstention (status) | always `INSUFFICIENT_EVIDENCE` | **Yes** | **Yes** |
| S7 | abstention (status) | always `INSUFFICIENT_EVIDENCE` | **Yes** | No (safety split) |
| S8 | relation_supported | always `False` | **Yes** | No (stable-direct) |

**Finding.** Of the five primary components {S1, S2, S3, S5, S6}, **two (S3 and S6) are
constant-gold components**: a predictor that always emits the constant answer scores 1.000 on them.
S1/S2 (entity copy) and S5 (evidence-ref selection) require reading varying context. Therefore any
model that learns just the two constants floors at **2/5 = 0.40 primary**, which is why both arms
sit at ≈0.40–0.46.

Per the protocol-lock wording, the construction was **protocol-compliant** — Decision 3 explicitly
defines the primary to include S3 and S6, and both arms face the identical split mix. The required
caveat:

> Two of the five primary components are constant-output components. The absolute primary score
> therefore overstates general relational competence, although the paired B1 − B0 comparison
> remains mechanically symmetric.

**Audit-only diagnostic (does not replace the locked verdict):** a *non-constant selection score* =
mean of only the varying-content primary components {S1, S2, S5-F1} isolates the copy/selection
signal. On the reserved final means this is ≈0.06 (B1) / ≈0.09 (B0) — i.e. **both arms are at or
near floor on the components that actually require reading the structure**, with prose marginally
higher. The locked primary (with the two constants) is 0.435 (B1) / 0.457 (B0). The
non-constant diagnostic is reported by the audit-replay reconstruction alongside the locked
primary.

**Non-constant split characterization (S1, S2, S4, S5):** two same-type candidates each (chance
≈0.5 on entity selection); disjoint unseen-ID final pool [600,1000) with zero overlap against the
train pool [100,600); the correct answer is an opaque identifier that must be **copied token-for-
token from context**. This is exactly the capability the follow-on copy/selection probe isolates.

## L. Shortcut-gate audit
Locked gate: each shortcut baseline must be ≤ **chance + 0.05** on its relevant split (chance
computed per split); a baseline exceeding that "requires investigation **before** reserved
execution", and the benchmark is **not** adjusted after inspecting reserved results.

Measured lexical-overlap baseline (same-type candidate sharing most characters with the query id),
chance = 0.5, bound = 0.55:

| Cohort | per-seed lexical-overlap | mean |
|---|---|---|
| dev 760/761/762 | 0.431, 0.514, 0.431 | **0.458** (below chance) |
| final 7160–7164 | **0.639**, 0.514, 0.583, 0.514, 0.486 | **0.547** |

**Findings.**
1. The reported "0.639" is specifically the **worst of the five** final seeds (7160, the cohort the
   driver's shortcut check happened to use). The final-cohort **mean is 0.547** (≈ chance+0.047);
   dev cohorts average 0.458 (below chance). The pattern — scattered around 0.5 with occasional
   ~0.64 excursions on 72-item cohorts (binomial sd ≈0.06) — is consistent with **small-sample
   noise around chance**, not systematic label leakage. After `relabel_episode`, identifiers are
   random, so query-candidate character overlap has no lawful signal.
2. **Process deviation (documented):** the locked protocol expects shortcut baselines to be
   investigated **before** reserved execution; in the executed driver the baseline was computed
   **during** the final phase on one cohort. The shortcut check was therefore not run as a
   pre-reserved gate. This is a process gap, recorded honestly; it is **not** remediated by
   re-touching the benchmark (forbidden after inspecting reserved results).
3. **Classification.** On the reserved data the baseline **marginally exceeds** the 0.55 bound on
   2/5 seeds (mean 0.547). Mapped against the locked outcome logic:
   - It **cannot** satisfy the validated outcome: 0.55–0.64 is far below the 0.80 primary bar and
     the S1/S2 ≥0.85 per-split bars; and the *learned* models scored **below** the shortcut
     (S1 ≈0.05–0.09), so no representation gains a false advantage from it.
   - The endpoint verdict is `ADVANTAGE_NOT_FOUND` on the improvement/floor conditions
     **independently** of the shortcut gate.
   - Therefore the shortcut anomaly is classified as a **documented limitation + process deviation
     that does not change the not-found outcome**, not as a result-altering leakage finding.

The audit report keeps three things explicitly separate: the **endpoint null**, the
**shortcut-baseline anomaly**, and the **causal non-interpretability due to near-floor clean
competence**.
