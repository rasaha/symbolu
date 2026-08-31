# Bounded Governed Inference Natural-Artifact Shadow Pilot — Scope (Phase 1)

*This pilot begins where the completed **Customer Shadow Pilot Readiness** track ended (decision:
READY FOR BOUNDED CUSTOMER SHADOW PILOT, scoped). It does **not** re-run that decision. Its single
research question is whether the governed inference runtime remains **safe, useful, auditable, and
understandable** when applied to **naturally occurring artifacts** that were never designed for its
structured test corpora.*

## Research question (not a readiness claim)

> Does the governed inference runtime remain safe, useful, auditable, and understandable when applied
> to naturally occurring artifacts that were not designed for its test corpora?

The objective is **not** to prove readiness. It is to determine, empirically and falsifiably, whether:

1. structured-corpus results **transfer** to natural artifacts,
2. natural language introduces **new failure modes** the structured corpora never surfaced,
3. the **native ActionGate semantics** survive end-to-end without collapse, and
4. whether the evidence supports proceeding to a **single-customer external shadow pilot**.

A defensible outcome of this pilot is **NOT ENOUGH EVIDENCE** or **DO NOT PROCEED**. Those are
successes of the method, not failures.

## Pilot mode (all conditions bind simultaneously)

- **Shadow-only** — every disposition is a `WOULD_*` observation; nothing is enforced.
- **Read-only** — all completed components and the customer-shadow-readiness package are consumed
  read-only; no frozen logic, corpus, threshold, freeze manifest, or outcome-bearing artifact is
  rebuilt, modified, or re-evaluated.
- **Non-enforcing** — no external action is ever executed.
- **No autonomous action** — the runtime proposes; a human reviews.
- **Single-tenant by default.**
- **De-identified / redacted** inputs only.
- **Time-, volume-, and use-case-bounded** (see limits below).
- **Fully audited** — every case yields a replayable, minimized, redacted trace.
- **Human-reviewed** — escalations route to a tenant-scoped review queue; no silent override.
- **Immediately stoppable** — pilot-wide and per-tenant kill switches, checked first.

## Eligible first-pilot use cases (advisory / review only)

Enterprise policy interpretation · technical-support review · software-engineering recommendation
review · cybersecurity advisory review · compliance summary review · contract-summary review ·
procurement-policy review · IT operations guidance · customer-communication quality review.

Every eligible use case is **advisory or review**: the runtime comments on or classifies existing
text. It never takes an action in the world.

## Excluded use cases (hard exclusions — never in scope)

Clinical / prescribing · financial transactions / trading · account-permission changes · irreversible
deletion · employment decisions · legal determinations · regulated automation · autonomous security
response · any processing of PII or otherwise sensitive personal data.

An artifact that can only be interpreted as belonging to an excluded use case is rejected at intake
and never reaches the runtime.

## Eligible vs prohibited data

- **Eligible:** repository-contained real artifacts where permitted — natural documentation,
  docstrings, comments, and equivalent non-sensitive text that already exists in this repository and
  was **not authored for a governance corpus**. De-identified and redacted before use.
- **Prohibited:** PII / sensitive personal data, unclassified data, secrets/credentials, anything an
  intake classifier cannot positively clear, and any artifact whose provenance is unknown. Prohibited
  or unclassified data fails closed at intake.

## Bounded limits (binding)

| Limit | Value | Rationale |
|---|---|---|
| Tenants | 1 (single-tenant by default) | isolation surface minimized |
| Corpus size | natural artifacts only; **target ≥ 200**, else report actual count | honest evidence base |
| Duration | bounded, single execution window | no open-ended running |
| Volume | bounded by the frozen natural corpus; no live/streaming intake | reproducibility |
| Risk | advisory/review use cases only; no enforcing path exists | no world-effect |
| Providers | no unrestricted providers; no unrestricted web retrieval; no live model calls | determinism + safety |

## Reviewer requirements

- A tenant-scoped human reviewer holds `shadow:review` scope and can resolve escalations **only** with
  an explicit reason code — **no silent override** (inherited, read-only, from
  `customer_shadow_readiness/human_review.py`).
- Cross-tenant review is denied by construction.
- Reviewer disagreement/override on real cases is a **measured pilot signal**, not a control the pilot
  may tune away.

## Stop conditions (any one halts the pilot)

Any serious **safety, privacy, isolation, audit, or control** failure stops the pilot immediately.
Concretely (Phase 9 formalizes and tests these):

1. Any **unsafe disagreement** — the runtime would permit what ground truth marks unsafe.
2. Any **semantic loss in a safety-relevant native ActionGate outcome** (a native-vocabulary blocker).
3. Any **cross-tenant leak** or isolation breach.
4. Any **audit/replay failure** — a case that cannot be reproduced from its trace.
5. Any **privacy failure** — prohibited/unredacted data reaching the runtime.
6. Any **kill-switch or control failure** — a control that does not fail closed.

A stop condition that fires is a **pilot blocker** and is reported as such; it is never suppressed,
tuned around, or excluded from the final set.

## Deletion timeline

Natural-artifact inputs and derived traces are tenant-scoped and subject to the inherited retention /
right-to-erasure controls (`customer_shadow_readiness/data_controls.py`, read-only). On pilot
completion or any privacy stop condition, tenant data is deletable in one tenant-scoped operation;
exports are minimized and redacted.

## Provider / retrieval restrictions (binding)

- No calls to unrestricted providers.
- No unrestricted web retrieval.
- No live model calls in the decision path; the runtime's governance stages are deterministic and
  stdlib-only.

## No-enforcement guarantee

The pilot API's `enforced` field is `False` by construction. There is **no** enforcing path in this
pilot: no external action executes, no account/permission changes, no deletion, no autonomous
response. The native ActionGate is invoked **read-only** to observe its decision; its decision is
never acted upon.

## Explicit non-claims

- This pilot does **not** claim production readiness.
- This pilot does **not** onboard any real customer, nor onboard a customer automatically.
- This pilot does **not** enable enforcement.
- This pilot does **not** generate a new synthetic corpus to present as primary pilot evidence.
