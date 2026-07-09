# B1.6 — 10-Sample Exploratory Generation Probe

**Status:** Exploratory probe (docs only). **EXPLORATORY, NOT FORMAL EVIDENCE.** Cannot emit a `GENUTILITY_*`
terminal label.
**Outcome: the real generation probe COULD NOT BE EXECUTED in this environment — no credentialed generator or
judge model is available. No outputs, ratings, arm summaries, or effect judgements were fabricated.**
**B1.4b′ remains `NULL_RETURN_BOTTOM` and is not reinterpreted. No ontology, no Sanskrit privilege, no validated
meaning, no `ONTOLOGICAL_SIGNAL`. Original B1.4b remains blocked. Track B remains blocked. Structure, not
validated meaning.**

**Framing label: `B1_6_10_SAMPLE_EXPLORATORY_GENERATION_PROBE`.
Execution status: `B1_6_10_SAMPLE_PROBE_BLOCKED_NO_GENERATOR_MODEL`.**

Uses: frozen scaffolds (`b1a3227`), generation driver (`cc56eb1`), judging harness (`6b2b7da`), mock dry run
(`913339e`).

---

## 1. Why this is blocked (stated first, plainly)

A real exploratory probe needs a real generator model (one fixed model, identical settings across arms) and — for
LLM-as-judge — a **different** real model. **This environment has neither:**

- **No API credentials** — `ANTHROPIC_BASE_URL=https://api.anthropic.com` is set but there is **no API key**; a
  minimal call returns **HTTP 401**. No OpenAI/Mistral/other keys present.
- **No LLM SDK** — `anthropic`/`openai`/`mistralai` not installed (`transformers` is present but there is no
  suitable local model, and a tiny local model's interpretations would be noise, not a legitimate fixed
  generator).
- **No local model server** — no `ollama`, no served endpoint.

The B1.6 generation driver was **built with no LLM adapter on purpose** (real generation is operator-run). With
no reachable model, generation cannot be performed here **without fabricating text** — which is forbidden.
**Fabricating generated outputs and ratings and reporting arm summaries / an effect label would be manufacturing
the exact evidence this program refuses to fake.** So the probe is recorded as blocked, honestly, rather than
faked.

This is consistent with the standing position: **real generation is an operator action** (e.g. RunPod with a
real model + key). §7 gives the exact commands to run this probe there.

## 2. What WAS done here (real, non-fabricated)

- **Deterministic 10-target balanced subset** selected from the frozen 24-target file (§3) — reproducible, no
  cherry-picking, no scaffold edits.
- **Pipeline readiness re-verified** — driver + judging tests **39/39**; the real evidence-freeze gate **refuses**
  without an operator declaration; mock plumbing works end-to-end (`913339e`).
- **No temporary probe declaration was created**, because with no generator there is nothing to gate; §5 gives
  the template for the operator to use under a gitignored runtime path.

## 3. Selected 10-target subset (deterministic, balanced)

Round-robin across the six frozen strata (pass-by-pass, file order within stratum) until 10 — **not** seeded on
expected Symbol-U success:

| # | item_id | target | stratum | consonant coverage |
|---|---|---|---|---|
| 1 | b16-01 | river | common concrete | 1.00 |
| 2 | b16-05 | balance | abstract | 1.00 |
| 3 | b16-09 | Maya | name-like | 1.00 |
| 4 | b16-13 | lotus | symbolic/spiritual | 1.00 |
| 5 | b16-17 | Lumen | brand/product | 1.00 |
| 6 | b16-21 | grief | emotionally charged | 0.67 |
| 7 | b16-02 | bridge | common concrete | 1.00 |
| 8 | b16-06 | freedom | abstract | 0.75 |
| 9 | b16-10 | Rowan | name-like | 1.00 |
| 10 | b16-14 | dawn | symbolic/spiritual | 1.00 |

Per-stratum counts: common-concrete 2, abstract 2, name-like 2, symbolic 2, brand 1, emotional 1 (all six strata
represented). The already-frozen scaffold records (incl. KCPR dual-pole frames, `THEORY_NONCANONICAL_INPUT_POLARITY`,
CSR/STL and Kosha deferred) are used **unedited**.

## 4. Arms (would be run; identical settings each)

`SYMBOLU_SCAFFOLD`, `PLAIN_PROMPT_BASELINE`, `GENERIC_STRUCTURED_PROMPT_BASELINE`, `RANDOMIZED_SYMBOLU_CONTROL`,
`SEMANTIC_LLM_BASELINE` → 10 targets × 5 arms = **50 outputs** (none produced here).

## 5. Probe-specific declarations (templates; operator-created; gitignored)

Under a runtime path such as `run_out/b1_6_10_sample_probe/` — **never** the full-pilot paths:

```json
// run_out/b1_6_10_sample_probe/PROBE_EVIDENCE_FREEZE.json
{
  "artifact": "b1_6_pilot_EVIDENCE_FREEZE_DECLARED",
  "evidence_freeze_declared": true,
  "mode": "exploratory_10_sample_generation_probe",
  "scaffold_manifest_sha256": "<sha256 frozen/b1_6_pilot_scaffold_manifest.json>",
  "target_scaffold_sha256": "<sha256 frozen/b1_6_pilot_targets_scaffolds.json>",
  "randomized_control_manifest_sha256": "<sha256 frozen/b1_6_pilot_randomized_control_manifest.json>",
  "prompt_rubric_sha256": "<sha256 B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md>",
  "declared_by": "<operator>", "declared_at_utc": "<ISO-8601>",
  "attestation": "B1.6 pilot generation only; no judging; no semantic truth claim; Symbol-U utility test only; B1.4b′ remains NULL_RETURN_BOTTOM."
}
```

