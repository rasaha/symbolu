# C×R×S MATCH-Filter — Phase 3: Answer Audit / Post-Check Layer

> **Phase 3 does not add new ontology layers. It audits answer-frame compliance using the frozen
> C×R×S frame.** No Bhava/Guna/vrittis, no JEPA, no hidden states, no logits, no governance. The
> Phase 1 scorer (thresholds 0.20 / 0.05, grouped-R, S-gated C/R) and the Phase 2 framed prompt are
> imported **read-only** and are NOT modified.

## The Phase 3 question

> **Can C×R×S detect when an answer violates its selected semantic frame?**

NOT: *Can we force every answer through a rewrite?* Phase 3 is a **detector / classifier / explainer**.
It looks at (query, answer, frozen C×R×S trace) and emits structured findings: what kind of
frame-violation occurred, how severe it is, which domain, the textual evidence, and a plain-language
explanation. Rewriting is **optional and conservative** — only triggered on a small set of
high-confidence failure modes, and even then only *recommended*, never forced.

This is a post-check / audit layer, deliberately separate from the answer generator. It re-uses the
same deterministic, negation-aware detectors validated in Phase 2 / 2B (`rubric.asserted_domains`,
`mentioned_domains`, `has_phoneme_overreach`, `forbidden_rate`) so the audit and the eval rubric agree
by construction.

## What the auditor sees

```
audit_answer(
    query,                    # the user question
    answer,                   # the model's answer text
    csr_trace,                # frozen Phase 1 trace: primary / secondary / rejected domains
    rubric=None,              # optional rubric cfg (version-aware; defaults to v2 semantics)
    terms=None,               # dominant terms (defaults to csr_trace / query)
    alternate_true_senses=None,  # domains that are TRUE alternate senses (secondary-allowed)
    false_claims=None,        # factuality: phrases that would be factually wrong if asserted
    answer_id="",
) -> AnswerAuditResult
```

The trace can be a real `CSRMatchTrace` (Phase 1) or a plain dict fixture
`{primary_domains, secondary_domains, rejected_domains}` — the audit only reads those three lists, so
Phase 3 never needs to re-run the frame.

## Finding taxonomy

Each `AnswerAuditFinding` has a `finding_type`, a `severity`, an optional `domain`, an `evidence`
snippet, and a human-readable `explanation`.

| finding_type | severity | meaning |
|---|---|---|
| `frame_compliant` | info | answer asserts the primary frame, no leaks, no promotion, no overreach |
| `primary_frame_missing` | error | the primary domain is never positively asserted |
| `secondary_promoted_to_primary` | error | a secondary/alternate sense leads while the primary is absent |
| `rejected_domain_promoted` | critical | an irrelevant *rejected* domain is asserted as the answer frame |
| `rejected_domain_mentioned_as_refutation` | info | a rejected domain is named only to deny it ("X is *not* a fruit") — **not** a leak |
| `alternate_true_sense_allowed` | info | a true alternate sense is mentioned alongside the primary — allowed, not a violation |
| `phoneme_overreach_claim` | critical | the answer asserts sound/phonemes *prove* meaning (the one hard C×R×S taboo) |
| `factuality_suspected` | error | a registered `false_claim` is positively asserted |
| `answer_too_generic` | warning | answer is empty / too short / never mentions the queried term |

Severities map to a per-finding confidence: `critical → 0.9`, `error → 0.8`, `warning → 0.5`,
`info → 0.2`. The result's `confidence` is the **max** finding confidence (how confident we are that
*something* is wrong), and `passed` is true iff there is no finding of severity `error` or worse — so
a `warning`-only finding such as `answer_too_generic` is flagged but still *passes* (it is not a frame
violation, just a non-answer).

The `rejected_domain_promoted` finding is **context-dependent**: `critical` when the rejected domain
is the answer frame (primary absent), `error` when it merely leaks alongside a present primary.

## Conservative rewrite policy (`should_rewrite`)

