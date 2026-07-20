# Judge Protocol (v0.1)

Source: `judges.py`. Three specialized judges; **no majority voting**.

> **Honest substitution.** The brief specifies LLM judges. LLM judges are
> non-deterministic and unavailable in this offline, reproducibility-gated setting,
> so the judges here are **deterministic, span-grounded rule engines** — stand-ins
> for what would be LLM judges in a resolver-connected deployment. This is the
> single largest deviation from the brief and is declared in the preregistration.
> It makes "Judge determinism passes" and "two deterministic runs match" meaningful
> rather than impossible.

---

## 1. Judge A — evidence advocate

For each predicate, searches the **cited** spans for support. Marks a predicate
`supported` (and `explicit` when the support is an explicit, non-negated assertion
of the exact relation in the correct direction). Emits `supporting_spans` and
`supporting_document_ids`.

## 2. Judge B — evidence challenger (independent)

Independently tries to **falsify** the claim. Scans **all** documents (a challenger
is not limited to the proposer's citations) for: an explicit negation
(`negates`), a contrary superseding relation (`contradicts`), or an
exclusive reverse-direction assertion (`exclusive_direction`). Records
`contradicted` predicates (with `explicit`), `contradicting_spans`, and the set of
predicates with **no** supporting evidence (`missing`).

**Independence is structural:** Judge B does not receive Judge A's trace. (Judge B
recomputes an independent advocate pass internally only to compute its own
"missing" set; it never reads A's returned conclusion.)

## 3. Deterministic pre-judge gate

Before Judge C, deterministic checks resolve legality, schema, duplicate,
direction well-formedness, document existence, and citation validity
(`DETERMINISTIC_VALIDATION.md`). Only **unresolved semantic disagreements** reach
Judge C.

## 4. Judge C — adjudicator (runs only on disagreement)

A disagreement is a predicate where **A found support and B found contradiction**.
Judge C receives the claim, both traces, and the deterministic result, and resolves
**each disputed predicate on evidence**, not by preference:

| A explicit | B explicit | Judge C verdict |
|---|---|---|
| yes | yes | **UNKNOWN** (manual review) — equally-explicit conflict |
| no | yes | CONTRADICTED |
| yes | no | SUPPORTED |
| no | no | CONTRADICTED (conservative) |

Judge C resolves predicates; it does not pick a "preferred explanation."

## 5. Measured judge behavior on the corpus (from the run)

- Judge B is what catches contradictions: **V2 (advocate only) accepts 12
  claims that V4 rejects** (`ABLATION_RESULTS.md`).
- Judge C ran on exactly the **4** equally-explicit direction-conflict cases and
  routed them to UNKNOWN; without it, V3 accepts those 4 as SUPPORTED (false
  acceptances). See `AGREEMENT_REPORT.md`.
