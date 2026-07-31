# Composite Capability & Sequence-Risk Analyzer — Specification

**Status:** design + reference implementation for an **advisory** evidence
producer that plugs into the deterministic Action Gate
([`ACTION_GATE_SPECIFICATION.md`](ACTION_GATE_SPECIFICATION.md)).

> **Product statement.** ActionGate controls individual actions; the sequence-risk
> analyzer detects when individually acceptable actions collectively assemble a
> prohibited or high-risk capability.

**What this version is:** deterministic; recipe- and ontology-driven; advisory,
evidence-producing; limited to *encoded* capability patterns.
**What it is not:** a general intent-understanding system; a learned anomaly
detector; a system that reconstructs arbitrary criminal narratives or infers
motive. It does not "understand crime". It identifies when *linked, individually
admissible* actions accumulate the fragments of a *versioned, encoded* recipe.

The physical firearm example (steel rod + piston + trigger → firearm) is retained
**only as a synthetic illustration** that the engine is domain-agnostic. The
product target is enterprise AI-agent and infrastructure workflows.

Reference implementation: [`composite_threat_detector/`](composite_threat_detector/).
Conformance keywords **MUST / MUST NOT / SHOULD / MAY** are RFC-2119.

---

## 1. Problem: individually-admissible, jointly-dangerous

The Action Gate decides **one action at a time** and, for the same envelope +
policy + evidence, always returns the same one of six outcomes. That determinism
is its strength and, for a patient adversary, its gap: a prohibited *composite*
can be decomposed into steps that each clear the per-action gate. Within one case
(and often across sessions and actors), a sequence of admissible actions —
obtain a credential, reach protected data, open an outbound path — can assemble a
data-exfiltration capability that no single action reveals.

The Action Gate reserves `correlation_id` / `sequence_id` "for structuring
detection" ([spec §2](ACTION_GATE_SPECIFICATION.md), fields 23–24). This analyzer
is that layer — but it does **not** use `correlation_id` as the sole grouping key
(§4).

---

## 2. Authority boundary — advisory, escalate-only

The analyzer's output alphabet is exactly **`OBSERVE`**, **`ESCALATE`**, and
**`UNAVAILABLE`**. It **MUST NOT** emit `ALLOW`, `AUTHORIZE`, `DENY`, `BLOCK`, or
`EXECUTE`. It is behavioral evidence in the sense of
[Action Gate §3](ACTION_GATE_SPECIFICATION.md) — *ADVISORY, OPTIONAL* — governed
by the **non-compensatory** invariant: it may only move a decision toward *more*
assurance.

**Policy integration contract.** An authoritative ActionGate or workflow policy
**MAY** convert an analyzer `ESCALATE` into `HOLD_FOR_REVIEW`, `BLOCK`, or another
configured consequence (see `policy.py`). The analyzer remains advisory; **policy
owns the binding outcome**.

**Removal invariant.** Removing or disabling the analyzer **MUST NOT** increase
authority or convert a denied action into an allowed one. With no finding, policy
returns `NO_CONSEQUENCE` and the per-action gate decision stands unchanged. The
analyzer can only ever *add* a hold/block on top of an already-admissible action.

`UNAVAILABLE` is fail-loud: emitted when the analyzer cannot evaluate faithfully
(e.g. bounded-state exhaustion, §13). It is never silent evidence loss.

---

## 3. State model — multi-timescale, no silent windowing

**A short recent-event window does NOT prevent low-and-slow attacks — it can help
them,** by letting an early part scroll out of view before the last part lands.
The analyzer therefore keeps state at multiple timescales:

1. **Short operational window** — recent raw-event bookkeeping (ordering,
   diagnostics), bounded in count.
2. **Medium case history** — the assembly's fragment record over the workflow.
3. **Persistent capability ledger** — `PERSISTENT` fragments (a credential
   obtained, a privilege granted, a foothold) survive until explicitly revoked.
4. **Decaying evidence** — `TRANSIENT` fragments lose weight smoothly
   (`0.5 ** (elapsed / half_life)`); below a floor they are retained as `DECAYED`
   (recorded, non-contributing), **not deleted**.