Detection is cheap; rewriting is expensive and can *introduce* errors, so the rewrite gate is
deliberately narrow. `should_rewrite(result)` is **True only** when one of these holds:

- a **critical** `rejected_domain_promoted` finding, or
- a **critical** `phoneme_overreach_claim` finding, or
- a `primary_frame_missing` finding with confidence ≥ 0.75, or
- a `secondary_promoted_to_primary` finding with confidence ≥ 0.75.

Everything else — `alternate_true_sense_allowed`, `rejected_domain_mentioned_as_refutation`,
`factuality_suspected` (out of scope for a *frame* rewrite), `answer_too_generic` — is **flagged but
not rewritten**. The status string is one of `audit_pass`, `audit_warn`, `audit_rewrite_recommended`.

The design bias is toward **false negatives over false positives on rewriting**: we would rather
*not* rewrite a borderline answer than churn a good one. The eval measures `false_rewrite_rate`
(rewrites recommended on answers that should pass) and `missed_critical_failure_rate` (critical
failures we failed to flag) precisely to keep this honest.

## Optional rewrite prompt

`build_rewrite_prompt(query, answer, csr_trace, audit_result)` produces a minimal correction prompt
that names the specific findings to fix and re-states the frame. It is only consulted when
`--rewrite-mode` is `suggest` (build the prompt, attach it, do **not** call the model) or `auto`
(build it and actually rewrite). Default everywhere is **off** / `suggest` — never `auto`.

## Integration with the Phase 2 runner

`eval_framed_answers.py` gains two opt-in flags, both **off by default**:

- `--audit-answers` — run `audit_answer` on each arm's answer and report `audit_pass_rate`,
  `rewrite_recommended_rate`, `critical_findings_rate` per arm.
- `--rewrite-mode {off,suggest,auto}` (default `off`) — `suggest` attaches a rewrite prompt to
  rewrite-recommended answers; `auto` performs one rewrite. Neither changes the frozen frame or the
  Phase 2 scoring of the original arms.

## Pass/fail labels (`eval_answer_audit.py`)

The audit is scored against a pre-registered fixture dataset (`eval_data/answer_audit_eval.jsonl`)
with gold `expected_findings`, `expected_passed`, `expected_needs_rewrite`. The decision label is one
of:

| label | condition |
|---|---|
| `PHASE3_ANSWER_AUDIT_PASS` | high finding-type F1, high rewrite precision **and** recall, low false-rewrite rate, **zero** missed critical failures |
| `PHASE3_AUDIT_WEAK_REWRITE_TOO_AGGRESSIVE` | detection good but `false_rewrite_rate` over budget (rewrites good answers) |
| `PHASE3_AUDIT_MISSES_CRITICAL_FAILURES` | `missed_critical_failure_rate` > 0 (a critical frame violation slipped through) |
| `PHASE3_AUDIT_NEEDS_HUMAN_REVIEW` | metrics in the gray zone — detector works but not certifiable deterministically |
| `PHASE3_AUDIT_NO_VALUE` | the auditor adds nothing over a trivial baseline (no discrimination) |

`PHASE3_AUDIT_MISSES_CRITICAL_FAILURES` dominates: a single missed critical (a promoted rejected
domain or a phoneme-overreach claim that the auditor passed) blocks `PASS` regardless of the other
metrics, because the whole point of the layer is to catch exactly those.

## Hard boundaries (unchanged from Phase 1/2)

- No new ontology / Bhava / Guna / vrittis / JEPA / hidden-state / logit / governance machinery.
- The frozen Phase 1 thresholds, grouped-R, and S-gated C/R are **not** touched.
- The Phase 2 framed prompt is **not** modified (any rewrite prompt is a new, clearly-labeled
  Phase 3 artifact, not an edit to the frozen prompt).
- The auditor is **deterministic** and needs no LLM; an LLM is only ever used to *perform* a rewrite
  under `--rewrite-mode auto`, never to detect.
