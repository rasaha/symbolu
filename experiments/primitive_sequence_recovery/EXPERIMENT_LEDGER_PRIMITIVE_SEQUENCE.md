# Experiment Ledger — Primitive-Sequence Recovery (Tracks C, D0/D, E-flat, F, G)

**Read-only ledger. Nothing rerun, rescored, or reinterpreted.** `frozen/manifest.json` NOT_READY; base run manifests `run_enabled:false` / `NOT_APPROVED`; Stage A untouched; four-sphere JSON parked; **Track B BLOCKED**; no `ONTOLOGICAL_SIGNAL`, no Sanskrit privilege. Every result below is exploratory triage, English/LLM-mediated, not validation.

## Scoreboard

| Track | What it tested | Status | Result label | Supports / blocks Track B |
|---|---|---|---|---|
| **C** — dictionary-referent recovery | Do varṇa sequences recover a word's dictionary meaning? | Closed | **No robust signal** (seed-fragile; domain-mismatch + leakage/collision) | Does not support; Track B stays blocked |
| **D0/D** — experiential-weather matching | Does flat varṇa/vṛtti composition match a word's emotional profile? | Closed | **`LLM_PILOT_NO_SIGNAL`** (`BARNUM_OVERMATCH` + `SCRAMBLE_EQUIVALENT`) | Does not support; blocked |
| **E-flat** — candidate boundary selection | Does the varṇa boundary reweight candidates toward the context-correct meaning? | Closed (narrow path) | **`CONTEXT_ONLY_EXPLAINS`** (context solved 11/12; A beat only dictionary-only) | Does not support; blocked |
| **F** — inference-output steering | Does varṇa-boundary prompting usefully steer a real LLM's inference? | Closed (exploratory) | **`CORRECTNESS_DEGRADED`** (distinctive steer, but correctness/usefulness dropped; single-model-judge caveat) | Does not support; blocked |
| **G** — polarity-boundary | Does a frozen, varṇa-**derived** signed-polarity vector place a word on its target pole better than random-flip / context / scramble / Barnum / dictionary? | **Scored** (commit `1fe5562`) | **`RANDOM_POLARITY_EXPLAINS`** — `malformed_rate 0.0`, `tasks_judged 10`, **`A_vs_R −0.1917`**, **`A_vs_X −0.075`** | Does not support; blocked |
| **B** — confirmatory / non-circular | An ontology-supporting, non-circular validation path | **BLOCKED** (unreachable here) | — | No confirmatory evidence exists |

## Per-track detail

**C — dictionary-referent recovery.** *Tested:* direct recovery of a word's dictionary sense from its varṇa sequence. *Can prove:* whether a simple recovery mapping is demonstrable. *Cannot prove:* absence of any mapping — apparent effects were seed-fragile and failed family-bootstrap/multi-seed stability. *Verdict:* no robust signal; not demonstrated (not disproven).

**D0/D — experiential-weather matching.** *Tested:* whether flat varṇa/vṛtti composition matches a word's emotional profile beyond controls. *Can prove:* whether the real composition beats Barnum/scramble baselines. *Cannot prove:* ontology — the real composition matched a generic Barnum profile (`BARNUM_OVERMATCH`) and scored no better than scrambled (`SCRAMBLE_EQUIVALENT`). *Verdict:* `LLM_PILOT_NO_SIGNAL`.

**E-flat — candidate boundary selection.** *Tested:* whether the varṇa boundary reweights candidates toward the context-correct one. *Can prove:* incremental value of the boundary over context. *Cannot prove:* boundary utility — context-only already ranked the correct candidate #1 in 11/12; the real boundary lost to context, scramble, etymology, and Barnum, beating only dictionary-only. *Verdict:* `CONTEXT_ONLY_EXPLAINS`; narrow flat path closed, do not scale.

**F — inference-output steering.** *Tested:* whether varṇa-boundary prompting usefully steers a real LLM (Mistral). *Can prove:* distinctiveness of the steer and its effect on correctness/usefulness. *Cannot prove:* usefulness — the steer was distinctive but reduced correctness/usefulness (both −0.1), and the judge was a single self-model. *Verdict:* `CORRECTNESS_DEGRADED`; no useful steering shown.

**G — polarity-boundary (committed `1fe5562`).** *Tested:* whether a **frozen, varṇa-table-derived** signed-polarity vector A places words on their pre-registered pole/candidate better than random sign-flip (R, co-primary), context-only (X, co-primary), scramble (B), Barnum (I), and dictionary (D). *Can prove:* whether the specific varṇa→polarity sign carries information and adds anything over context. *Cannot prove:* ontology — the varṇa polarity table is researcher-authored/high-DOF, so even a positive would be architecture-bound utility, never truth. *Result:* A was the second-worst arm (MRR: R 0.95 > I 0.875 > X 0.833 > B 0.775 > A 0.758 > D 0.692). The two co-primary bars **failed**: `A_vs_R = −0.19` (the real sign does *worse* than a random flip of itself) and `A_vs_X = −0.075` (no gain over context). Under the pre-registered rule (`A_vs_R ≤ eps → RANDOM_POLARITY_EXPLAINS`), the label is **`RANDOM_POLARITY_EXPLAINS`**. Consistent with the pre-registered prior (table authored blind to target poles). Caveats: n=10 smoke, single model, single seed. *Verdict:* negative/null; does not support Track B.

**Infrastructure (not a result).** Commit **`de58503`** adds an optional `--all-raw-dump` full-run scorer audit capture (every generation: raw text, parse status, normalized scores). It is **auditability infrastructure only** — gitignored, never a scoring artifact, changes no scores/labels/thresholds. Preceding harness fixes B1 (malformed-only debug dump) and B2 (accept positional-array scores) are likewise ingestion-layer only; B2 is what converted G's earlier 78%-malformed abort into the scoreable `1fe5562` result.

## Conclusion (explicit)

- **No ontology validation.** Five operationalizations (C, D0, E-flat, F, G) tested; none demonstrated useful or robust varṇa semantic signal. The core ontological claim remains **untested, not validated** (unshown ≠ disproven; equally, not validated).
- **No Sanskrit privilege.** No arm granted Sanskrit/varṇa special status; no `ONTOLOGICAL_SIGNAL`/privilege label was ever emitted.
- **Track B remains BLOCKED.** The only non-circular confirmatory path was never opened; no confirmatory evidence exists.
- **Current evidence favors random/context explanations over a varṇa-derived polarity signal.** In Track G specifically, a random sign-flip and plain context both explain the model's choices at least as well as the real varṇa-derived polarity (`A_vs_R −0.19`, `A_vs_X −0.075`); this mirrors the cross-track pattern of Barnum-overmatch, scramble-equivalence, and context-dominance.
- **What did work:** the evaluation framework and guardrails — pre-registration, frozen inputs, blinded packets, refusal-gated runners, adversarial controls — consistently caught weak positives and preserved honest negatives.

Structure, not validated meaning.
