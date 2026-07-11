# B1.10 — Official Contexts v3 (non-Claude blind author: Qwen) — PENDING PACKET-AWARE AUDIT

**Classification: `NONCLAUDE_BLIND_AUTHORED_v3_PENDING_PACKET_AWARE_AUDIT`.** These twelve sentences were
authored by a **packet-naive, non-Claude** author (Qwen2.5-14B/32B) via the per-word blind-authoring
workflow (`B1_10_PERWORD_BLIND_AUTHORING_WORKFLOW.md`, commit `0785b1ec` + `--max-rung` fix `1b47c8f6`).
They have passed **surface validation only**. They are **NOT yet approved** as official experimental
stimuli — the packet-aware audit (context-independence → Tier-3 echo → Tier-1/Tier-2 fairness → per-word
decisions) has **not** been run and is the deliberate next step. No judges have been run; no evidence-freeze
declaration has been created; the experiment number is unchanged (B1.10).

Guardrails: resonance / phonetic-fidelity refinement only. **No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no
semantic-truth / ontology / Sanskrit-privilege claim.** B1.4b′ remains `NULL_RETURN_BOTTOM`; original B1.4b
blocked; Track B blocked. **Structure, not validated meaning.**

---

## 1. Provenance summary (authoritative on-box hashes)

Master author packet: `B1_10_OFFICIAL_CONTEXT_AUTHOR_PACKET.md`, sha256
`7e07e16bb160481c647b5f6e11ff166f63f2fa42e442ba16bfa6fcffe9c30628` (asserted by the runner before every
generation; never edited). Authoring ladder: Qwen2.5-14B-Instruct → Qwen2.5-32B-Instruct → packet-naive
human. Generation settings: transformers/float16, temperature 0.7, top_p 0.9, top_k 0, repetition_penalty
1.0, do_sample, max_new_tokens 400. Each word authored in an **independent** fresh process fed **only** the
master packet + a per-word output-scope directive.

| word | accepted rung / model | resolved revision | attempt / seed | accepted raw_output_sha256 | failed attempts |
|---|---|---|---|---|---|
| pride | 0 / Qwen2.5-14B-Instruct | `cf98f3b3…` | 0 / 20260720 | `286f91d7…` | 0 |
| freedom | 0 / Qwen2.5-14B-Instruct | `cf98f3b3…` | 0 / 20260721 | `18a9c8e9…` | 0 |
| patience | 1 / Qwen2.5-32B-Instruct | `5ede1c97…` | 2 / 20260724 | `fa8366ea…` | 8 (6× rung0, 2× rung1) |
| courage | 0 / Qwen2.5-14B-Instruct | `cf98f3b3…` | 5 / 20260728 | `84cc9277…` | 5 (rung0) |
| control | 0 / Qwen2.5-14B-Instruct | `cf98f3b3…` | 0 / 20260724 | `3ba3f3df…` | 0 |
| doubt | 0 / Qwen2.5-14B-Instruct | `cf98f3b3…` | 1 / 20260726 | `84d4465d…` | 1 (rung0) |

Full per-attempt hashes/issues: `b1_10_author_v3_perword/MANIFEST.json`,
`b1_10_author_v3_perword/run_summary_phaseA.json`, `b1_10_author_v3_perword/provenance_patience_phaseB.json`.

**Byte-fidelity caveat:** the RunPod box could not `git push`; the sentence blocks below and the accepted
raw files in `b1_10_author_v3_perword/accepted/` are **transcribed from a terminal paste**. The
**authoritative** artifacts are the on-box files hashing to the `raw_output_sha256` values above (each was
`sha256sum`-verified on the box against its provenance). Every pasted `ACCEPTED.txt` hash matched its
authoritative provenance hash; the transcriptions are substantively faithful but may not be byte-exact
(whitespace / unicode apostrophes). See `b1_10_author_v3_perword/CAPTURE_NOTE.md`.

## 2. The twelve sentences (canonical block)

Combined-block sha256 (over the exact text between the fences): `a0abccb89091578cc6ee81b22143bd2bcd82ee9eb8624ba6855224825a418bfc`

```
pride
A: Sarah beamed with pride as she watched her son win the championship, knowing her years of coaching had paid off.
   intended class: A | confidence: high | mixed-condition detected: no | naturalness: natural
B: Mark felt a quiet pride in his ability to solve complex problems without needing external validation or praise.
   intended class: B | confidence: high | mixed-condition detected: no | naturalness: natural

freedom
A: She felt a surge of freedom when she finally quit her job and started her own business, despite the uncertainty.
   intended class: A | confidence: high | mixed-condition detected: no | naturalness: natural
B: He found true freedom in his daily walks through the park, enjoying the quiet solitude and natural beauty.
   intended class: B | confidence: high | mixed-condition detected: no | naturalness: natural

patience
A: She could barely keep her patience as she waited for the promotion that her colleagues seemed to be receiving.
   intended class: A | confidence: high | mixed-condition detected: no | naturalness: natural
B: He practiced patience while meditating, focusing on his breath without seeking external validation.
   intended class: B | confidence: high | mixed-condition detected: no | naturalness: natural

courage
A: Sarah felt a surge of courage when she saw her rival falter, knowing this was her moment to shine.
   intended class: A | confidence: high | mixed-condition detected: no | naturalness: natural
B: In the silence of his meditation, Mark found the courage to face his fears without needing anyone's approval.
   intended class: B | confidence: high | mixed-condition detected: no | naturalness: natural

control
A: She maintained a tight grip on the reins, her success hinging on her ability to control the spirited horse.
   intended class: A | confidence: high | mixed-condition detected: no | naturalness: natural
B: He let go of the steering wheel, trusting the car's autonomous system to control the vehicle smoothly.
   intended class: B | confidence: high | mixed-condition detected: no | naturalness: natural

doubt
A: Sarah felt a surge of doubt when she compared her progress to her colleagues', wondering if she was good enough.
   intended class: A | confidence: high | mixed-condition detected: no | naturalness: natural
B: Tom maintained a calm inner resolve, allowing his doubt to fade as he trusted in his own journey.
   intended class: B | confidence: high | mixed-condition detected: no | naturalness: natural
```

## 3. Surface validation (independent re-check)

Each pair independently re-validated with the frozen validator
(`python3 b1_10_surface_validator.py --raw <file> --word <word>`): all six returned exit 0,
`surface_pass: true`, `issues: []`. Rules unchanged (count / 12–22 words / target-word-exactly-once /
forbidden labels / self-check fields / mixed≠yes / naturalness≠forced).

## 4. Status / next step (NOT done here)

The **packet-aware audit** is the next step and has not been run. Do not run judges, do not create an
evidence-freeze declaration, and do not treat these as approved stimuli until the audit passes. If a word
fails the audit, regenerate **only that word-pair** via a fresh per-word blind job (never a packet-aware
edit) and re-audit. Items a reviewer should scrutinize are listed neutrally in
`b1_10_author_v3_perword/CAPTURE_NOTE.md` (§ audit-watch) — that list is *not* an audit finding, only a
pointer for the deferred review.

## 5. Guardrails
Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no semantic-truth
/ ontology / Sanskrit-privilege claim. **B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track
B blocked. Structure, not validated meaning.**
