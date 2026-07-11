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

---

## Appendix — Operational Commands (Non-Normative)

> **These commands are operational examples only. They do not modify the scientific protocol or decision
> rules. Any discrepancy between this appendix and the protocol documents is resolved in favor of the
> protocol documents.**
>
> Scope note on what exists as code vs. as an operator procedure: steps 1–4 are fully scripted
> (`b1_10_perword_author_run.py`, `b1_10_surface_validator.py`). Step 5 (packet-aware audit) is a
> **reviewer procedure** defined in the protocol docs, with one programmatic aid (`dry-check`
> tier-identifiability). Step 6 (judges) runs through the existing gated `run_b1_10_control_ext.py`. Step 7
> (single evidence freeze) is **operator-assembled** per `B1_10_WORKFLOW_PROTOCOL_UPDATE.md` §4 — there is
> no auto-assembler, by design (the freeze is a deliberate, gated act). Paths below assume the experiment
> directory `experiments/primitive_sequence_recovery/`.

### 1. Start a per-word author run

The runner authors each requested word independently. The **model is chosen by the escalation ladder**
(not a free `--model` flag): `--start-rung 0` = Qwen2.5-14B, `1` = Qwen2.5-32B, `2` = human. **Seeds are
pre-declared** in `BASE_SEEDS` (attempt *k* uses `base_seed + k`) — they are not a CLI parameter, to keep
seeds fixed before generation.

```bash
# all six words, starting at rung 0 (Qwen2.5-14B); only the master packet is on the box
python3 b1_10_perword_author_run.py \
    --packet /workspace/B1_10_OFFICIAL_CONTEXT_AUTHOR_PACKET.md \
    --out    /workspace/b1_10_author_v3_perword

# a single word only (e.g. regenerate one word after an audit rejection)
python3 b1_10_perword_author_run.py \
    --packet /workspace/B1_10_OFFICIAL_CONTEXT_AUTHOR_PACKET.md \
    --out    /workspace/b1_10_author_v3_perword \
    --words  courage
```

| parameter | how it is set |
|---|---|
| word | `--words <w> [<w> ...]` (default: all six, packet order) |
| model | `--start-rung {0,1,2}` → ladder rung (14B / 32B / human); climbs automatically on surface failure |
| seed | pre-declared `BASE_SEEDS[word] + attempt_index` (fixed before generation; not a flag) |
| output directory | `--out <dir>` |

Each word writes `provenance_<word>.json` and one `<word>_rung<r>_attempt<k>/` directory per attempt
(every raw attempt preserved unedited; the accepted one also as `ACCEPTED.txt`).

### 2. Run surface validation

The runner already surface-validates internally, but each accepted/failed pair can be re-checked
standalone. **Prints the validation JSON; exit code 0 = pass, 1 = fail.**

```bash
python3 b1_10_surface_validator.py \
    --raw /workspace/b1_10_author_v3_perword/pride_rung0_attempt0/raw_output.txt \
    --word pride
echo "exit=$?"     # 0 = surface_pass, 1 = surface fail
```

Expected JSON (pass):

```json
{ "surface_pass": true, "issues": [], "word": "pride", "n_sentences": 2 }
```

Expected JSON (fail — e.g. over-length):

```json
{ "surface_pass": false,
  "issues": ["[A: Michael tightened his grip on the steeri...] wordcount 24 out of 12-22"],
  "word": "control", "n_sentences": 2 }
```

Running the module with **no arguments** executes the built-in self-tests (mock only), not a validation.

### 3. Escalate to the next rung

Escalation is **automatic** inside a single run (a word climbs 14B → 32B → human only when a rung's
operational retry budget is exhausted on **surface-validation failure**). To resume a specific word
directly at a higher rung (e.g. after a manual stop), pass `--start-rung`:

```bash
# resume one word at rung 1 (Qwen2.5-32B)
python3 b1_10_perword_author_run.py \
    --packet /workspace/B1_10_OFFICIAL_CONTEXT_AUTHOR_PACKET.md \
    --out    /workspace/b1_10_author_v3_perword \
    --words  doubt --start-rung 1
```

**Human-author handoff (rung 2).** When both model rungs are exhausted the runner emits
`provenance_<word>.json` with `status: ESCALATE_TO_HUMAN`. Procedure:

