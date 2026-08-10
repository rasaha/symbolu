# Model Selection Experiment — Version 2 Amendment

*A controlled version amendment, not silent protocol drift. Version 1 is preserved
unchanged and permanently marked **UNRESOLVED — blocked before execution**. This
document defines Version 2, whose sole purpose is to re-bind the frozen experiment to
currently-executable model endpoints while preserving the scientific question and
methodology.*

**Status of V2: NONVIABLE in the current environment — not frozen, not executed.**
See `V2_VIABILITY_REPORT.md`. This amendment is created regardless (it is the versioning
record); V2 will only be frozen/executed once a viable execution set exists.

---

## Lineage

```
Version 1  — frozen registry: Anthropic (claude-3-5-haiku-20241022, claude-3-7-sonnet-20250219),
             OpenAI (gpt-4o, o3-mini), Bedrock (llama-3.1-70b)
   │  pre-execution gate failed (attempts 1–3): providers unreachable / credentials invalid /
   │  pinned Anthropic snapshots not available to the account. No real-model results produced.
   ▼
Version 2  — created because provider access and pinned-model availability materially changed
             (the account exposes a newer Anthropic model generation; only Anthropic is an
             executable provider here). Re-binds ONLY model endpoints; preserves the design.
```

## 1. Why Version 1 could not execute

Across three verification attempts (see `EXECUTION_ATTEMPT_REPORT.md`): OpenAI — missing
credential and proxy-denied; Bedrock — invalid AWS credential; Mistral (a supplied key,
not a V1 provider) — network-policy denied; and the **V1-pinned Anthropic snapshots
(`claude-3-5-haiku-20241022`, `claude-3-7-sonnet-20250219`) return `model_not_found`**
for this account. V1 never reached inference; its verdict is UNRESOLVED.

## 2. Constraints that remain UNCHANGED (immutable in V2)

The research hypothesis; the task corpus and dev/shadow split; routing arms A–G; the F1,
F2, and G definitions; hard governance constraints; the scoring methodology; the
selection-regret and cost-per-success definitions; the statistical tests; fixed-sequence
gatekeeping; the 3-percentage-point non-inferiority margin; the commercial thresholds
(≥15% cost / ≥20% regret vs static / 3 pp non-inferiority); spend-control logic; and the
decision-record schema. **None of these is changed by V2.**

## 3. What is being re-bound (and ONLY this)

The **capability registry's `provider_facts` bindings** — the concrete model identifiers,
provider assignments, pricing, and context/output limits — are re-pointed from V1's
unavailable snapshots to currently-executable endpoints. The registry **schema** is
unchanged; the logical model slots (a cost-oriented model, a general model, a strong
model, a long-context model, an additional distinct family) are unchanged; only the
vendor/model bound to each slot changes. Nothing else in the experiment is touched.

## 4. Why the re-binding is scientifically necessary

The hypothesis ("does a governed policy route better than simpler baselines?") is
**model-agnostic** by design — it is a claim about the *decision procedure*, not about
specific vendor models. V1's pinned snapshots are not executable in any reachable
environment, so the only way to obtain real-model evidence is to bind to executable
models. Re-binding the endpoints while freezing the entire experimental design is the
minimal change that restores executability without altering what is being tested.

## 5. Comparability RETAINED with V1

Everything that defines the experiment as a scientific test is identical: same
hypothesis, corpus, arms, policy logic, scorers, regret/cost definitions, statistical
tests, gatekeeping order, margins, and commercial thresholds. A V2 result is therefore
interpretable under the **same pre-registered design and the same decision rule** as V1
would have been. The falsification logic is unchanged.

## 6. Comparability LOST with V1

The specific model set differs, so the *operating-point spread* and any *absolute
per-model* numbers are not comparable to V1's intended models. This loss is immaterial in
practice because **V1 produced no real-model numbers to compare against** — V2 is the
first execution, not a replication. V2 must not be described as reproducing or confirming
any V1 measurement.

## 7. Did any threshold, scorer, corpus item, or statistical test change?

**No.** Thresholds, scorers, corpus items, splits, arms, policy rules, and statistical
tests are byte-for-byte identical to V1 (V1 hashes preserved in the repo). The **only**
delta is the registry's model/provider/pricing bindings. Any future unavoidable change
(e.g. an adapter for a newly-required provider) will be listed and justified separately
in the viability report and manifest, and must pass the same interface tests.

## 8. Why no observed outcome influenced this amendment

V1 executed **zero** real-model inferences and produced **zero** results, scores,
regrets, or costs. There is therefore no outcome that *could* have influenced the choice
of V2 models. The re-binding is driven **solely** by executability — which endpoints
authenticate, which model IDs the account can call, and which providers the network
policy permits — determined by free/least-cost verification, never by any performance
observation. This is what makes V2 a legitimate pre-registration amendment rather than
outcome-driven drift.

---

## Operational definition of "model family" (fixed before selection)

**A model family = a distinct pretraining lineage / base architecture** (e.g. Claude,
Gemini, GPT, Llama, Mistral). Size or tier variants of one architecture (e.g. Claude
Haiku vs Sonnet vs Opus; Gemini Flash vs Pro) count as **one** family. This is the strict
reading required by the V2 instruction ("do not satisfy the family requirement merely by
using several size variants of one architecture"). It is stricter than — and does not
override — the frozen protocol's capability-profile phrasing; the frozen protocol is
unchanged, and V2 additionally requires ≥3 distinct **architectural** families.

## V2 provider/model binding — INTENDED (pending viability)

Preferred providers are V1's (Anthropic, OpenAI, Bedrock) where accessible. In this
environment only **Anthropic** is executable, so a viable V2 requires ≥1 additional
executable provider of a distinct family. Because that is not available here (see
viability report), **no V2 registry or manifest is created and no paid pilot runs.**
Verified-executable Anthropic candidates (real inference succeeded 2026-07-23) that V2
would bind once a second provider exists:

| Logical slot | Anthropic model (executable-verified) | Role |
|---|---|---|
| cost-oriented | `claude-haiku-4-5-20251001` | fast/low-cost |
| general / strong | `claude-sonnet-4-5-20250929` | general-purpose, higher capability |

(Additional Anthropic tiers exist on the account but, per the family definition, do not
add distinct families and cannot substitute for the second-provider requirement.)
