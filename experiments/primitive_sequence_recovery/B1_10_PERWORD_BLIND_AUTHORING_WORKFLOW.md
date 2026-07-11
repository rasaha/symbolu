# B1.10 — Per-Word Blind Authoring with Pre-Registered Escalation (operational improvement only)

**This is an operational improvement to the *authoring mechanics* of B1.10. It does NOT change the
experiment.** The six words, Condition A/B, the master author packet (sha256
`7e07e16bb160481c647b5f6e11ff166f63f2fa42e442ba16bfa6fcffe9c30628`, never edited), the surface
rules, the Llama/Gemma judge panel, the statistics, the evidence-freeze model, and the experiment
number are all **unchanged**. Both prior read-only design reviews approved this decomposition and the
escalation ladder. Resonance / phonetic-fidelity refinement only — **no `GENUTILITY_*`, no
`ONTOLOGICAL_SIGNAL`, no semantic-truth / ontology / Sanskrit-privilege claim.** B1.4b′ remains
`NULL_RETURN_BOTTOM`; original B1.4b blocked; Track B blocked. **Structure, not validated meaning.**

---

## 1. Why change the mechanics (not the design)

Two non-Claude blind attempts to author all six words in a single shot failed the surface validator on
**instruction-following**, not on content:
- Qwen2.5-7B (seed 20260712): 3 missing-target-word + 1 too-short → `EXCLUDED_FAILED_SURFACE_VALIDATION`.
- Qwen2.5-14B (seed 20260714): 3 missing-target-word + 2 over-length → `EXCLUDED_FAILED_SURFACE_VALIDATION`.

