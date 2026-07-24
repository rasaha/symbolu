# Adversarial Decomposition Study (Phase 17)

*`claim_integrity/adversarial.py` + `eval_adversarial.py` → `eval_results/adversarial.json`. 25 cases
engineered to induce semantic drift. Each is run through every method; "silent drift" = the method
produces a fluent decomposition whose audited disposition is a drift state.*

## Which methods silently alter meaning

| Method | silent drift / 25 | rate |
|---|--:|--:|
| Q_oracle | 0 | 0.00 |
| **P_claim_integrity** | **0** | **0.00** |
| A_preserve_whole | 2 | 0.08 |
| B_sentence_split | 2 | 0.08 |
| H / I / J / K / L / M | 2 | 0.08 |
| N_minimal_split | 3 | 0.12 |
| R_learned_comparator | 4 | 0.16 |
| C_clause_split / O_aggressive | 14 | 0.56 |
| D_dependency / E_srl | 16 | 0.64 |
| F_openie / G_rule_spo | 21 | 0.84 |

## Reading

- **Triple/parser/aggressive methods drift on the majority of adversarial cases** (0.56–0.84). Stripping
  modifiers to a bare SPO core inverts modality, drops negation, detaches exceptions, and mutates
  numerics — exactly the meaning inversions the taxonomy's "reject" class covers.
- **The component reaches 0**, matching the oracle, but the margin over sentence-splitting is **two
  cases**, and both are specific: (1) a conjunction carrying two independently-evaluable claims, where
  sentence-splitting under-splits and omits one, and the component splits correctly; (2) a rhetorical
  question followed by a claim, where sentence-splitting extracts the question as a claim and the
  component filters it as non-assertive.
- **Preserve-whole is *not* uniformly safest here** (2 drift): on genuinely-two-claim adversarial text
  it omits a claim. That refines the H0-17 picture — "preserve the whole sentence" is safe against
  *meaning-inversion* drift but fails *completeness* when one sentence carries two claims.

## Two honest process notes

1. **A gold-construction bug, found and fixed.** The first run showed the component drifting on 3 cases
   and *worse* than sentence-splitting. Investigation showed two of those "drifts" were a scoring
   artifact: two cases are genuinely two-claim text, but their gold listed only one claim, so the
   component's *correct* second claim was falsely flagged INVENTED. The gold was corrected to list both
   claims (both cases now carry two golds); only then did the true picture appear. Recorded here rather
   than silently reconciled — the same discipline applied to the EvidenceAssurance corpus v1_1 fix.
2. **A capability added because the study exposed its absence.** The remaining real drift was the
   component extracting a rhetorical question ("Is it safe?") as a claim. The taxonomy already commits
   that `rhetorical_non_assertive` text must not be extracted (failure type 45), so a non-assertive
   filter was added to the component. This is a taxonomy-mandated capability the adversarial study
   surfaced, not a tune-to-the-test — and it changed nothing on the main corpus (P still ≡ B at
   754/832), because the main corpus contains no rhetorical questions.

## What this does and does not establish

It establishes that **stripping decomposition (triples/SPO) is dangerous** and that a preservation-
first component avoids the meaning inversions on constructed traps. It does **not** establish that the
component beats sentence-splitting in practice: the margin is two adversarial cases, and on the 832-case
main corpus the component and sentence-splitting are identical at the intrinsic layer. Whether the
component's edge on multi-claim splitting and non-assertive filtering translates into fewer **unsafe
downstream deliveries** is the Phase-18 question — still unanswered here, by design.
