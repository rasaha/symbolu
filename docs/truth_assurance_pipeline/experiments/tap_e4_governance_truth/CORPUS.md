# TAP-E4 — Corpus

New, independently authored governance corpus: **30 cases / 15 families / 26 evidence
units**, split **dev 15 / eval 15** (one case per family per split). No upstream gold is
reused as governance gold.

## Construction

Each case is authored as a `Situation` plus one or more `PolicySpec` candidate authorities.
From the specs the builders synthesize the real upstream structures:

- a TAP-E2 **`RetrievalRecord`** — one frozen `EvidenceUnit` per spec, carrying the
  `DocumentType` + `AuthorityLevel` that fix the candidate's governance tier;
- a TAP-E3 **`RelationshipRecord`** — one governance `RelationshipAssertion` per spec
  (`GOVERNS`/`REQUIRES`/…) with every governance attribute placed in the assertion `scope`
  map (`jurisdiction`, `user_role`, `environment`, `version`, `value`, `tier`, `emergency`),
  plus `SUPERSEDES` and `EXEMPTS` assertions.

The relationship inputs are authored to be **already-perfect** (upstream confidence 1.0):
this study evaluates the **governance layer**, not upstream extraction. The intent is built
by the frozen TAP-E1 layer from the case's request text.

## Ground truth

Each case declares its `expected_authority` (or `None`), `expected_status`,
`expected_conflicts`, and `expected_gaps`. Each candidate `PolicySpec` carries a
`disqualifier` (`expired` / `superseded` / `draft` / `wrong_jurisdiction` / `out_of_scope`
/ `future` / `""`) and a `gold_winner` flag. The disqualifiers are what let the metrics
detect **critical failures independently**: e.g. `EXPIRED_POLICY_SELECTED` fires iff the
layer selects a candidate whose gold disqualifier is `expired`, regardless of the accuracy
numbers.

## Families (15)

| Family | Tests | Adversarial trap |
|---|---|---|
| basic | single applicable authority governs | — |
| jurisdiction | only the in-jurisdiction authority governs | out-of-jurisdiction candidate ranked first by name |
| scope | only the matching-role authority governs | wrong-role candidate ranked first by name |
| expired | an expired authority is never selected | expired candidate outranks by name |
| superseded | a superseded authority is never selected | `SUPERSEDES` from a lower-name successor |
| future | a not-yet-effective authority is never selected today | future candidate outranks by name |
| version | the most recent version governs | higher version has the *lower* name |
| draft | a draft is never selectable even if it appears first | draft listed first |
| customer_override | a contract overrides an equal-tier corporate policy | policy outranks the contract by name |
| emergency_override | an emergency procedure overrides the normal SOP | normal SOP outranks by name |
| law_supremacy | a law governs; a contract may not override it | contract listed first |
| exception | an exempted role is not governed by the general obligation | exemption must be honored |
| conflict | two equal-precedence authorities, incompatible obligations | must be surfaced, not resolved |
| no_governing | the only candidate does not apply | must report a gap, not fabricate |
| upstream_gap | a governing authority resolves, but an upstream gap is preserved | gap must survive downstream |

The name-ordering traps are deliberate: a naive baseline that tie-breaks by tier-then-name
selects the wrong candidate, so each rung of the A–F ladder is genuinely exercised. The full
set covers every adversarial category the spec requires: superseded, overlapping
jurisdiction, conflicting contracts, temporary exceptions, historical/future-effective,
draft-vs-approved, regional override, customer override, emergency override.

## Splits and locking

`dev` is used for configuration selection; `eval` is a **content-hash locked development
evaluation** (`eval_inputs_hash = c28e23f3…`, `n_eval = 15`). The eval inputs were inspected
during iterative engineering — a locked development set, **not an untouched or blind
holdout** (see [LEAKAGE_AUDIT](LEAKAGE_AUDIT.md)). The public `loader.py` exposes only the
situation + candidate names, never the gold.
