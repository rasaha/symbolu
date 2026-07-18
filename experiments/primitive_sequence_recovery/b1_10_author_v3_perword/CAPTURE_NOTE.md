# B1.10 non-Claude author v3 (Qwen, per-word) — capture note & attempt log

**Classification: `NONCLAUDE_BLIND_AUTHORED_v3_PENDING_PACKET_AWARE_AUDIT`.** Surface-valid only; **not** yet
approved as official stimuli. No judges run; no evidence-freeze declaration; experiment number unchanged
(B1.10). Guardrails: no `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; B1.4b′ `NULL_RETURN_BOTTOM`; original B1.4b
blocked; Track B blocked; **structure, not validated meaning.**

## Byte-fidelity caveat

The RunPod box could not `git push`. The accepted sentence blocks (`accepted/*.txt`, the canonical block in
`../B1_10_OFFICIAL_CONTEXTS_v3_QWEN.md`) and the provenance JSONs here are **transcribed from terminal
pastes**, so they are **not guaranteed byte-exact**. The **authoritative** artifacts are the on-box files
hashing to the `raw_output_sha256` values below. On the box, each accepted `ACCEPTED.txt` was
`sha256sum`-verified and **matched** its provenance hash, so the accepted content is verified at the source;
the repo copies are substantively faithful transcriptions (possible whitespace / unicode-apostrophe drift).
The full **FAILED** raw outputs remain on-box (only their hashes + issue text are captured here); they can be
added byte-exact if the box can ever push.

Authoritative runner-emitted provenance on-box: `run_summary.json` (Phase A, all six words) and
`provenance_patience.json` (Phase B). Phase B is transcribed here as `provenance_patience_phaseB.json`; the
full Phase A summary is captured in `MANIFEST.json` + the attempt log below.

## Two-phase run (one rung per fresh process — disk/VRAM safe)

- **Phase A** — rung 0 `Qwen/Qwen2.5-14B-Instruct` (rev `cf98f3b3…`), all six words, `--max-rung 0`.
  5/6 accepted; `patience` exhausted rung 0 (6 surface failures).
- **Phase B** — rung 1 `Qwen/Qwen2.5-32B-Instruct` (rev `5ede1c97…`), only `patience`,
  `--start-rung 1 --max-rung 1` (after freeing the 14B cache). Accepted on attempt 2.

## Full attempt log (14 failed + 6 accepted = 20 attempts)

| word | rung / model | attempt / seed | raw_output_sha256 | surface | issue summary |
|---|---|---|---|---|---|
| pride | 0 / 14B | 0 / 20260720 | `286f91d7…` | ✅ PASS | — |
| freedom | 0 / 14B | 0 / 20260721 | `18a9c8e9…` | ✅ PASS | — |
| patience | 0 / 14B | 0 / 20260722 | `6ecd53b9…` | ❌ | both sentences missing "patience" |
| patience | 0 / 14B | 1 / 20260723 | `5365c748…` | ❌ | both missing "patience" |
| patience | 0 / 14B | 2 / 20260724 | `b67ddee0…` | ❌ | both missing "patience" |
| patience | 0 / 14B | 3 / 20260725 | `68c51df3…` | ❌ | A missing "patience" |
| patience | 0 / 14B | 4 / 20260726 | `a212c6ea…` | ❌ | A missing; B 23 words + missing |
| patience | 0 / 14B | 5 / 20260727 | `6ecd666b…` | ❌ | both missing "patience" |
| patience | 1 / 32B | 0 / 20260722 | `531e80dd…` | ❌ | A "impatience" ≠ "patience" |
| patience | 1 / 32B | 1 / 20260723 | `17b2f00e…` | ❌ | B missing "patience" |
| patience | 1 / 32B | 2 / 20260724 | `fa8366ea…` | ✅ PASS (accepted) | — |
| courage | 0 / 14B | 0 / 20260723 | `0c7f6b88…` | ❌ | both missing "courage" |
| courage | 0 / 14B | 1 / 20260724 | `7de0c706…` | ❌ | both 23/25 words + missing |
| courage | 0 / 14B | 2 / 20260725 | `33903766…` | ❌ | both missing "courage" |
| courage | 0 / 14B | 3 / 20260726 | `cf99ad12…` | ❌ | both missing "courage" |
| courage | 0 / 14B | 4 / 20260727 | `ce23bff3…` | ❌ | both missing "courage" |
| courage | 0 / 14B | 5 / 20260728 | `84cc9277…` | ✅ PASS (accepted) | — |
| control | 0 / 14B | 0 / 20260724 | `3ba3f3df…` | ✅ PASS | — |
| doubt | 0 / 14B | 0 / 20260725 | `49ac2536…` | ❌ | both "doubted" ≠ "doubt" |
| doubt | 0 / 14B | 1 / 20260726 | `84d4465d…` | ✅ PASS (accepted) | — |

Accept-first-pass held for every word (the accepted attempt is the **first** `surface_pass: true` at its
rung; no later pass overrode it; no A/B mixed across attempts; nothing edited/patched/truncated).

## Note on the `patience` accepted raw

The on-box accepted raw for `patience` (hash `fa8366ea…`) includes, **after** the two sentences, an echo of
the author packet's Section-9 provenance *template* (`author_identity: … Qwen clean session`,
`date_utc: 2023-10-06…`, `[Not computed]`, the attestation string). This is the **model echoing the packet
placeholders**, not real provenance — the authoritative provenance is `provenance_patience_phaseB.json`. The
echo is preserved in `accepted/patience_ACCEPTED.txt` for fidelity; only the two-sentence block is carried
into the canonical context concatenation (the echo is not part of the stimuli).

## Audit-watch (pointers for the DEFERRED packet-aware audit — NOT audit findings)

These are neutral pointers for the reviewer who runs the packet-aware / sentence-quality audit next. They are
**not** adjudicated here (that audit is deliberately not run in this step):
- `freedom` A uses "despite the uncertainty" — the reviewer should confirm it does not introduce a
  mixed/opposite condition (packet §5 flags "despite" when it flips the state).
- `control` B ("autonomous system to control the vehicle") — reviewer should confirm the Condition-B reading
  (non-grasping / letting go) is credible and that "control" reads naturally.
- General: confirm each A sits wholly in Condition A and each B wholly in Condition B, and run the Tier-3 echo
  overlap check against the pre-registered cap.