1. Give a **packet-naive human** (non-Claude family; disjoint from the Tier-3 paraphrase author and the
   Llama/Gemma judge panel) **only** the master packet (`7e07e16b…`) + the per-word directive for that one
   word (both are in the provenance record's `delivered_prompt_sha256` / `per_word_directive`).
2. Take back exactly one A + one B sentence with the four self-check fields; save as
   `<word>_rung2_human/raw_output.txt`.
3. Surface-validate it (step 2). On pass, record the human's identity + blindness attestation into the
   provenance (`human_author_identity`, `human_blindness_attestation`).

**No regeneration after a passing pair.** Once any rung produces a surface-passing pair, that pair is
final for the word: the runner stops (accept-first-pass), never regenerates it, and never compares it
against other passing versions. Do not re-run an already-accepted word.

### 4. Concatenate accepted pairs

The runner **automatically** writes the combined file once **all six** words have a surface-passing pair:

```bash
# produced by the run when all six pass:
cat /workspace/b1_10_author_v3_perword/b1_10_contexts_v3_perword.txt
cat /workspace/b1_10_author_v3_perword/combined_context_sha256.txt   # its sha256

# verify exactly 12 sentences (6 words x one A + one B):
test "$(grep -cE '^[AB]:' /workspace/b1_10_author_v3_perword/b1_10_contexts_v3_perword.txt)" -eq 12 \
    && echo "OK: 12 sentences" || echo "FAIL: not 12 sentences"
```

If any word is still `ESCALATE_TO_HUMAN` (or a subset was authored), **no** combined file is written — the
concatenation gate requires all six passing pairs.

### 5. Packet-aware audit

> **This step occurs ONLY after all six pairs have passed surface validation** (step 2) and been
> concatenated (step 4). It is a **reviewer procedure** (packet-aware), performed directly on the
> Git-tracked development context file per `B1_10_INDEPENDENT_CONTEXT_GENERATION_PROTOCOL.md` §7 and
> `B1_10_WORKFLOW_PROTOCOL_UPDATE.md` §3: context-independence → Tier-3 echo (lexical Jaccard + human
> near-paraphrase check vs. the pre-registered cap) → Tier-1/Tier-2 fairness → per-word decisions. There is
> no single "audit" binary; the audit is the reviewer applying those checks.

Programmatic aid — the tier-identifiability (style-only leave-one-out) diagnostic, which flags whether the
three tiers are separable by superficial style (chance = 0.333; well-above-chance = a style tell to fix
**before** any real run):

```bash
# after rebuilding the control-ext items with the new blind contexts, run the mock dry-check;
# it prints tier_style_loo_accuracy vs. chance (0.333). No judges, no verdict.
python3 run_b1_10_control_ext.py dry-check --seed 20260712
```

If a word fails the audit, regenerate **only that word-pair** via a fresh per-word blind job (step 1,
single `--words <w>`) — never a packet-aware edit — then re-audit. Repeat until all pass.

### 6. Judge run

> Runs **only after** the context set passes the packet-aware audit (step 5). Uses the **frozen** panel
> from `B1_10_OFFICIAL_JUDGE_PANEL_SPEC.md`: **J0 `meta-llama/Llama-3.1-8B-Instruct`, J1
> `meta-llama/Meta-Llama-3-8B-Instruct`, J2 `google/gemma-2-9b-it`**, greedy decoding, same panel for all
> three tiers. No Claude judge.

```bash
# gated real run: requires the single evidence-freeze declaration (step 7) AND a real
# Llama/Gemma judge backend supplied programmatically; refuses otherwise.
python3 run_b1_10_control_ext.py run \
    --decl /workspace/frozen/b1_10_control_ext_EVIDENCE_FREEZE_DECLARED.json \
    --seed 20260712 \
    --out  /workspace/b1_10_control_ext_run
```

The `run` subcommand deliberately refuses without both the evidence-freeze declaration and a real judge
backend (anti-circularity). **No regeneration after judges begin** — once the real run starts against the
frozen inputs, contexts/packets are not edited or re-authored; results are interpreted only against the
pinned inputs.

### 7. Final evidence package

> Assembled **once**, by the operator, only after the real run + statistics — per
> `B1_10_WORKFLOW_PROTOCOL_UPDATE.md` §4. There is no auto-assembler; the single freeze is a deliberate
> gated act.

```bash
# 1) compute sha256 of every artifact to be pinned (contexts, all three tier packets, control
#    hierarchy, judge-panel spec, prompts, seeds file, provenance, raw judge outputs, parsed
#    scores, statistics) and record them in the freeze declaration:
sha256sum \
    b1_10_contexts_v3_perword.txt \
    frozen/b1_10_control_ext_items.json \
    frozen/varna_polarity_table_v3.json \
    frozen/varna_polarity_bridge_v3.json \
    B1_10_OFFICIAL_JUDGE_PANEL_SPEC.md \
    provenance_*.json

# 2) create the SINGLE evidence-freeze declaration (JSON), pinning those hashes + panel + seeds
#    (same shape as frozen/b1_10_EVIDENCE_FREEZE_DECLARED.json, the microtest reference); this
#    declaration is what run_b1_10_control_ext.py run consumes in step 6.

# 3) verify manifest integrity by re-hashing every pinned artifact and diffing against the
#    declaration (any mismatch = the inputs changed after freeze -> stop):
sha256sum -c frozen/b1_10_control_ext_freeze_manifest.sha256
```

The freeze declaration + raw judge outputs + parsed scores + computed statistics + per-artifact hashes +
final report together form the **single** immutable evidence package. Development context versions are
never individually frozen.
