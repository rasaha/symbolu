# ACTIONGATE_REMEDIATION_DESIGN — deterministic remediation guidance (vNext)

Status: **DESIGN ONLY. No implementation in this milestone.**
Grounded in the reference gate `action_gate_reference/action_gate_ref/` (gate.py,
policy.py, projection.py, evidence.py, approval.py, audit.py, errors.py, schema.py).

## 0. Thesis

The gate already computes, deterministically, *why* an action did not ALLOW: it walks
every effect of every rule for the operation and records the winning (most-restrictive)
tier as `dispositive_rules`. Remediation guidance is a **read-only re-projection of that
same evaluation** — it tells a caller which inputs would need to change for a *fresh*
action to clear, without changing this action's decision.

Three invariants govern the entire design:

- **I1 — Decision purity.** The decision remains `D(envelope, signed_policy, evidence,
  approvals, state)`. Remediation is computed *after* `D` from the identical inputs and is
  never fed back into `D`. Removing the remediation layer must not change a single outcome.
- **I2 — Non-compensatory dominance is preserved.** The outcome is still the minimum-severity
  tier over all effects (`gate._SEVERITY`: DENY 0 < REQUEST_MORE_EVIDENCE 2 <
  SIMULATE_AND_RETRY 3 < ESCALATE_TO_HUMAN 4 < ALLOW_WITH_CONSTRAINTS 5 < ALLOW 6).
  Remediation never implies that satisfying one condition alone yields ALLOW when a
  more-restrictive unmet condition co-exists.
- **I3 — DENY is terminal and never re-labelled retryable.** A cause that resolved to DENY
  (hard invariant, FORBID/REQUIRE, present-but-invalid approval, hard `MUST_HAVE`) is
  emitted with remediation class `TERMINAL`/`IMPOSSIBLE` and carries **no** retry path.
  Remediation may describe *what is wrong*; it may never describe *how to make a DENY
  become ALLOW*.

LLMs stay entirely outside the trust boundary: they may *read* remediation and propose a
new action, but the new action is re-evaluated from scratch by the same pure `D`.

## 1. `required_changes[]` — should the gate emit it? (Design Q1)

**Yes.** Every non-ALLOW outcome in `gate.evaluate` already knows the exact unmet operator
(`op`, its `rule_id`, and the missing datum — evidence `kind`, simulation `fidelity`,
`approver_policy`, a `MAX_*` threshold and the offending `fact`). Today the evaluator keeps
only the winning tier and discards the operator detail. `required_changes[]` is that detail,
surfaced.

Derivation is a pure function of already-computed values:

```
required_changes[] = f(dispositive effects at the winning tier,
                       envelope, signed_policy, evidence, approvals, state)
```

Each entry names one unmet condition and the *class* of change that would let a **new**
action satisfy it — with no promise that it alone yields ALLOW (I2). The full field schema,
reason codes, and per-operator examples are in
`ACTIONGATE_REQUIRED_CHANGES_SCHEMA.md`. Summary of an entry:

- `condition_id` — stable id of the unmet check (rule id + operator, e.g. `R2:MUST_HAVE`).
- `operator` — the effect op (`MUST_HAVE`, `REQUIRE_SIMULATION`, `REQUIRE_APPROVER`, …).
- `remediation_class` — from the retry matrix (`RETRYABLE_BY_EVIDENCE`,
  `…_BY_SIMULATION`, `…_BY_ACTION_MODIFICATION`, `HUMAN_ONLY`, `TERMINAL`, `IMPOSSIBLE`).
- `required` — the machine-readable target (evidence `kind`; `min_fidelity`;
  `approver_policy` + count; threshold + current value; the boolean fact to clear).
- `binding` — the `action_hash` this evaluation was against, so a caller understands that
  any modification produces a *different* action_hash and re-binds everything (see §6 of
  `ACTIONGATE_RETRY_ARCHITECTURE.md`).
- `severity_tier` — the outcome tier this condition maps to (so the caller sees dominance).

Because it is a re-derivation of inputs already bound into `action_hash`, `policy_hash`, and
`dispositive_rules`, `required_changes[]` introduces **no new trust-bearing state** and does
not need to be added to the hashed audit payload (see §3 and the compatibility review).

## 2. `all_unmet_conditions[]` — full failure reporting (Design Q2)

Today the response exposes only the **dispositive** tier. A caller that fixes the reported
REQUEST_MORE_EVIDENCE item may still be blocked by a co-present ESCALATE_TO_HUMAN item it
never saw — wasting a retry and, worse, turning the gate into a slow oracle probed one layer
at a time. We evaluate exposing `all_unmet_conditions[]` (every unmet effect across all
tiers) while keeping a single dispositive record.

- **Determinism.** Fully deterministic. `gate.evaluate` already visits every effect; today
  it only *keeps* the minimum-severity one. Collecting all unmet effects is the same walk
  with nothing discarded — identical inputs, identical order, identical output. No new logic
  affects the decision.
