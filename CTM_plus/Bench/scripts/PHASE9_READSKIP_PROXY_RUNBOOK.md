# Phase 9 — read-skip proxy runbook (`phase9_readskip_proxy.sh`)

> **Purpose:** decide whether the intra-sequence read-skip kernel is worth
> building — *before* building it — by measuring Step-0's two IFs (throughput
> win + quality cliff) on a model whose sliding-window attention already IS a
> fixed intra-sequence read-skip. GPU pod, ~$0.30–0.50.

## The idea in one line

Sliding-window attention (SWA) attends only the last `W` tokens and physically
skips older reads = a fixed StreamingLLM read-skip. Toggle it on/off on the same
model, on a long needle-in-haystack, and read off:
- **Throughput:** SWA-on decode tps vs SWA-off (full attention) at long context.
- **Quality:** needle hit-rate by depth. A needle at depth-fraction `d` in an
  `L`-token context is inside the window iff `(1-d)·L ≤ W`.

## Run

```bash
cd /workspace/symbolu/CTM_plus
source /workspace/venv-vllm/bin/activate
# Mistral-7B-v0.1 has native sliding_window=4096 and is the default model:
huggingface-cli download mistralai/Mistral-7B-Instruct-v0.1 --exclude "*.pth"   # ~14GB, one-time
bash Bench/scripts/phase9_readskip_proxy.sh
```

Env knobs: `MODEL`, `WINDOW` (4096), `CONTEXT_TOKENS` (16000), `DEPTHS`
(`0.1,0.5,0.8,0.95`), `ITEMS`, `GPU_UTIL`. CPU self-test: `python
Bench/scripts/phase9_readskip_proxy.py --selftest`.

## ⚠ Two caveats that gate trusting the result

1. **The SWA toggle must actually take effect.** The script forces the window via
   vLLM `hf_overrides={"sliding_window": W or None}`. The wrapper runs a **cheap
   `--check-window` preflight first** and prints `effective_sliding_window` for
   both settings. **If the two are identical, the override is being ignored on
   this vLLM build — STOP**; the proxy is invalid. Fallback: compare
   Mistral-v0.1 (window 4096) vs Mistral-v0.2 (window null) as two models
   (architecture-matched, config differs) — confounded but workable.
2. **It is a PROXY, not the real mechanism.** SWA is a *fixed* window (recent
   only); real attention-guided read-skip would also keep sinks + high-attention
   tokens. So the proxy's quality is a **lower bound** — it will miss early needles
   that attention-guided retention would save. That is the point: see the gate.

## The kernel go/no-go (what each outcome means)

| outcome | meaning | decision |
|---|---|---|
| read-skip **faster** AND deep (inside-window) needles still hit, but early/mid **miss** | the throughput lever is real; the misses are exactly the H2O loss that sinks+high-attention retention would rescue | **BUILD the attention-guided kernel** — the proxy shows headroom the fixed window leaves on the table |
| read-skip **faster** AND quality holds at ALL depths | suspicious "free lunch" — almost certainly the window didn't apply; check `effective_sliding_window` | re-verify before concluding |
| read-skip **not faster** (`delta ≤ 0`) | even a perfect fixed skip buys no throughput at this context | **DO NOT build** — lengthen context (Step 0 said the prize grows with length) or stop |
| read-skip misses even **late/inside-window** needles | proxy/model/task broken | fix before concluding |

This converts Step-0's modeled "~1.9× IF quality survives" into a *measured*
quality cliff + a *measured* throughput delta — the cheapest possible gate on a
multi-session kernel build.