The recurring failure is a genuine multi-constraint tension across **twelve** sentences at once ("use the
exact word once" + "one stable condition" + "no caricature" + "12–22 words"). One failing sentence sinks
the whole set (surface validation requires all twelve). Open 7B/14B models do not reliably satisfy all of
it in a single response.

The fix is purely operational: **decompose authoring into six independent per-word jobs**. A failure now
isolates to one word; only that word is regenerated. This does not touch the blinding, the rules, the
packets, or the judging — it only reduces the per-call constraint load.

## 2. What is unchanged (explicit)

| Element | Status |
|---|---|
| Six target words (pride, freedom, patience, courage, control, doubt) | **unchanged** |
| Condition A / Condition B definitions | **unchanged** |
| Master author packet (`7e07e16b…`) | **unchanged, byte-for-byte; hash asserted every run** |
| Surface rules (count / 12–22 words / target-word-exactly-once / forbidden labels / self-check / no mixed=yes / no forced) | **unchanged — NO relaxation** |
| Packet-aware audit (context-independence → Tier-3 echo → Tier-1/Tier-2 fairness) | **unchanged** |
| Judge panel J0/J1/J2 (Llama-3.1-8B, Meta-Llama-3-8B, gemma-2-9b-it) | **unchanged** |
| Statistics (specific / valence / generic-source-condition margins + both increments) | **unchanged** |
| Single-final-evidence-freeze model | **unchanged** |
| Experiment number (stays B1.10; no B1.11) | **unchanged** |

## 3. The per-word decomposition

Six **independent** blind generations, one per word. Each job:

1. Receives **only** the unchanged master author packet (`7e07e16b…`, all six words) **plus** a small
   per-word **scoping directive** that names which single word to author this run and the matching
   two-sentence output layout. The directive does **not** alter, restate, or reinterpret Conditions A/B
   or any rule — those come solely from the master packet. It only narrows the **output scope** to one
   word. The scientific/blinding content the author sees is identical to the six-word packet; only the
   number of words authored per run changes. The job receives **no** Tier-1/Tier-2/Tier-3 packet, no
   varṇa mapping, no audit, no prior context set, and no result.
2. Produces **exactly one** Condition-A sentence + **one** Condition-B sentence for that word, each with
   the four self-check fields (intended class / confidence / mixed-condition detected / naturalness).
3. Is **surface-validated in isolation** (`b1_10_surface_validator.validate_word_pair`), scope = one
   word-pair, **same rules, no relaxation**.

### Accept-first-pass (atomic A/B pairs)

- The **first** surface-passing pair for a word is **accepted and kept**.
- An accepted pair is **never regenerated**, and passing versions are **never compared** against each
  other (no cherry-picking a "best" passing pair — that would be a hidden selection channel).
- On surface **failure**, the whole pair is **discarded** — never edited, patched, or truncated — and
  only that word is regenerated with a **fresh seed** (`base_seed + attempt_index`).

## 4. Pre-registered escalation ladder

The per-rung retry budget (`ATTEMPTS_PER_RUNG`, default 6) is an **operational safeguard only** — it is
**not** an experimental, evidentiary, hypothesis-testing, or judging parameter. Its **sole** trigger is a
packet-blind **surface** failure. When a rung exhausts its budget without a pass, authoring for that word
**escalates** along a ladder fixed in advance:

```
rung 0:  Qwen/Qwen2.5-14B-Instruct
rung 1:  Qwen/Qwen2.5-32B-Instruct
rung 2:  packet-naive human author
```

- A word climbs the ladder **only** because of surface-validation failure — never because of content,
  echo, results, or any packet-aware signal (the runner never sees a packet or an audit).
- Because the trigger is packet-blind and identical for every word, the ladder introduces **no hidden
  selection bias**: it selects for *instruction-following capacity*, which is orthogonal to the tested
  hypothesis.
- `reason_for_escalation` is recorded as the frozen constant **`SURFACE_VALIDATION_FAILURE_ONLY`** on
  every provenance record, so any climb is attributable only to surface failure.
- The final rung is a **packet-naive human** — the same independence bar as the models (non-Claude,
  disjoint from the Tier-3 paraphrase author and the judge panel, blind to all §1-never-see material).
  The runner cannot generate this rung; it emits an `ESCALATE_TO_HUMAN` record and stops for that word.

## 5. Assembly and audit (unchanged downstream)

1. Author each of the six words independently (§3–§4). Every raw attempt — pass or fail — is saved
   unchanged under its own `<word>_rung<r>_attempt<k>/` directory (auditable; failures preserved, never
   patched).
2. **Only after all six word-pairs pass**, concatenate the six accepted pairs into **one** development
   context file (`b1_10_contexts_v3_perword.txt`) — an ordinary Git-tracked file, **no intermediate
   freeze** (per `B1_10_WORKFLOW_PROTOCOL_UPDATE.md`).
3. Run the **packet-aware audit** directly on that live development file (context-independence → Tier-3
   echo → Tier-1/Tier-2 fairness → per-word decisions). If a word fails the audit, regenerate **only that
   word-pair** via a fresh blind per-word job (§3) — never a packet-aware edit — and re-audit until all
   pass.
4. Only after all items pass, the judges complete the real run, and statistics are computed, create the
   **single** final evidence package (`B1_10_WORKFLOW_PROTOCOL_UPDATE.md` §4). **No judges are run until
   the context set passes the packet-aware audit.**

## 6. Files

| File | Role |
|---|---|
| `B1_10_OFFICIAL_CONTEXT_AUTHOR_PACKET.md` | master packet, **unchanged** (`7e07e16b…`) |
| `b1_10_surface_validator.py` | packet-blind surface validator, per-word-pair scope, **same rules** |
| `b1_10_perword_author_run.py` | per-word runner with escalation ladder + accept-first-pass |
| `B1_10_PERWORD_PROVENANCE_SCHEMA.md` | per-pair provenance record schema |
| `B1_10_PERWORD_BLIND_AUTHORING_WORKFLOW.md` | this document |

`B1_10_NONCLAUDE_AUTHOR_HANDOFF.md` (six-word, single-shot) is **superseded** for authoring mechanics by
this per-word workflow; its blinding, scope, and independence requirements (§2, §5) still hold and are
carried here unchanged.

## 7. Invocation (RunPod / GPU host, clean env)

```bash
# only the master packet is copied to the box; no other B1.10 file
python3 b1_10_perword_author_run.py \
    --packet /workspace/B1_10_OFFICIAL_CONTEXT_AUTHOR_PACKET.md \
    --out    /workspace/b1_10_author_v3_perword
# authors all six words, climbing the ladder per word only on surface failure;
# writes b1_10_contexts_v3_perword.txt only if all six pass.
```

## 8. Guardrails

Operational improvement only; the B1.10 scientific design is unchanged. Resonance / phonetic-fidelity
refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no semantic-truth / ontology /
Sanskrit-privilege claim. **B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked.
Structure, not validated meaning.**