5. **Explicit retention/expiry** — the analyzer distinguishes *event expiry*,
   *evidence decay*, *case closure*, and *administrative reset*. An early fragment
   **MUST NOT** disappear silently because a fixed event-count window was exceeded.

All aging is computed against an **evaluation time supplied as event data** (epoch
seconds when timestamps are present, else the monotonic step position) — never
wall-clock — so replay is exact.

---

## 4. Trace identity vs. threat grouping

`correlation_id` (one execution/trace flow) and `sequence_id` (ordered position)
are preserved, but the **assembly boundary** is a deterministic `assembly_key`
derived from configurable *entity* identifiers, not the correlation id. This
supports: one sequence across multiple correlation IDs; several actors
contributing to one capability; human + agent actions in one case; multiple
sessions in one assembly; and interleaved unrelated workflows without
contamination.

Key derivation is `assembly_key = digest(tenant_id, key_spec, {dim: value})` over
an :class:`AssemblyKeySpec` (a versioned set of entity dimensions). Because keys
are always tenant-scoped, cross-tenant linkage is impossible by construction.
Shipped specs: `by_actor`, `by_case`, `by_target`, `by_actor_target`, and
`by_correlation` (legacy/synthetic only — §4 forbids correlation as the sole
*default* boundary). Schema: `ctd.linkage/1.0.0` (see
[`composite_threat_detector/LINKAGE_SCHEMA.md`](composite_threat_detector/LINKAGE_SCHEMA.md)).

---

## 5. Entity-linkage model

A deterministic layer groups events by **explicit identifiers**, never inferred
intent. It normalizes entity identifiers (`actor`, `agent`, `workflow`,
`target_family`, `credential`, `dataset`, `destination`, `device`, `tool`,
`environment`), preserves tenant isolation, records *which* identifiers caused a
link, reports a deterministic linkage confidence (`EXACT` / `PARTIAL` /
`AMBIGUOUS` — a rule output, not a probability), supports one event contributing
to multiple candidate assemblies (one per configured spec), and rejects ambiguous
cross-tenant linkage. No embeddings and no LLM enter this path.

---

## 6. Recipe model

Recipes are versioned data (`recipe_id@version`). Fragment **count is necessary
but never sufficient** — a sequence must not escalate merely because it contains
the same nouns as a prohibited capability. Each recipe carries: required &
optional fragments; mutually-exclusive fragment sets; ordering constraints;
temporal `max_assembly_gap` / pair gaps; actor scope (ANY / SAME / MULTI);
resource scope; completion / escalation / observe thresholds; required
corroboration and minimum-optional counts; benign-use exclusions; severity;
recommended (advisory) consequence; and a concise explanation template. Schema:
[`composite_threat_detector/RECIPE_SCHEMA.md`](composite_threat_detector/RECIPE_SCHEMA.md).

---

## 7. Benign-explanation handling

A benign explanation **MUST NOT** automatically suppress risk. It may qualify
(downgrade `ESCALATE` → `OBSERVE`) **only** when backed by explicit, scope-matched
evidence — an approved change ticket, authorized workflow id, named approver,
unexpired time-bounded approval, matching target scope, and valid policy version
where required. The analyzer records **both** the threat evidence and the benign
evidence, and every finding states whether the threat interpretation
`THREAT_DOMINATES`, is `NEUTRALIZED`, or remains `AMBIGUOUS`.

---

## 8. Minimal-completion analysis (advisory extension)

For a partially-matched recipe the analyzer reports the missing required
fragments, the minimal remaining set, which next-fragments would materially
reduce the distance, and whether ordering/entity/temporal constraints already
make completion impossible. This is a lookahead over *known encoded* recipes.

> The analyzer identifies which capability fragments would complete a known recipe
> if they appeared next.

It does **not** predict attacker intent and is **not** claimed to be novel (§14).
Output remains advisory evidence.

---

## 9. Finding semantics

