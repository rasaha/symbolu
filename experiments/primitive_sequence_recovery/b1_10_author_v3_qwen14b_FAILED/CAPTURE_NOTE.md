# B1.10 non-Claude author — Qwen2.5-14B attempt #2 — FAILED (evidence record)

**Classification: `EXCLUDED_FAILED_SURFACE_VALIDATION`. Not for use.** Second non-Claude context-authoring attempt
(model swap 7B→14B, new seed). **Failed surface validation.** Raw output preserved unedited; not repaired; no retry
run. B1.4b′ `NULL_RETURN_BOTTOM`; original B1.4b blocked; Track B blocked; no `GENUTILITY_*`, no
`ONTOLOGICAL_SIGNAL`; structure, not validated meaning.

## Run (authoritative — from the pasted `provenance.json`, saved verbatim here)

| field | value |
|---|---|
| model_id | `Qwen/Qwen2.5-14B-Instruct` |
| revision requested | `main` |
| **revision resolved** | `cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8` |
| author-packet sha256 (asserted before run) | `7e07e16bb160481c647b5f6e11ff166f63f2fa42e442ba16bfa6fcffe9c30628` ✓ |
| **raw_output_sha256 (authoritative)** | `aad818d85c72ed40f89047f4439d40ede743151398d1f812d73b9d87e2be17be` |
| settings | temp 0.7 · top_p 0.9 · top_k 0 · rep_pen 1.0 · do_sample · **seed 20260714** · max_new 900 · runs 1 |
| timestamp_utc | `2026-07-11T07:21:24.322655+00:00` |

`provenance.json` and `surface_validation.json` here are **verbatim** (byte-exact) from the box.

## raw_output.txt byte-fidelity

`raw_output.txt` here is a **transcription from the terminal paste** (the box could not `git push`), so it is **not**
byte-exact:
- authoritative on-box `raw_output_sha256` (in `provenance.json`) = `aad818d8…`
- this transcription's sha256 = `880c1f9a187223cbe5a9f805bee57a2bb52d93611d1a2c5c0e447ebdfae297e2`
- match? **NO** (paste drift: code-fence/whitespace/newline). Content is substantively faithful; replace with the
  byte-exact `raw_output.txt` (hashing to `aad818d8…`) when the box can push.

> The provenance block at the tail of `raw_output.txt` (`Qwen … model id Qwen`, `date 2023-10-06…`,
> `[SHA256 hash of …]`) is the **model echoing the packet's Section-9 template placeholders**, not real provenance.
> The authoritative provenance is `provenance.json` above.

## Why it failed (all 5 issues verified genuine)

| issue | sentence | verdict |
|---|---|---|
| pride/A 24 words (>22) | "Mark felt a surge of pride…knowing it would impress his parents." | genuine |
| control/A 23 words (>22) | "Michael tightened his grip on the steering wheel…as the car slid on the icy road." | genuine (word "control" *is* present; length fails) |
| courage/B missing word | "Jamie faced her fears head-on, drawing inner strength from her own resolve…" | genuine — no "courage" |
| control/B missing word | "Rachel allowed herself to flow with the current of events, trusting her inner compass…" | genuine — no "control" |
| doubt/A missing word | "Tom's confidence…wavered as his boss's skepticism began to affect his self-belief." | genuine — no "doubt" |

7 of 12 sentences pass; surface validation requires all 12, so the set fails.

## Recurring failure pattern (across attempts #1 and #2)

Both non-Claude attempts failed the same class of surface rule — **the model omits the literal target word when
writing a natural, single-condition sentence**, especially for self-grounded (B) sentences and transformation-ish
states (courage-B "inner strength/resolve", control-B "inner compass", doubt-A "confidence wavered"). The 14B also
over-ran the 12–22 word limit twice. This is a genuine tension between "use the exact word once" + "one stable
condition" + "no caricature" + "12–22 words" that 7B/14B open models do not reliably satisfy in a single shot.

## Attempt log

| # | model | seed | resolved rev | result | evidence dir |
|---|---|---|---|---|---|
| 1 | Qwen2.5-7B-Instruct | 20260712 | a09a3545… | FAILED (3 missing-word + 1 short) | `b1_10_author_v3_qwen_FAILED/` |
| 2 | Qwen2.5-14B-Instruct | 20260714 | cf98f3b3… | FAILED (3 missing-word + 2 over-length) | `b1_10_author_v3_qwen14b_FAILED/` |

## Status / next step

- **No edit, no repair, no auto-retry** (workflow failure-handling rule). Awaiting operator instruction.
- Options (each a **new blind generation**, never an edit): (a) larger model — `Qwen/Qwen2.5-32B-Instruct` (needs a
  bigger-disk pod); (b) another seed on the 14B; (c) Mistral-7B; (d) a packet-naive **human** author; (e) operator
  reconsiders the surface-rule strictness (e.g. whether "exactly once" / the 12–22 band should be relaxed — a
  validation-rule decision for the operator; the packet content itself would remain unchanged).
