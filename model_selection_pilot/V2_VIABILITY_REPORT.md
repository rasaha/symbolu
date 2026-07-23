# Version 2 — Pre-Execution Viability Report

*Produced before any freeze. Verification date context: 2026-07-23. Per the V2
procedure: if the ≥4 model / ≥2 provider / ≥3 family requirement cannot be met, STOP and
do not create a frozen V2 manifest. **That condition is triggered: V2 is NONVIABLE here.***

---

## Reachable providers (network / proxy layer)

Tested by direct `CONNECT` through the enforced agent proxy (the proxy must not be
bypassed). Only two LLM provider endpoints are permitted:

| Endpoint | Network reachability |
|---|---|
| `api.anthropic.com` | **reachable** (proxy allowlist) |
| `generativelanguage.googleapis.com` (Google Gemini) | **reachable** (HTTP 404 to base, i.e. permitted) |
| `api.openai.com` | proxy-denied (403 CONNECT) |
| `api.mistral.ai` | proxy-denied (403 CONNECT) |
| `api.groq.com`, `api.together.xyz`, `api.cohere.ai`, `api.deepseek.com`, `openrouter.ai`, `api.x.ai`, `api.fireworks.ai` | all proxy-denied (403 CONNECT) |
| AWS Bedrock | credential invalid (`InvalidClientTokenId`) |

**At most two distinct-architecture providers are network-reachable here: Anthropic and
Google.**

## Executable models (reachable + valid credential + real inference succeeded)

A provider counts only after ≥1 model completes a real inference; a model counts only
after a minimum-cost inference succeeds.

| Provider | Model | Executable? | Evidence (real inference, 2026-07-23) |
|---|---|---|---|
| Anthropic | `claude-haiku-4-5-20251001` | **YES** | in=13 out=4 tok, 759 ms, $0.000033; returned id matches |
| Anthropic | `claude-sonnet-4-5-20250929` | **YES** | in=13 out=4 tok, 1527 ms, $0.000099; returned id matches |
| Google | (Gemini) | **NO** | endpoint reachable but auth `401` — no API key; `CLOUDSDK_AUTH_ACCESS_TOKEN` invalid |
| OpenAI / Bedrock / others | — | **NO** | proxy-denied or invalid credential |

**Executable providers = 1 (Anthropic). Executable distinct families = 1 (Claude).**

## Family classification (per the fixed operational definition)

Family = distinct pretraining lineage / base architecture; size/tier variants count as
one. Executable families here: **{Claude}** only. Google (Gemini) would be a second
family *if* credentialed, but no valid Google credential exists. No third
distinct-architecture family is even network-reachable.

## Verified pricing

Anthropic per-1M-token pricing used for cost math is **provider-published, not
live-verified this session** (no reliable pricing-endpoint access; flagged with
provenance, same discipline as the V1 registry). Cost figures above are computed from
billed token counts returned by the API (authoritative for tokens), multiplied by
published prices. Pricing must be live-verified before any real pilot.

## Cost / runtime projection (moot — not run)

Not computed for execution, because the configuration is nonviable. For reference, the
frozen corpus is 63 tasks (35 dev / 28 shadow); a full counterfactual at k=3 over ~4–5
models would be ~$30–40 typical / <$100 worst-case under the `$8`... (the configured
`PILOT_MAX_SPEND_USD=8.00` cap would itself need raising for the full protocol — a
separate pre-freeze decision, not taken because the run is blocked upstream).

## Adapter readiness

The Anthropic adapter path was exercised end-to-end against the live endpoint (auth,
request, response parsing, token/latency capture) — **ready**. A Google/Gemini adapter is
**not implemented** (V1 shipped Anthropic/OpenAI/Bedrock only); adding one would be a
listed, justified change requiring the same interface tests — deferred, since Google is
uncredentialed anyway. Tests: **17/17 pass**.

## Unresolved blockers

1. **Only one executable provider** (Anthropic). Fails mandatory **≥2 providers**.
2. **Only one executable family** (Claude). Fails mandatory **≥3 distinct families** —
   and this cannot be met in the current environment even with ideal credentials, because
   only two distinct-architecture providers (Anthropic, Google) are network-reachable.
3. Google reachable but **uncredentialed**; OpenAI/Bedrock/others **proxy-denied or
   invalid**.

## Viability verdict — STOP

**NONVIABLE.** The ≥4 models / ≥2 providers / ≥3 families requirement cannot be met.
Per the V2 procedure, **no V2 capability registry, no V2 provider-binding manifest, and
no frozen V2 run manifest are created, and no paid pilot is executed.** Only free /
least-cost verification inference was performed (~$0.0002 total, on Anthropic, for
executability proof); keys were confined to the session scratchpad (outside the repo),
never committed, and deleted after use.

## What would make V2 viable (actionable)

- The cheapest path to a **second provider/family** is a **valid Google Gemini API key**
  (its endpoint is already network-reachable) — but that yields only 2 families, still
  short of ≥3 under the strict definition.
- Meeting **≥3 distinct families** requires an environment whose network policy permits a
  **third** distinct-architecture provider endpoint (e.g. OpenAI or a Bedrock/Llama or
  Mistral endpoint) **and** valid credentials for ≥2 of the reachable providers.
- Alternatively, run in an environment matching V1's frozen providers (Anthropic +
  OpenAI + Bedrock) with valid credentials and network access.

Until then the falsification verdict stays **UNRESOLVED**; interim default unchanged
(**Category 2 — retain static routing**); definitive recommendation **deferred**.