- **Complexity.** Negligible runtime cost (same loop). Response size grows from one tier to
  ≤ (#effects for the operation); the reference rules have ≤ 5 effects per operation, so
  this is small and bounded. The state machine, precedence, and outcome are untouched.
- **Compatibility.** Purely additive optional field (see `ACTIONGATE_COMPATIBILITY_REVIEW.md`).
  `dispositive_rules` remains the single, unchanged audit anchor; `all_unmet_conditions[]`
  is supplementary and, like `required_changes[]`, is re-derivable and therefore excluded
  from the hashed audit payload.
- **Audit impact.** Keep exactly one dispositive record per decision (`dispositive_rules`,
  already hashed by `audit.build_audit_record`). `all_unmet_conditions[]` is *reporting*, not
  *adjudication*: it must never be interpreted as multiple co-equal decisions. The audit
  chain hash is unchanged because the audit payload schema is unchanged.
- **Security caveat.** Full failure reporting is the strongest policy oracle in this design;
  it is therefore gated by disclosure level (§4 of the threat model) — `FULL` only, redacted
  or absent at `STANDARD`/`MINIMAL`/`NONE`.

**Recommendation:** expose `all_unmet_conditions[]`, disclosure-gated, with `dispositive_rules`
retained verbatim as the single audit anchor.

## 3. Determinism & audit relationship (why this is safe to add)

`required_changes[]` and `all_unmet_conditions[]` are both **functions of inputs already
committed to the audit record**: the envelope (via `action_hash`), the policy (via
`policy_hash`), the evidence/approval hashes, and the dispositive rules. Given an audit
record and the signed policy, any verifier can *recompute* them offline and get the same
bytes. Therefore:

- they add no new authority and need not be signed or chained;
- the existing `audit.build_audit_record` payload — and thus every existing
  `audit_record_hash` and chain head — is **unchanged**;
- the conformance vectors, which pin canonical bytes and `action_hash`/digest values and
  test binding/canonicalization invariants, still pass unchanged (remediation touches none).

This is the crux of the "add guidance without weakening guarantees" claim: guidance is a
**pure view** over already-adjudicated, already-hashed facts.

## 4. Seventh outcome? (Design Q9) — **Recommendation A: no new outcome, payload enrichment only**

We evaluated adding `REQUEST_MODIFICATION` / `REQUEST_CHANGES` as a seventh outcome versus
keeping the six frozen outcomes and enriching the payload.

**Recommendation: A — keep the six outcomes; add remediation as payload only.**

Rigorous justification:

1. **The six outcomes already partition the remediation space.** Every unmet operator maps
   onto an existing tier: missing evidence → REQUEST_MORE_EVIDENCE; missing simulation →
   SIMULATE_AND_RETRY; missing approver → ESCALATE_TO_HUMAN; threshold/irreversibility
   exceeded → ESCALATE_TO_HUMAN; forbidden/hard/self-grant → DENY. "Modification" is not a
   new *decision*; it is a *property of a required change* (`RETRYABLE_BY_ACTION_MODIFICATION`),
   already expressible in `required_changes[]`.
2. **A seventh outcome would change decision semantics — forbidden by the brief.** The
   operators that suggest "modify" (`MAX_SCOPE`, `MAX_COST`, `MAX_BLAST_RADIUS`,
   `MAX_IRREVERSIBILITY`) currently resolve to **ESCALATE_TO_HUMAN** (`gate.evaluate`).
   Re-pointing them to `REQUEST_MODIFICATION` would *soften* a human-escalation into a
   self-service retry — exactly the "silently convert a stricter outcome into retryable"
   failure mode we must avoid. Keeping them at ESCALATE and annotating "a smaller-scope
   *new* action would avoid this rule" preserves the decision while still guiding.
3. **It would break frozen surfaces.** The outcome set is enumerated in the schema, the
   state machine `OUTCOME_TO_STATE`, the conformance vectors, and every SDK/CLI/MCP switch.
   A seventh value is a **major** compatibility break (see compatibility review) for zero
   decision-semantic gain.
4. **Non-compensatory clarity.** With six outcomes the dispositive tier is unambiguous.
   A "modification" outcome would compete with DENY/ESCALATE at the same action and muddy
   which tier is dispositive; annotation avoids that entirely.

If a future major version ever reconsiders this, the safest form is still additive
(a distinct terminal state that never relaxes an existing DENY/ESCALATE) — but this
milestone recommends **A**.

## 5. Answers to the milestone's explicit conclusion questions

1. **Is `required_changes[]` worth implementing?** — **Yes.** It is a deterministic,
   audit-neutral, additive re-projection of the evaluation the gate already performs; it
   materially reduces blind retries and enables an external planner, at no cost to decision
   purity. Ship it behind disclosure control.
2. **Should `all_unmet_conditions[]` be exposed?** — **Yes, disclosure-gated**, with
   `dispositive_rules` retained as the single audit anchor. It is deterministic and additive;
   its only risk is oracle leakage, which the disclosure levels contain.
3. **Should the current six outcomes remain unchanged?** — **Yes.** They already cover the
   remediation space; changing them would alter decision semantics and break frozen surfaces.
4. **Is a seventh outcome justified?** — **No.** Recommendation **A** (payload enrichment).
   Modification-retryability is a property of a required change, not a new decision.
5. **What is the safest roadmap?** — The phased, additive, disclosure-defaulted rollout in
   `ACTIONGATE_REMEDIATION_ROADMAP.md`: derive-internally → expose `required_changes[]`
   additively at `STANDARD` → add retry governance/accounting → expose the external planner
   interface — each phase gated on conformance-vector and audit-hash invariance.

## 6. Document map

- `ACTIONGATE_REQUIRED_CHANGES_SCHEMA.md` — concrete schema, reason codes, per-operator examples.
- `ACTIONGATE_RETRY_ARCHITECTURE.md` — retry classification matrix (Q3), retry governance
  (Q5), action-hash evolution & replay-impossibility (Q6), external planner sequence (Q10).
- `ACTIONGATE_THREAT_MODEL_REMEDIATION.md` — disclosure levels (Q4), new attack surfaces (Q7).
- `ACTIONGATE_COMPATIBILITY_REVIEW.md` — SDK/CLI/MCP/schema/conformance/versioning (Q8).
- `ACTIONGATE_REMEDIATION_ROADMAP.md` — phased plan + the five conclusion answers.
