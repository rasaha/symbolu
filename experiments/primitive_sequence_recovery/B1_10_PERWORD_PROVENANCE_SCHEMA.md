# B1.10 — Per-Word Author Provenance Schema (docs-only)

Defines the per-word-pair provenance record emitted by `b1_10_perword_author_run.py`. **Operational
improvement only** — no experimental design element changes. Resonance / phonetic-fidelity refinement
only — **no `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`, no semantic-truth / ontology / Sanskrit-privilege
claim.** B1.4b′ remains `NULL_RETURN_BOTTOM`; original B1.4b blocked; Track B blocked. **Structure, not
validated meaning.**

---

## 1. One record per word

Each of the six words gets its own `provenance_<word>.json`. There is no single-shot 12-sentence
provenance any more; provenance is **per word-pair**, matching the per-word decomposition.

## 2. Required fields (accepted pair)

| field | meaning |
|---|---|
| `artifact` | constant `"b1_10_perword_author_run"` |
| `word` | the target word (one of the six) |
| `word_index_1based` | 1–6, the packet-order position |
| `status` | `"ACCEPTED"` |
| `accepted.ladder_rung` | rung that produced the accepted pair (0=14B, 1=32B, 2=human) |
| `accepted.model_id` | model id of the accepting rung |
| `accepted.revision_requested` / `accepted.revision_resolved` | pinned vs resolved HF commit |
| `accepted.attempt_index` | 0-based attempt number within the rung that passed (accept-first-pass) |
| `accepted.seed` | the seed used for the accepted attempt (`base_seed + attempt_index`) |
| `accepted.raw_output_sha256` | sha256 of the accepted raw model output |
| `generation_settings` | backend, dtype, temperature, top_p, top_k, repetition_penalty, do_sample, max_new_tokens |
| `master_packet_sha256` | **must equal** `7e07e16b…` (asserted before any generation) |
| `delivered_prompt_sha256` | sha256 of (master packet + per-word directive) actually fed to the model |
| `per_word_directive` | the exact per-word scoping text appended to the master packet |
| `attempts` | full log of every attempt (rung, model, revision, attempt_index, seed, raw hash, surface_pass, issues, timestamp) — failures included |
| `reason_for_escalation` | constant **`SURFACE_VALIDATION_FAILURE_ONLY`** |
| `retry_budget_role` | states the retry budget is an operational safeguard only (not experimental/evidentiary/hypothesis-testing/judging) |
| `blindness_attestation` | explicit statement the process saw ONLY the master packet + per-word directive; no packets/varṇa/audits/prior contexts/results |
| `timestamp_utc` | ISO-8601 UTC |

## 3. Required fields (escalated to human)

If both model rungs exhaust their operational budget on surface failures, the record uses:

| field | meaning |
|---|---|
| `status` | `"ESCALATE_TO_HUMAN"` |
| `ladder_rung` | `2` |
| `model_id` | `"PACKET_NAIVE_HUMAN"` |
| `reason_for_escalation` | `"SURFACE_VALIDATION_FAILURE_ONLY"` |
| `master_packet_sha256` / `delivered_prompt_sha256` | as above |
| `attempts` | the full failed-attempt log across both model rungs |
| `note` | human-intake instruction (record human identity + blindness attestation on intake) |
| `timestamp_utc` | ISO-8601 UTC |

On human authoring, extend the record with `human_author_identity` and `human_blindness_attestation`
at intake (the human is packet-naive, non-Claude, disjoint from the Tier-3 paraphrase author and the
judge panel).

## 4. Invariants (auditor checklist)

- [ ] `master_packet_sha256 == 7e07e16bb160481c647b5f6e11ff166f63f2fa42e442ba16bfa6fcffe9c30628`
- [ ] `reason_for_escalation == SURFACE_VALIDATION_FAILURE_ONLY` on every record
- [ ] every attempt in `attempts` has its own raw-output sha256 and surface-validation result
- [ ] accepted attempt is the **first** `surface_pass: true` in its rung (accept-first-pass; no later pass overrides it)
- [ ] `seed == base_seed(word) + attempt_index` for each attempt (fresh seed per attempt)
- [ ] no accepted pair was edited/patched (accepted `raw_output_sha256` matches the saved `ACCEPTED.txt`)
- [ ] ladder order is exactly 14B → 32B → human; a climb happens only after a rung's budget is exhausted

## 5. Guardrails

Operational only; B1.10 design unchanged. Resonance / phonetic-fidelity refinement only. No
`GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no semantic-truth / ontology / Sanskrit-privilege claim.
**B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked. Structure, not validated
meaning.**
