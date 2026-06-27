# Symbol-U as an API-Level Control Protocol — Architecture Review + Pilot

**Final question:** *Is Symbol-U better treated as an external API-level control
protocol than as an internal neural architecture?*

**Two-part answer, kept separate on purpose:**

1. **As an engineering layer: YES — external is the right layer.** Controlling a
   frozen modern LLM through structured context is the correct, platform-aligned
   pattern; the internal-neural integrations were fighting the platform. So
   "external protocol" > "internal neural module" as an *engineering decision*.
2. **For Symbol-U's value: NO — the API framing does not rescue it, and arguably
   exposes the emptiness more clearly.** A JSON packet sent over the API is just
   tokens; its effect is fully mediated by the **natural-language meaning of its
   fields**. The actionable steering lives in the `response_policy` (tone/avoid/
   prefer) — which is plain instruction wearing JSON syntax. The `symbolu_state`
   ontology only helps insofar as the model understands Sanskrit terms, where they
   are vaguer and higher-variance than plain English, and adds **~4× the token
   cost** for the same actionable content.

**Environment limit (decisive):** the core question — *does a real LLM follow a
Symbol-U JSON packet better than plain NL instruction?* — is empirical about a
real model's instruction-following. In this sandbox **no LLM API key is available**
(`api.anthropic.com` is reachable but returns `authentication_error: x-api-key
header is required`; the harness's session OAuth token is not a scriptable key and
must not be repurposed). So the decisive adherence arm **cannot run here.** The
harness is built and wired to run it the instant a key exists (§Commands).

---

## 1. Architecture review (the substance)

### 1.1 What an "API control packet" actually is
When you send `{"symbolu_state": {...}, "response_policy": {...}}` to an LLM, the
model reads it **as tokens in context** — there is no privileged control channel.
This collapses the question to: *does expressing control intent as a Symbol-U JSON
packet produce better adherence than expressing the same intent as plain
instruction?* Everything below follows from that.

### 1.2 The packet decomposes — and only one half does work
- **`response_policy`** (`tone: calm`, `avoid: speculation`, `prefer: clarity`) is
  **natural-language instruction in JSON clothing.** It steers exactly to the
  extent NL instruction steers. This half carries the signal.
- **`symbolu_state`** (`guna: sattva`, `vritti: pramana`, `kosha: manomaya`) is the
  ontology. The model can only act on it via its pretraining knowledge of those
  Sanskrit/yoga terms — where understood, they are **looser, higher-variance**
  proxies for plain words like "calm/clear"; where not understood, they are
  ignored or loosely pattern-matched.

### 1.3 The translation step is the tell
Producing `response_policy` from `symbolu_state` requires a fixed table
(sattva → calm/clear/grounded). **That hand-authored table is the thing doing the
work** — it is ordinary instruction authoring. Symbol-U is a *label* on a control
instruction a human wrote. The ontology contributes nothing the table author isn't
already contributing in English.

### 1.4 The one genuinely different mode: rerank/refine
Best-of-N with a Symbol-U *scorer* is **not** prompting — it is a real
inference-time control method (classifier-guidance family). It is the most
defensible mode. But its value equals the **scorer's** quality, and prior work
established Symbol-U scoring is **phonological/weak**; a sentiment scorer or the
LLM's own self-critique will beat it as a semantic/affect judge. Worth testing
hardest, low prior of winning.

### 1.5 Why this is the same finding as the neural pilots, relocated
The neural controllability pilot found **vacuous controllability** (any separable
code steers; the ontology is a basis choice). At the API level the analogue is:
**any packet whose `response_policy` names the target tone steers; the ontology
fields are inert.** Information theory, control theory, and now the API framing
converge on the same deflation by independent routes.

---

## 2. Pilot design (isolates the ontology's contribution)

Seven arms, each a control message prepended to the user prompt; identical LLM;
arms differ only in the control structure. Built in `packets.py`.

| arm | content | isolates |
|---|---|---|
| `none` | — | baseline |
| `nl_instruction` | plain-English policy only | ordinary prompting |
| `symbolu_json` | `symbolu_state` ONLY (ontology, no NL) | can the ontology alone steer? |
| `hybrid` | `symbolu_state` + `response_policy` | full packet |
| `sentiment_json` | `response_policy` ONLY (NL fields in JSON) | policy without ontology |
| `random_json` | random valid ontology + random policy | does any JSON help? |
| `shuffled_symbolu` | ontology values corrupted, **policy kept correct** | does ontology CONTENT matter? |

