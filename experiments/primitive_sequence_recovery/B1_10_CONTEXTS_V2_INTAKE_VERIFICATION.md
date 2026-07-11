# B1.10 Official Contexts v2 — Intake Verification (docs-only)

**Verdict: REJECTED for official use — fails the context-author independence rule.** The v2 set is retained as a
record, not frozen as official stimuli. Docs-only: no frozen items, packets, contexts, runners, evidence-freeze
declarations, results, or experiment numbers changed. Stays under B1.10. Resonance / phonetic-fidelity refinement
only — **no `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`, no semantic-truth / ontology / Sanskrit-privilege claim.**
B1.4b′ remains `NULL_RETURN_BOTTOM`; original B1.4b blocked; Track B blocked. **Structure, not validated meaning.**

Reviewed file: `B1_10_OFFICIAL_CONTEXTS_v2.md` (+ byte-identical `B1_10_OFFICIAL_CONTEXTS_v2_FROZEN.md`), imported
from `origin/claude/blinded-authoring-task-zdlwby` into this branch as commit `10efd766` (file content only; none
of the other session's commit history was merged).

---

## 1. Well-formedness checks — PASS

- 12 sentences, two per word, in packet order (pride, freedom, patience, courage, control, doubt). ✔
- Each sentence 12–22 words; target word used naturally; no dialogue; no forbidden labels. ✔
- Each sentence a single stable condition; no A→B or B→A transition. ✔
- Four self-check fields present per sentence; provenance block present; `_FROZEN` copy byte-identical. ✔
- Blindness attestation string present. ✔

## 2. Author-independence check — FAIL (blocking)

Provenance: `author_identity: fresh isolated model session — claude-opus-4-8, clean session`.

- `B1_10_OFFICIAL_JUDGE_PANEL_SPEC.md §5` and `B1_10_INDEPENDENT_CONTEXT_GENERATION_PROTOCOL.md` require the context
  author to be **disjoint from the Tier-3 paraphrase author — "not Claude / not any Anthropic model."**
- The Tier-3 packet paraphrases were authored by **Claude**; the v2 author is **`claude-opus-4-8`** — the **same
  model**. A clean session may make it packet-*blind*, but it is **not independent** of the paraphrase author.
- This is exactly the confound §5 guards against: shared model priors between the paraphrase author and the context
  author can manufacture spurious context↔packet alignment without any explicit packet exposure.

## 3. Convergence evidence — corroborates non-independence

The "clean Claude session" converged closely on the settings/phrasings used in the Claude-authored
`EXCLUDED_DEVELOPMENT_CONTEXTS_PACKET_AWARE` sets:

| word / pole | excluded packet-aware dev set (Claude) | v2 "blind" set (claude-opus-4-8) |
|---|---|---|
| freedom B | "Walking the coast at dawn, he felt a quiet freedom…" | "Walking the coastal path alone at dawn, she felt a freedom that asked nothing…" |
| courage A | "On the trading floor his courage swelled with the crowd's attention…" | "His courage on the trading floor appeared only when colleagues were watching…" |
| doubt B | "The physicist treated doubt as a quiet tool, probing her own assumptions…" | "The physicist held her doubt about the result steadily, testing it against the data…" |
| control B | "The pilot's control was mostly inward…" | "The pilot guided the small plane down through crosswinds with a control that belonged wholly to herself." |
| pride B | "The old carpenter took a private pride in a well-cut joint, needing no customer to praise…" | "He felt a quiet pride in the fence he built, whether or not anyone ever noticed it." |
| patience B | "The beekeeper worked with an unhurried patience…" | "The old gardener tended his slow-growing orchard with a patience that expected no particular harvest." |

Independent (non-Claude) authorship would be very unlikely to reproduce pilot-control, trading-floor-courage,
physicist-doubt, coast-at-dawn-freedom, and artisan-craft-pride simultaneously. The convergence is a milder cousin
of the echo confound — model-prior correlation, not literal packet echo — and confirms the §2 rule violation
matters in practice.

## 4. Classification

`B1_10_OFFICIAL_CONTEXTS_v2.md` and `B1_10_OFFICIAL_CONTEXTS_v2_FROZEN.md` are classified
**`EXCLUDED_CLAUDE_FAMILY_CONTEXTS`** (analogous to `EXCLUDED_DEVELOPMENT_CONTEXTS_PACKET_AWARE`). They are retained
as a record and as a diff reference; they **must not** become the frozen official stimuli and **must not** be wired
into any evidence-freeze declaration or run.

## 5. Remedy (unchanged from protocol)

Re-issue `B1_10_OFFICIAL_CONTEXT_AUTHOR_PACKET.md`, **unchanged**, to a **non-Claude / non-Anthropic** party:
- a human author who hasn't seen the internals, **or**
- a fresh isolated session of a different model family, disjoint from both the paraphrase author (Claude) and the
  judge panel (Llama / Gemma) — e.g. a Mistral or Qwen session.

Require the provenance block to name a non-Claude author and to carry the blindness attestation. When that set
returns: freeze it **before** any packet comparison, then run naturalness → quality → packet-comparison → echo
audit; reject-and-regenerate (never edit) any echoing item.

## 6. Status

- Docs-only intake record. The v2 files remain on disk (imported) but are **REJECTED for official use**. No
  official contexts are frozen. No protected B1.10 artifact was modified; no foreign commit history was merged.

## 7. Guardrails
Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no semantic-truth /
ontology / Sanskrit-privilege claim. **B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked.
Structure, not validated meaning.**
