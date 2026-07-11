# B1.10 non-Claude author — Qwen attempt #1 — FAILED (evidence record)

**Classification: `EXCLUDED_FAILED_SURFACE_VALIDATION`. Not for use.** This is the preserved record of the first
non-Claude context-authoring attempt, which **failed surface validation**. Per the workflow, the raw attempt is
preserved unedited; the output was **not** repaired, and no retry has been run. B1.4b′ remains `NULL_RETURN_BOTTOM`;
original B1.4b blocked; Track B blocked; no `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`; structure, not validated meaning.

## Capture method (important — byte-fidelity caveat)

The RunPod box could not `git push`. These files were **transcribed from a terminal `cat` paste**, not copied from
the box. Byte-fidelity is therefore **not** guaranteed:

| item | value |
|---|---|
| authoritative on-box `raw_output_sha256` (runner-computed) | `f0b934ecaa456fec87f43aa11fc767628aebec717d0d59b7026f7ab633c6829a` |
| this transcription's sha256 (`raw_output.txt` here) | `181d12bb2255284bceb425c7127bdc0b9d457119857f0f1c350f49e7c0d083d5` |
| match? | **NO** — differs from the authoritative hash |

The mismatch is expected from a terminal paste (trailing whitespace on the `intended class` lines, final-newline,
or unicode em-dash/apostrophe drift). **The content is substantively faithful, but `raw_output.txt` here is NOT the
byte-exact model output.** The authoritative artifact remains on the box; when it can be pushed, replace this
transcription with the real `raw_output.txt` (which will hash to `f0b934ec…`) and the real `provenance.json`.

## Run parameters (from the runner's stdout summary + declared settings)

| field | value |
|---|---|
| model_id | `Qwen/Qwen2.5-7B-Instruct` |
| revision (requested = resolved) | `a09a35458c702b33eeacc393d103063234e8bc28` |
| author-packet sha256 (asserted by runner before run) | `7e07e16bb160481c647b5f6e11ff166f63f2fa42e442ba16bfa6fcffe9c30628` |
| generation settings | backend=transformers, dtype=float16, temperature=0.7, top_p=0.9, top_k=0, repetition_penalty=1.0, do_sample=true, seed=20260712, max_new_tokens=800, runs=1 |
| structural blindness | fresh isolated process fed ONLY the author packet (no packets/varṇa/audits/results/prior contexts) |
| `timestamp_utc` | NOT captured in the paste (present in the on-box `provenance.json`, not transcribed) |

> Note: the provenance block visible at the tail of `raw_output.txt` (`model id + note "clean session"`,
> `date 2023-10-06…`, placeholder hashes) is the **model echoing the author packet's Section-9 template
> placeholders** — it is not real provenance. The authoritative provenance is the runner's `provenance.json` on the
> box (real hashes/timestamp).

## Why it failed (all four issues verified genuine against the sentences)

| issue | sentence | verdict |
|---|---|---|
| pride/A target word missing | "After losing the championship, she couldn't bear the thought of her teammates looking at her with disappointment." | genuine — no "pride" |
| patience/A target word missing | "He fidgeted restlessly, unable to bear the wait for the test results that would decide his future." | genuine — no "patience" |
| control/A target word missing | "He felt a surge of anger, the kind of uncontrollable rage that made him lash out." | genuine — "uncontrollable" ≠ the word "control" used naturally |
| courage/B wordcount 11 | "She faced the challenge with courage, determined to overcome her fears." | genuine — 11 words (< 12) |

Cause: typical 7B multi-constraint slippage (dropped the target word in 3 of 6 Condition-A sentences; one too-short
sentence). Not a validator artifact — the parser found all 12 sentences in the correct word-blocks.

## Status / next step

- **No edit, no repair, no auto-retry** (per the workflow's failure-handling rule).
- Awaiting operator instruction on the remedy: (1) one fresh retry at a new seed; (2) a stronger non-Claude model
  (e.g. `Qwen/Qwen2.5-14B-Instruct`) for better instruction-following — recommended; or (3) switch family to
  `mistralai/Mistral-7B-Instruct-v0.3`. Any remedy is a **new blind generation**, never an edit of this output.
