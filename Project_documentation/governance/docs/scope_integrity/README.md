# Scope-Carrying Conjunction Decomposition — Completion Report

*Isolated falsification study attacking the ClaimIntegrity residual (0.068 unsafe delivery,
concentrated in exception-bearing / scope-spanning conjunctions). Determines whether a **small**
scope-carrying transformer can reduce that residual without introducing new drift. Deterministic,
stdlib-only, no live calls. Consumes the FROZEN ClaimIntegrity downstream adapter read-only; modifies
no prior artifact.*

## The question

The ClaimIntegrity study left an unsolved residual: exception-bearing conjunctions ("X is approved, but
not during pregnancy unless monitored") that the preservation-first splitter keeps whole (under-split),
leaving the governing conjunct ungoverned — while aggressive splitting is worse because it detaches the
exception. Can a small, targeted transformer split these correctly, carrying the governing scope?

## The answer

**Yes — as a tightly-gated small extension, and only that way.**

- A **gated hybrid** (split a scope-spanning conjunction only when attachment is provable, carrying the
  postposed exception across conjuncts and resolving references; else preserve-and-flag) reduces the
  residual on the **un-rigged general ClaimIntegrity corpus from 0.068 to 0.000** — with no rise in
  false-rejection or evidence-query alteration.
- **Every ungated variant makes the general corpus dramatically worse** (0.218–0.472): aggressive
  scope-carry mangles non-conjunction text. The purpose-built scope corpus *flatters* those variants
  (0.074); the general corpus exposes them as undeployable. The claim rests on the general corpus, not
  the corpus built for the mechanism.
- **The single load-bearing rule is postposed-exception distribution.** Subject-carry, qualifier/
  exception prefixes, and even the spanning-modifier gate are not load-bearing for the actual residual
  (reference resolution already supplies the subject).

## Decision

**Option 5 — gated hybrid** (split-when-provable, else preserve-and-flag), as a small regex extension
over the frozen ClaimIntegrity splitter's output. Not full scope-carry (undeployable), not
subject-only (not load-bearing), not preserve-all (leaves the residual), not reject (the residual is
removable). The integration contract and the exact unresolved residual are in
`ARCHITECTURAL_DECISION.md`.

## Falsification scorecard

No condition rejects the *gated* mechanism. Two honest qualifications: spurious over-propagation
(~7.7%, converting to conservative false-rejection only) and the corpus-bounded nature of the "0.000"
(the transferable claim is directional). The ungated variants **are** rejected by condition 1 on the
general corpus. (`FALSIFICATION_AND_COMPLEXITY.md`.)

## Milestones

| M | Deliverable | Commit |
|---|---|---|
| M1 | prior-result freeze + scope model & protocol | (this branch) |
| M2 | scope-conjunction corpus (sc_corpus_v1, 520) + ground-truth protocol | — |
| M3 | six variants A–F + hybrid G | — |
| M4 | downstream evaluation + decisive general-corpus cross-check + gated H | — |
| M5 | ablation — minimum load-bearing rule set | — |
| M6 | freeze + tests + falsification/complexity + decision + integration contract + this report | — |

## Final tallies

- **Files:** `scope_integrity/` package (dataset, variants, eval_downstream, eval_ablation, verify_*,
  tests), 6 docs under `docs/scope_integrity/`.
- **Corpus:** `sc_corpus_v1`, 520 examples, 13 families, 8 domains, 1080 gold claims (880 unsafe-allow),
  120 ambiguous, 168 held-out, governing-scope graph per example.
- **Tests:** 10 ScopeIntegrity + 92 prior = **102 passed**; prior suites unchanged; both scope guards
  green; all 14 prior artifacts byte-identical.
- **Key result:** general corpus residual **0.068 → 0.000** (gated extension), no new harm; ungated
  variants 0.218–0.472 (undeployable); load-bearing rule = postposed-exception carry.

## Reproduce

```bash
python -c "from scope_integrity import dataset; dataset.dump_json('scope_integrity/data/v1/corpus.json')"
python -m scope_integrity.eval_downstream
python -m scope_integrity.eval_ablation
python -m scope_integrity.verify_frozen
python -m scope_integrity.verify_prior_artifacts
python -m pytest scope_integrity/tests claim_integrity/tests evidence_assurance/tests \
  assertion_governance/tests assertion_gate_robustness/tests model_selection_reconciliation/tests -q
# 102 passed
```

## Integrity notes

- **Frozen scorer:** unsafe delivery is measured by the ClaimIntegrity downstream adapter, unchanged —
  not a new scorer built to flatter the mechanism.
- **Held-out discipline:** 168 held-out examples (5th lexicalization + two entire ambiguous families);
  and the whole general corpus is effectively held out. The win survives both.
- **Anti-flattery:** the decisive evidence is the general-corpus cross-check, explicitly because the
  scope corpus was constructed around the mechanism and cannot, by itself, establish success.
- **Bounds stated as prominently as results:** the ambiguous residual (0.148, flagged not solved), the
  corpus-bounded 0.000, and the spurious-over-propagation cost are all in the headline.

## Document index

`SCOPE_MODEL_AND_PROTOCOL.md` · `GROUND_TRUTH_PROTOCOL.md` · `FALSIFICATION_AND_COMPLEXITY.md` ·
`ARCHITECTURAL_DECISION.md` · this `README.md`.
