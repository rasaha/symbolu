# Naming evaluation harness

Evaluates whether the frozen canonical Symbolic Profile improves naming vs strong non-symbolic
baselines. Four arms (identical framing; only the conditioning differs):

- **A** baseline (brief + constraints only)
- **B** full Symbolic Profile
- **C** random-symbolic control (a real profile from a *different* seed, length-matched)
- **D** minimal summary (varṇas + dominant poles)

## Deterministic metrics (no LLM needed)

```bash
python run_eval.py          # token cost, determinism, injected honesty, arm distinctness, ablations
python test_naming_eval.py  # 12/12
```

## Live validation with a real LLM (Mistral / Qwen / OpenAI-compatible / Anthropic)

Configure **any one** provider (two+ judges recommended for cross-model disagreement):

```bash
# Mistral
export MISTRAL_API_KEY=...            # → mistral:mistral-large-latest

# Qwen (DashScope, OpenAI-compatible, international endpoint)
export DASHSCOPE_API_KEY=...          # → qwen:qwen-max   (or QWEN_MODEL=qwen2.5-72b-instruct)

# Any OpenAI-compatible endpoint (OpenRouter / Together / vLLM / Ollama / local)
export LLM_BASE_URL=https://openrouter.ai/api/v1  LLM_API_KEY=sk-...   # → compat:<model>
export LLM_MODEL=qwen/qwen-2.5-72b-instruct

# OpenAI / Anthropic
export OPENAI_API_KEY=...             # → openai:gpt-4o-mini
export ANTHROPIC_API_KEY=...          # → anthropic:claude-opus-4-8
```

Check connectivity, then run:

```bash
python llm_client.py --ping

# full run, auto-picking configured providers as gen + judges
python run_live_eval.py

# explicit models; small cheap smoke run with explanation-honesty
python run_live_eval.py --gen-model qwen:qwen-max \
    --judge-models mistral:mistral-large-latest,qwen:qwen-max --limit 6 --explanations
```

Output: `naming_eval_live_results.json` + console summary — pooled per-arm quality (1–5) with 95% CIs,
paired **B−A / B−C / B−D** effect sizes (Cohen's d) + win/tie/loss counts, deterministic constraint
satisfaction on the real names, cross-judge disagreement, and token cost.

## Interpreting results (evidence discipline)

- The **B vs C** comparison is the key test: if B ≈ C, any apparent lift is *same-size structured text*,
  not the symbolic content.
- The burden of proof is on PSE: declare benefit only if **B beats A _and_ C** by a statistically and
  practically meaningful margin under blinded judging.
- LLM judging is **not** equivalent to human validation — always report cross-judge disagreement and
  treat results as indicative. Nothing is fabricated when no provider is configured.
