# B1.2 Powered R3 V↔G Style-Tell Re-Adjudication

## Status: `STOP_NOW_R3_STYLE_TELL_ROBUST_FAIL`

The properly powered re-adjudication confirms, robustly, that the varṇa prediction **V** and the dictionary
answer key **G** are **distinguishable by surface style**. This is style-tell re-adjudication only — **no
mapping-fidelity alignment, no Symbol-U fit scoring, no renderer tuning, no target change**. B1.1 verdict
unchanged; Track B BLOCKED; no ontology / Sanskrit / semantic-truth claim. **Structure, not validated meaning.**

## Result

| metric | value |
|---|---|
| target set | frozen 70 words, hash `fe7aa7ac…` (verified) |
| signatures | **140** (70 V + 70 G) |
| renderer | committed symmetric matched-length keyword schema (2-step None→cap6; applied `maxlen=6`); **no tuning** |
| **balanced accuracy** | **0.7000** |
| **95% bootstrap CI** | **[0.5929, 0.7929]** (word-clustered, N_boot 1000, seed 80809) |
| V recall | 0.757 | 
| G recall | 0.643 |
| confusion (V→V, V→G, G→V, G→G) | 53, 17, 25, 45 |
| base rendering (maxlen=None) balanced accuracy | 0.75 (diagnostic) |

## Acceptance criterion (documented conflict → stricter rule applied)

- **R3 adjudication §4:** PASS = balanced accuracy ≤ 0.55 **AND** CI touching 0.5 (AND; stricter).
- **Task criterion-5 phrasing:** PASS = ≤ 0.55 **OR** CI includes/touches 0.5 (OR; easier).
- The freeze memo did **not** explicitly supersede, so per instruction the **stricter AND** is applied.

**Outcome under both rules:**

- `balanced accuracy ≤ 0.55`? **No** (0.70).
- `CI includes 0.5`? **No** (CI [0.5929, 0.7929] excludes 0.5).
- **Stricter AND → FAIL.** **Easier OR → also FAIL.** The result is unambiguous either way; the criterion
  conflict does not affect the decision.

## Interpretation

- At the provisional N=16 the point estimate was 0.5625 — a marginal miss that was **underpowered noise**.
- With proper power (N=140, CI excluding chance), the true style separability is **0.70** — V and G are
  **robustly distinguishable by surface style** under the committed symmetric matched-length keyword schema.
- **Why it matters:** if a blinded judge can tell V from G by style alone, any future V↔G *alignment* signal
  would be **confounded by style rather than measuring semantic fit**. The R3 comparability blocker — the
  "fragile point" flagged since the restriction adjudication — is now **robust**, not marginal.
- This is a property of the *rendering/register gap* between varṇa-gloss prose and dictionary-feature text; it
  is **not** a mapping-fidelity result and makes **no** claim about Symbol-U's truth or falsity. It only says
  the two pipelines cannot be rendered comparably enough (under the frozen, one-revision schema) to run a
  fair blinded alignment test.

## Integrity checks

- **B1.1 artifacts unchanged**; B1.1 verdict `RANDOM_OR_SCRAMBLED_MATCHES` unchanged.
- **No B1.2 mapping-fidelity scoring** was run (style-tell only).
- **No renderer tuning** (committed schema reused; the single committed revision `maxlen=6` reproduced, not
  re-tuned).
- **No target replacement** (frozen 70-word set, hash verified).
- **No threshold relaxation** (0.55 bar unchanged; stricter criterion applied).
- **No ontology / Sanskrit / semantic-truth claim.**

## Final status block

```
document:                   B1.2 POWERED R3 style-tell re-adjudication (audit only)
status:                     STOP_NOW_R3_STYLE_TELL_ROBUST_FAIL
balanced_accuracy:          0.7000
ci_95:                      [0.5929, 0.7929] (excludes 0.5)
n_signatures:               140 (70 V + 70 G)
criterion:                  stricter AND applied; FAILS under AND and OR both
renderer_tuned:             NO
targets_changed:            NO
mapping_fidelity_scored:    NO
threshold_relaxed:          NO
B1.1 verdict:               UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
LIMITED_GENERATION_UTILITY: NOT earned
Track B:                    BLOCKED
Track G / Track F:          RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next gate:                  VARNA_LINE_CLOSURE_MEMO
```

**Structure, not validated meaning.** The powered audit shows V and G are robustly style-separable, so a fair
blinded V↔G alignment test is not achievable under the frozen rendering; the STOP is now robust, the B1.1
verdict stands, and Track B remains BLOCKED.
