# BindingSlots value-path & gradient-conflict diagnosis — report

**Primary verdict: `BINDINGSLOTS_BOTH_FAILURE_FAMILIES_LOCALIZED` · `KDA_VALIDATION_BLOCKED`.**

Diagnostic phase only — no fix implemented, no coefficient tuned, no subsequent intervention phase
begun. The two failure families the persistence screen could only hypothesize are now **mechanically
localized to two different stages**, and they have **different causes** (as §2 required).

## Reproduction (A0)

All **12/12** cohort runs reproduced **byte-identically** through the EXACT-equality gate
(`INSTRUMENTED_REPRODUCTION_ACCEPTED`), each with exactly 1200 optimizer steps and frozen snapshots
at 600/700/900/1200. Determinism was established first on control **A+ s25** (byte-identical
needle/ppl/trajectory) before any failure exemplar. See `METHODS_AND_REPRODUCTION.md` and
`results/reproduction_results.json`.

## Provenance

| Item | Value |
|---|---|
| Persistence merge (PR #1340) | `05dcee8e…` (reconstructed `NO_PERSISTENCE_INTERVENTION_SELECTED`) |
| source execution commits | A+/R0/O1R `5cc392e1`; H2 `9380bdb1` |
| Frozen `abc.json` | `b31989a3…` unchanged |
| Cohort | {A+, R0, O1R, H2} × {23,24,25}, frozen before tensor inspection |
| Verifier | `BINDINGSLOTS_VALUE_PATH_DIAGNOSIS_VERIFIED` (32 checks, 0 failures) |
| Tests | 21 classifier + 11 instrumentation, all pass |
| Authorized correction | classifier value-path "recoverable" test → functional A4a/A3 (see `code_correction_record.json`) |

## Per-seed mechanical diagnosis

| arm·seed | committed | ordinary needle | A3 addr | A4a read | A4b restore | value-path | quality |
|---|---|---|---|---|---|---|---|
| H2 s23 | FORMED_THEN_COLLAPSED | 0.00 | **1.00** | 1.00 | 1.00 | **ADDRESS_DISTRIBUTION_FAILED** | n/a |
| R0 s23 | FORMED_THEN_COLLAPSED | 0.00 | **0.99** | 0.99 | 0.99 | **ADDRESS_DISTRIBUTION_FAILED** | n/a |
| H2 s24 | CLEAN_STABLE (weak) | 0.28 | 0.36 | 0.36 | 0.38 | VALUE_PATH_NOT_LOCALIZED | n/a |
| R0 s24 | CLEAN_STABLE | 1.00 | 1.00 | 1.00 | 1.00 | NOT_APPLICABLE (present) | n/a |
| O1R s23 | CLEAN_STABLE | 1.00 | — | — | — | NOT_APPLICABLE (present) | n/a |
| O1R s24 | QUALITY_FAILED | 1.00 | — | — | — | NOT_APPLICABLE (present) | **QUALITY_GRADIENT_CONFLICT_LOCALIZED** |
| O1R s25 | QUALITY_FAILED | 1.00 | — | — | — | NOT_APPLICABLE (present) | **QUALITY_GRADIENT_CONFLICT_LOCALIZED** |
| H2 s25 | QUALITY_FAILED | 0.61 | — | — | — | NOT_APPLICABLE (present) | **QUALITY_GRADIENT_CONFLICT_LOCALIZED** |
| R0 s25 | QUALITY_FAILED | 0.12 | — | — | — | VALUE_PATH_NOT_LOCALIZED | QUALITY_INTERFERENCE_NOT_LOCALIZED |

## Family 1 — value path: the read *address* fails, the memory does not

On both collapsed seeds (H2 s23 **and** plain-CR1 R0 s23) the stored value is intact and usable:
cosine(m_postwrite, m_query) = 0.996 / 0.952, and **all three oracle bypasses recover retrieval**
(oracle one-hot address, direct query-time read, and post-write restore → needle ≈ 1.0; answer-logit
margin flips from −6.0/−9.5 to +6.4/+5.6). Ordinary retrieval fails because the eval-time read places
only **0.58–0.60** probability on `s*` — enough to prefer it on the fixed probe (~0.96 there) but not
to win on the real eval distribution. **This is not a broken-memory or readout failure; it is an
evaluation-time read-address selection/generalization failure**, and it is **not teacher-specific**
(plain R0 shows it too). The linear probe reads these collapsed slots at ~chance, but per §9 that is
not evidence of absence — the oracle bypasses prove the value is present and usable.

## Family 2 — quality: a gradient conflict in the write-address projection

Every quality-failed seed shows materially negative LM-vs-auxiliary gradient alignment concentrated
in the **write-address projection** (`write_addr_proj`, i.e. `W_wk`), with the clean controls
positive:

| group | O1R s23 (clean) | O1R s24 | O1R s25 | H2 s24 (clean) | H2 s25 |
|---|---|---|---|---|---|
| write_addr_proj | +0.24 | **−0.12** | **−0.25** | +0.10 | **−0.21** |
| write_gate | +0.06 | **−0.26** | −0.06 | +0.09 | +0.15 |

The persistence/teacher objective and the language-model objective pull the addressing parameters in
opposing directions; this is an optimization-balance failure localized to the addressing machinery,
**distinct** from the read-address selection failure of Family 1. R0 s25 is quality-failed but has no
persistence/teacher auxiliary, so its quality failure is correctly **not** attributed to a gradient
conflict (`QUALITY_INTERFERENCE_NOT_LOCALIZED`) — an honest null.

## H2 s24 — weak-former control

H2 s24 passes the clean-stable gate weakly (needle 0.28) but with **read probability 0.01 on `s*`**
and oracle address barely helping (0.28 → 0.36): its residual retrieval is **address-independent**,
not slot-routed. It is reported `VALUE_PATH_NOT_LOCALIZED` (gray-zone retrieval, no clean boundary) —
the correct, non-forced outcome, and a caution that "clean-stable" can be achieved off the slot path.

See `VALUE_PATH_AND_QUALITY_FINDINGS.md` for detail, `NEXT_INTERVENTION.md` for the single
evidence-implied next step, and `LIMITATIONS_AND_NONCLAIMS.md`. KDA remains blocked.