Each finding carries: finding id (deterministic digest); tenant id; assembly key;
key spec; related correlation ids and event ids; recipe id + version; present and
missing fragments (with provenance); ordering status; entity-link evidence;
benign-context evidence; completion score; minimal-completion analysis;
escalation reason; severity; recommended consequence; first-seen / last-updated
positions; state-expiry info; and the advisory signal. Text is concise and
non-dramatic, e.g.:

> Individually admissible actions have accumulated the credential-access,
> protected-data-access, and outbound-transfer fragments required by the versioned
> data-exfiltration recipe.

---

## 10. Validation (detection AND non-detection)

The test suite (`tests/`) proves both firing and non-firing across: a true
harmful sequence; a benign look-alike; an authorized security test; out-of-order
events; long-and-slow; cross-session; multi-actor; human + agent; interleaved
unrelated workflows; duplicate and idempotency-retried events; same fragments
across tenants; an unknown (unencoded) threat; renamed tools with equivalent
capability metadata; expired vs. valid approvals; ambiguous linkage; analyzer
unavailable (bounded state); recipe-version change mid-case; and policy converting
an escalation to `HOLD_FOR_REVIEW`. See §12 for the evaluation plan.

---

## 11. Integrity / anti-confounder reporting

Every run maintains a `RunReport` (`analyzer_enabled`, ontology + recipe
versions, key specs, timescale unit, events ingested, fragments extracted, events
linked, ambiguous links, assemblies/correlations, duplicates & retries
suppressed, capabilities revoked, unmapped capabilities, unavailable events,
findings & escalations). **No silent fallback may produce a clean result** — an
ambiguous link, an unmapped capability, a decayed fragment, or a bounded-state
breach is always counted and surfaced.

---

## 12. Evaluation

Measurable metrics and methodology are in
[`COMPOSITE_SEQUENCE_RISK_EVALUATION_PLAN.md`](COMPOSITE_SEQUENCE_RISK_EVALUATION_PLAN.md).
Population rates (true-positive, false-escalation, miss, lead time, detection
rates, runtime) require a labeled corpus that does not exist in-repo and are
reported as **`NOT RUN`**. Determinism, dedup sensitivity, bounded-state memory,
mean-events-before-escalation, and explanation completeness are measured on the
*illustrative* scenarios and are explicitly **not** a benchmark.

---

## 13. Deterministic, bounded operation

The authoritative analyzer is deterministic, replayable from an event log, and
has no wall-clock dependence in replay, no randomness, no network calls, and no
LLM dependency. Per-event processing is bounded; tenant state is bounded by
`StateLimits`. On limit breach the analyzer emits `UNAVAILABLE` (fail-loud) —
never silent evidence loss.

---

## 14. Novelty & IP

Sequence-based threat detection, attack graphs, complex-event processing,
provenance analysis, and multi-stage attack reconstruction have **substantial
prior art**. Recipe matching, missing-fragment calculation, attack-path
reachability, and escalate-only evidence are **not** claimed as established
novelty.

> Potential differentiation may lie in the exact composition of deterministic
> sequence-risk evidence with ActionGate's canonical exact-action identity,
> non-compensatory policy semantics, replayability, and binding-authority
> separation. Patent novelty has not been established and requires professional
> prior-art review.

No patent claims are drafted in this phase.

---

## 15. Reference implementation

`composite_threat_detector/` — Python 3.11+, standard library only.

```bash
cd cyber_security/composite_threat_detector
python3 -m pytest -q                                          # test suite
python3 -m composite_threat_detector.cli demo exfiltration    # harmful → ESCALATE
python3 -m composite_threat_detector.cli demo benign          # look-alike → no escalate
python3 -m composite_threat_detector.cli demo firearm         # synthetic illustration
python3 -m composite_threat_detector.cli eval                 # metrics (NOT RUN honest)
python3 -m composite_threat_detector.cli run events.jsonl --spec by_case --spec by_actor --policy
```

Exit code is non-zero when any `ESCALATE`/`UNAVAILABLE` finding is produced. See
also `RECIPE_SCHEMA.md`, `LINKAGE_SCHEMA.md`, and `MIGRATION_NOTES.md` in the
package directory.
