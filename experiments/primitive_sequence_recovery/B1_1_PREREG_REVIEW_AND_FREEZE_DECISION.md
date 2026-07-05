# B1.1 Prereg Review & Freeze Decision

## 1. Scope and non-claims

**Review / decision memo only.** Reviews the B1.1 prereg draft (`9d474f2`) and decides whether B1.1 can move
toward freeze under fallback-qualified status. **No freeze · no model run · no generation / scoring /
judging.** Does **not** modify B1, change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B
(**BLOCKED**). No ontology validation, Sanskrit privilege, or semantic-truth claim. **Structure, not
validated meaning.**

## 2. Prereg completeness review

Verified against `B1_1_PREREG.md` (22 `##` sections present):

| required element | present? |
|---|---|
| prior fixed results (B1, Track G `1fe5562`, Track F) | ✓ §2 |
| research question | ✓ §3 |
| can / cannot prove | ✓ §4 |
| materials | ✓ §5 |
| fallback caveat (verbatim) | ✓ §6 |
| arms (A/D/S/R_same/R_deranged/R_domain/C/X) | ✓ §7 |
| arm construction rules | ✓ §8 |
| tasks (T1–T6; T4 tracked separately) | ✓ §9 |
| models | ✓ §10 |
| seeds / sampling | ✓ §11 |
| leak scan | ✓ §12 |
| blinded judge packets | ✓ §13 |
| judge panel | ✓ §14 |
| scoring plan | ✓ §15 |
| primary success criterion (beat R_deranged ∧ R_domain ∧ R_same) | ✓ §16 |
| kill criteria | ✓ §17 |
| verdict labels | ✓ §18 |
| persistence requirements | ✓ §19 |
| non-rescue clause | ✓ §20 |
| go / no-go before freeze | ✓ §21 |
| final status block | ✓ §22 |

**Completeness result: COMPLETE as a draft.** All 22 required elements are present. The prereg *documents*
the plan; it does not yet *bind* the run-time configuration (see §4).

## 3. Scientific risk review

- **Embedding gate still blocked** (`BLOCKED_DEPENDENCY_UNAVAILABLE`, huggingface.co egress-denied); the deep
  semantic-contrastivity check was never run and is **still owed**.
- **Local audit is surface-only** (`PASS_LOCAL_SURFACE_ONLY`) — blind to paraphrase synonymy.
- **Elevated R-risk remains**: R_same / R_deranged / R_domain may stay strong for reasons the fallback cannot
  detect.
- **`R_deranged` is the crux** — it isolates word-specific fit at maximal mapping quality; if A can't beat it,
  H2-specific utility is unsupported regardless of contrastivity.
- **A positive result can only be `LIMITED_GENERATION_UTILITY`** (in-architecture, this frozen design) — not
  ontology validation.
- **A failure cannot be rescued** (§20 of the prereg): no hidden-signal reinterpretation, no Track B unblock;
  "better wording/embedding might work" is at most a *new* prereg. Two prior negatives (Track G, B1) stand in
  the evidence base.

## 4. Freeze-readiness checklist

| item | status |
|---|---|
| resolved lexicon committed | ✓ (`c6ad95b`, validator 18/18) |
| bridge pool draft committed | ✓ (`3e49583`, `PASS_BRIDGE_DRAFT / FALLBACK_QUALIFIED`) |
| prereg draft committed | ✓ (`9d474f2`) |
| fallback decision documented | ✓ (`e63c88b`, `PROCEED_TO_PREREG_UNDER_FALLBACK_QUALIFICATION`) |
| **arm-construction config** (A/R_same/R_deranged/R_domain/S builders + seeds) | ✗ needs implementation/config |
| **generation model IDs / versions** | ✗ needs final freeze |
| **seeds / decoding params** | ✗ needs final freeze |
| **judge panel config** (allowlist + attention/repair rules) | ✗ needs final freeze |
| **scorer config** (bootstrap/Holm/verdict map params) | ✗ needs final freeze |
| **leak-scan tooling / config** | ✗ needs final freeze |
| **packet persistence format** (incl. R-beats-A sample) | ✗ needs final freeze |
| **artifact hash manifest** (signed freeze record) | ✗ needs final freeze |

Four foundation artifacts are committed; **seven run-time freeze artifacts are not yet created.**

## 5. Decision

**`NOT_READY_FOR_FREEZE_YET`.**

**Reason:** the prereg is complete enough to stand as a committed **draft**, but B1.1 **cannot freeze** until
the remaining freeze artifacts exist and are hash-bound:
- arm-construction config;
- generation model / version config;
- seeds / decoding config;
- judge-panel config;
- scorer config;
- leak-scan and packet-persistence plan;
- artifact hash manifest (signed freeze record).

Freezing before these exist would repeat the B1 freeze-coverage gap (config outside the frozen set). The
embedding-gate fork also remains open (path A preferred; path B fallback-qualified) — but that is orthogonal
to the missing run-time artifacts and does not by itself unblock freeze.

## 6. Next gate recommendation

**`B1_1_FREEZE_ARTIFACTS_SPEC`** — define **exactly** what must be frozen before any generation run: the
seven artifacts above, their formats, and the signed hash-manifest procedure (analogous to the B0 freeze
discipline, this time with the lexicon + bridge pool **inside** the freeze set). Spec only; no freeze, no
generation.

## 7. Final status block

```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
Prereg:                COMMITTED DRAFT (9d474f2)
Freeze readiness:      NOT_READY_FOR_FREEZE_YET
Bridge:                PASS_BRIDGE_DRAFT / FALLBACK_QUALIFIED
Embedding gate:        BLOCKED_DEPENDENCY_UNAVAILABLE (still owed)
Generation/scoring/judging: NO
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (`1fe5562`; A_vs_R −0.1917, A_vs_X −0.075) · Track F
`CORRECTNESS_DEGRADED`. Contrastivity / non-synonymy repair remains **necessary but not sufficient**;
**`R_deranged` remains the crux**.

**Structure, not validated meaning.** Review/decision memo only; the B1 verdict stands and Track B remains
BLOCKED.
