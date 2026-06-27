# Symbol-U API Control Protocol (experimental / isolated)

**Status: EXPERIMENTAL.** A small isolated investigation: is Symbol-U better used
as an **external structured control packet sent to an LLM via the API** than as an
internal neural module? **No weights changed, no model trained, no decoder built.**

Read the architecture review + results in **`API_CONTROL_PROTOCOL_REPORT.md`**.

## The question

A JSON control packet sent to an LLM is just tokens in context. So the real
question is: does a Symbol-U packet steer better than plain natural-language
instruction — and does the Sanskrit `symbolu_state` ontology add anything over the
plain-English `response_policy` it translates to?

## Arms (in `packets.py`)

| arm | what it sends |
|---|---|
| `none` | nothing (baseline) |
| `nl_instruction` | plain-English instruction (ordinary prompting) |
| `symbolu_json` | `symbolu_state` ONLY (the ontology) |
| `hybrid` | `symbolu_state` + `response_policy` (full packet) |
| `sentiment_json` | `response_policy` ONLY (NL fields in JSON) |
| `random_json` | random valid ontology + random policy |
| `shuffled_symbolu` | ontology values corrupted, policy kept correct |

Decisive contrasts: `symbolu_json` vs `nl_instruction`; `hybrid` vs
`sentiment_json`; `hybrid` vs `shuffled_symbolu`.

## Hard environment limit

The decisive arm needs a **real LLM** (does it follow the packet?). In this
sandbox **no LLM API key is available** (`api.anthropic.com` is reachable but
requires `x-api-key`; the session OAuth token is not a scriptable key). So
`--backend anthropic` cannot run here. The `mock` backend is a deterministic
instruction-follower simulator that **encodes the null by assumption** — it tests
plumbing + metrics ONLY and proves nothing about the hypothesis.

## Commands

```bash
export PYTHONPATH=$(pwd)

python -m symbolu_neural.api_control_protocol.cli tokens          # token cost (offline, real)
python -m symbolu_neural.api_control_protocol.cli packets         # inspect each arm's message
python -m symbolu_neural.api_control_protocol.cli run --backend mock   # plumbing only

# decisive run — needs a real key (not present here). Pick a provider:
export ANTHROPIC_API_KEY=sk-ant-...
python -m symbolu_neural.api_control_protocol.cli run --backend anthropic
# or Mistral (hosted API = generation-only; or set MISTRAL_BASE_URL to an
# OpenAI-compatible server hosting Mistral open weights):
export MISTRAL_API_KEY=...
python -m symbolu_neural.api_control_protocol.cli run --backend mistral --model mistral-small-latest

python symbolu_neural/api_control_protocol/tests/test_api.py      # machinery tests
```

## What's already established offline

- **The full Symbol-U packet costs ~4× the tokens of plain NL instruction** for
  the same actionable content (real, backend-independent).
- `response_policy` and `symbolu_state` are both deterministic functions of the
  target axis → **redundant by construction**; carrying both adds tokens, not info.
- Predicted (needs API to confirm): the ontology adds nothing over plain
  prompting, and random/shuffled packets steer just as well via their policy field.

## Files

| file | role |
|---|---|
| `ontology.py` | axis → `symbolu_state` + `response_policy` tables, tone lexicon |
| `packets.py` | the 7 control-message builders + token estimate |
| `llm.py` | `anthropic` (real, needs key) + `mock` (offline, plumbing-only) clients |
| `evaluator.py` | offline tone-adherence proxy + token cost + LLM-judge adapter |
| `data.py` | tone-sensitive prompt set (+ paraphrases) |
| `pilot.py` / `cli.py` | orchestrator + CLI |
| `tests/test_api.py` | machinery tests |
| `API_CONTROL_PROTOCOL_REPORT.md` | architecture review + results + commands |

## Isolation

Self-contained; does **not** modify or depend on the older detector files or
`clean_softmax`. Nothing deleted.