Note `mode: "exploratory_10_sample_generation_probe"` — this **does not** masquerade as the full pilot freeze.
(The current driver checks `mode == "pilot_generation"`; for a real probe the operator either uses that mode or
runs the probe via an operator harness that accepts the exploratory mode. Either way it is exploratory-only and
emits no terminal label.) A separate probe `RATINGS_FROZEN` (with the judging attestation) governs unblinding.

## 6. Blinding

Blinding is enforced by the harness regardless of who runs it: judge-visible packages carry no arm names /
Symbol-U / KCPR / scaffold metadata (verified in the mock dry run); hidden metadata is a separate file, joined
only after ratings freeze. Since **no outputs were generated here**, there is nothing to un-blind and no
blindness breach.

## 7. Operator commands to run the real probe (RunPod or a model host)

```bash
cd experiments/primitive_sequence_recovery
# 1) operator supplies a real generator adapter generator(record)->str (one fixed model, identical settings)
#    and a DIFFERENT judge model for LLM-as-judge (exploratory only).
# 2) restrict to the 10 item_ids in §3, run 10x5 generation via run(mock=False, generator=..., decl_path=<probe>)
# 3) Phase A blind package -> human/LLM(diff-model) ratings -> probe RATINGS_FROZEN -> aggregate(...)
# record: model name+version, temperature, max tokens, seed, date/time, host.
```

All runtime artifacts stay under `run_out/` (gitignored). The probe may emit only the §10 exploratory labels —
**never** a `GENUTILITY_*` terminal label.

## 8. Arm-level summary / pairwise comparisons

**Not available** — no generation, no ratings. Reporting fabricated numbers is forbidden. The honest values are
**"not measured."** No `SYMBOLU_SCAFFOLD` vs plain / generic-structured / randomized / semantic-LLM comparison
exists to report.

## 9. Qualitative note on the effect

**None can be given.** Whether the Symbol-U scaffold looks promising, weak, null, or baseline-dominated is
**unknown** — it was not observed. Any statement otherwise would be invented. (Prior context, unchanged: the
per-varṇa polarity scaffold is `THEORY_NONCANONICAL_INPUT_POLARITY`, the blind attribute-prediction test B1.4b′
was `NULL_RETURN_BOTTOM`, and the pilot cannot in any case emit a terminal verdict.)

## 10. Exploratory label

Execution status: **`B1_6_10_SAMPLE_PROBE_BLOCKED_NO_GENERATOR_MODEL`** (a plumbing/environment blocker).

The effect labels — `..._SYMBOLU_PROMISING`, `..._SYMBOLU_WEAK`, `..._COLLAPSES_TO_GENERIC_STRUCTURE`,
`..._RANDOMIZED_MATCHES`, `..._LLM_BASELINE_WINS`, `..._NO_CLEAR_EFFECT` — are **not** applicable and **none is
emitted**, because each presupposes real ratings that do not exist. In particular `..._NO_CLEAR_EFFECT` is **not**
claimed (that would imply the probe ran and showed nothing; it did not run). `..._INVALID_BLINDING` does not
apply (nothing was generated/rated). **No `GENUTILITY_*` label emitted.**

## 11. Commit policy

Docs-only report committed. No generated outputs, ratings, hidden metadata, declarations, or run manifests exist
or are committed. `run_out/` remains gitignored.

## 12. Guardrails

No real generation (none possible here); no external API call succeeded (401); no real judging; no evidence
freeze; no ratings freeze; no fabricated outputs/ratings; no generated outputs committed; no semantic-truth
claim; no `ONTOLOGICAL_SIGNAL`; no Sanskrit privilege; KCPR caveat `THEORY_NONCANONICAL_INPUT_POLARITY` remains
active; **B1.4b′ remains `NULL_RETURN_BOTTOM`**; original B1.4b remains blocked; Track B remains blocked.
**Structure, not validated meaning.**

---

## Final report

- **Was 10-sample generation run?** **No** — blocked: no credentialed generator/judge model in this environment
  (`api.anthropic.com` → HTTP 401; no key; no SDK; no local model). Nothing was fabricated.
- **Generator model/settings:** none used (not runnable here).
- **Judge type/model:** none used.
- **Number of targets and outputs:** 10 targets selected (deterministic, balanced, §3); **0 outputs generated**
  (would be 10×5 = 50 on a real run).
- **Blinding passed?** N/A — nothing generated/rated; the harness's blinding was verified separately in the mock
  dry run.
- **Ratings frozen before unblinding?** N/A — no ratings.
- **Exploratory label:** `B1_6_10_SAMPLE_PROBE_BLOCKED_NO_GENERATOR_MODEL` (no effect label emitted).
- **Arm-level summary:** not measured.
- **Pairwise Symbol-U comparisons:** not measured.
- **Any formal `GENUTILITY_*` label emitted?** No.
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**
- **This is exploratory only** — and, here, not executed for lack of a model; the real probe is an operator run
  (§7).

> B1.6 10-sample exploratory generation probe completed/attempted. Exploratory only; no GENUTILITY terminal
> label. No ontology or semantic-truth claim. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains blocked.
> Track B remains blocked. Structure, not validated meaning.
