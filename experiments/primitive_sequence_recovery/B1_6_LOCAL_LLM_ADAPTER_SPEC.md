# B1.6 — Local LLM Adapter Specification

**Status:** Adapter spec (docs). Describes `b1_6_llm_adapter.py` + its integration into
`run_b1_6_pilot_generation.py`. **Mock-tested only. No real generation run. No external API call. No judging. No
evidence freeze. No `GENUTILITY_*` label.**
**B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b remains blocked. Track B remains blocked. Structure, not
validated meaning.**

**Readiness label: `B1_6_LOCAL_LLM_ADAPTER_READY_MOCK_TESTED`.**

Modeled on the B1.1 run pattern (`run_b1_1_generation.py`: `TransformersAdapter` / `MockAdapter` /
`_gen_with_retry` / `model_access_readiness`). Reuses that shape; does not copy obsolete/unsafe code.

---

## 1. Adapter interface

`generate(prompt: str, settings: GenerationSettings) -> str`. `GenerationSettings` fields: `model_id`,
`revision`, `backend`, `temperature`, `top_p`, `max_tokens`, `seed`, `timeout_s`, `max_attempts`, `base_url`
(local server only). `settings.metadata()` returns the recordable subset (**excludes `base_url`** so endpoint
hosts are not written to manifests).

## 2. Backends

- **`transformers`** (`TransformersAdapter`) — lazy-loads a frozen model at a frozen revision on a CUDA host;
  user-turn only, no system prompt; `set_seed` per call; `do_sample` with the frozen decode settings.
- **`openai_compat_local`** (`OpenAICompatLocalAdapter`) — POSTs to a **local** OpenAI-compatible server
  (`base_url`, e.g. a local vLLM). Talks only to that local address.
- **`fake`** (`FakeAdapter`) — deterministic, NO model/network; produces well-formed output by default (and
  malformed on request) for tests.

`model_backend_readiness()` reports torch/CUDA/transformers availability **without touching the network**; the
CLI **refuses** a transformers run when CUDA is unavailable (as in this environment).

## 3. B1.1 pattern reused

Model-load-at-revision, per-row seed, frozen decode settings, retry-with-backoff, a mock adapter for local CI,
and a readiness gate that refuses off a model-access host — all mirror B1.1. New here: output-format validation
tuned to the B1.6 Title/Interpretation/Reflection/Caution schema, and the two-mode (full vs exploratory) freeze
gate.

## 4. CLI integration

`run_b1_6_pilot_generation.py`:
- `--mock` — unchanged deterministic placeholder path.
- `--local-model <id_or_path>` — transformers backend.
- `--base-url <url>` — local OpenAI-compatible backend.
- `--adapter-config <json>` — a `GenerationSettings` JSON.
- `--mode {pilot_generation, exploratory_10_sample_generation_probe}` — must match the declaration mode.
- `--limit-items N` — deterministic balanced subset (e.g. 10 for the probe).
- `--item-ids ...` — explicit deterministic subset.

Real generation still requires a matching operator evidence-freeze declaration; the CLI refuses without one, and
refuses a transformers run without CUDA.

## 5. Exploratory vs full modes

- **Exploratory** (`exploratory_10_sample_generation_probe`, `--limit-items 10`): 10 balanced targets × 5 arms =
  50; run manifest `run_label = B1_6_10_SAMPLE_EXPLORATORY_GENERATION_PROBE`, `subset = true`. **Does not
  masquerade as the full pilot** — a pilot-mode declaration cannot authorize it, and vice versa (mode-matched
  gate).
- **Full pilot** (`pilot_generation`): 24 × 5 = 120.

## 6. Output-format validation + retry

Each real generation is checked for the four required sections (in order) and a rough Interpretation word-count
bound. On failure the adapter retries up to `max_attempts` (frozen), then records `format_invalid` (or `error`
on exception) in the manifest and **omits** the output from the judge-visible package. **Output is never edited
to "improve" or force validity.**

## 7. Blinding preserved

Real outputs are written **only** through the existing `make_judge_visible` path (guarded by `assert_blind`):
judge-visible packages carry no arm name, prompt, scaffold metadata, Symbol-U/KCPR labels, or hidden mapping;
hidden metadata stays a separate file.

## 8. Run manifest

Records: `generator_meta` (backend + model_id/revision/temperature/top_p/max_tokens/seed), `declared_freeze_mode`,
`run_label`, `subset`, `n_targets`/`n_arms`/`n_prompts`/`n_success`/`n_failures` (+ failure reasons), `item_ids`,
`frozen_input_hashes`, `declaration_sha256`, `judging_performed: false`, `b1_4b_prime_status`.

## 9. Tests

`test_b1_6_llm_adapter.py` (fake adapter only) + additions to `test_run_b1_6_pilot_generation.py`: validation
(well-formed/malformed/missing/out-of-order/empty), retry (ok / format_invalid-no-edit / exception→error /
no-validation-raw), readiness (no network), settings metadata excludes base_url, backend factory, mock still
works, real refuses without declaration, wrong-mode refuses, exploratory requires exploratory declaration, full
requires pilot mode, fake adapter 10×5 and 24×5, malformed→failures + empty judge-visible, real requires
adapter/generator, balanced subset covers all six strata. **No external API in any test.**

## 10. Guardrails

No real generation run; no external API call; no judging; no evidence freeze; no generated outputs committed;
no semantic-truth claim; no `ONTOLOGICAL_SIGNAL`; no `GENUTILITY_*` label; KCPR caveat
`THEORY_NONCANONICAL_INPUT_POLARITY` remains active; **B1.4b′ remains `NULL_RETURN_BOTTOM`**; original B1.4b
blocked; Track B blocked. **Structure, not validated meaning.**

---

> B1.6 local LLM adapter integrated and mock-tested only. No real generation run. No judging. No evidence freeze.
> No GENUTILITY terminal label. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains blocked. Track B remains
> blocked. Structure, not validated meaning.