**Decisive contrasts:** `symbolu_json` vs `nl_instruction` (ontology vs prompting);
`hybrid` vs `sentiment_json` (does ontology add over policy-only?); `hybrid` vs
`shuffled_symbolu` (does the ontology's content matter at all?).

Required prompt set spans tone-sensitive situations (a frustrated user, bad
results, breaking news to a team) each with a paraphrase (stability metric).

## 3. Offline results (runnable here — assumption-light)

### 3.1 Token cost (REAL, backend-independent) — `cli tokens`

| arm | control tokens (approx) | vs NL |
|---|---|---|
| nl_instruction | 26 | 1.0× |
| symbolu_json | 54 | 2.1× |
| sentiment_json | 61 | 2.3× |
| random_json | 103 | 4.0× |
| hybrid | 105 | **4.0×** |
| shuffled_symbolu | 105 | 4.0× |

**The full Symbol-U packet costs ~4× the tokens of plain instruction for the same
actionable content.** This is a real, permanent cost (latency + price + context
budget) that the ontology must *overcome*, not merely match, to be worth using.

### 3.2 Redundancy structure (analytic)
Both `symbolu_state` and `response_policy` are **deterministic functions of the
same target axis.** They are redundant by construction; one is recoverable from the
other via the fixed table. No information is added by carrying both — only tokens.

### 3.3 Mock adherence — PLUMBING-ONLY (not evidence)
The offline `mock` LLM keys only on English tone words and ignores Sanskrit; it
therefore **encodes the null hypothesis by assumption** and cannot adjudicate the
question. Its run confirms the pipeline + metrics work (and illustrates the
prediction: `symbolu_json`-only scores 0, `shuffled_symbolu` scores like `hybrid`
because the kept `response_policy` carries the signal). These numbers prove
nothing about a real LLM and are labeled as such in the output.

## 4. Adversarial predictions for the real-LLM run (pre-registered)

When run with `--backend anthropic`:
- `symbolu_json` ≈ or **<** `nl_instruction` (ontology no better than plain words;
  likely worse + 2× tokens).
- `hybrid` ≈ `sentiment_json` (the ontology adds nothing over policy-only).
- `shuffled_symbolu` ≈ `hybrid` (ontology **content** doesn't matter when the
  policy is correct).
- `random_json` steers whenever its random `response_policy` happens to name a
  tone — i.e., the *policy*, not the ontology, predicts adherence.
- **Plain `nl_instruction` is the value-for-tokens winner.**
The one place to watch for a surprise: rerank/refine (not in this minimal pilot) —
build it only if §5's results defy these predictions.

## 5. Commands to run the decisive arm (needs API access)

```bash
export ANTHROPIC_API_KEY=sk-ant-...      # a real key (absent in this sandbox)
export PYTHONPATH=$(pwd)

# decisive adherence comparison on a real LLM
python -m symbolu_neural.api_control_protocol.cli run --backend anthropic

# offline pieces (runnable anywhere)
python -m symbolu_neural.api_control_protocol.cli tokens     # token-cost table
python -m symbolu_neural.api_control_protocol.cli packets    # inspect each arm's message
python symbolu_neural/api_control_protocol/tests/test_api.py # machinery tests
```
To upgrade evaluation: pass a judge LLM to `evaluator.JudgeAdapter` (tone-match /
clarity / fluency 1-5) and add a human spot-check on ~30 outputs.

**Pass condition (pre-registered):** Symbol-U JSON must beat (a) plain
`nl_instruction`, (b) `sentiment_json` (policy-only), and (c) `shuffled_symbolu`,
on a judge-confirmed tone axis — *and* justify its ~4× token cost. Failing any
⇒ Symbol-U adds nothing over ordinary prompting at the API layer.

## 6. Required reporting — direct answers

- **Does Symbol-U JSON help beyond normal NL prompting?** Not testable offline
  here; predicted **no** (and it costs ~4× the tokens). Decisive run needs an API key.
- **Does the structured ontology matter?** By construction `response_policy` is
  recoverable from `symbolu_state`; the `shuffled_symbolu` arm is designed to show
  content-invariance. Predicted **no**.
- **Do random/shuffled packets work just as well?** Predicted **yes**, whenever
  they carry a valid `response_policy` — the policy, not the ontology, does the work.
- **Is this more promising than internal neural integration?** As an **engineering
  layer, yes** (right layer, frozen model, no training, interpretable, debuggable).
  As a vindication of **Symbol-U specifically, no** — it relocates the same
  deflation (ontology is an arbitrary label on a hand-authored instruction) to a
  layer where it also costs 4× the tokens.

## 7. Recommendation

If you pursue the API direction, pursue it as **plain structured prompting** (a
fixed `response_policy` schema), which is a real, mundane engineering win — and
**drop the `symbolu_state` ontology**, which adds tokens and ambiguity but no
demonstrated control. Reserve one further experiment for **rerank/refine** only;
it is the single mode that is not reducible to prompting. Everything else here
predicts that, at the API layer, Symbol-U is dominated by simply telling the model
what you want in English.
