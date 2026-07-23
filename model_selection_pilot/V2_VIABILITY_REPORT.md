# Version 2 — Pre-Execution Viability Report

*Produced before any freeze. Verification date context: 2026-07-23. Per the V2
procedure: if the ≥4 model / ≥2 provider / ≥3 family requirement cannot be met, STOP and
do not create a frozen V2 manifest. **That condition is triggered: V2 is NONVIABLE here.***

---

## Fresh viability re-check — 2026-07-23 (Google credential supplied) — SUPERSEDES the unauthenticated-Google findings below

A Google Gemini API credential was supplied and verified. This section reflects the
**verified** state and supersedes the earlier "Google unauthenticated" assessment in the
sections below; the earlier text is retained for the audit trail.

**Verified by real inference (a model counts only after a successful minimal inference):**

| Provider | Model | Executable? | Evidence |
|---|---|---|---|
| Anthropic (Claude) | `claude-haiku-4-5-20251001`, `claude-sonnet-4-5-20250929` | **YES** | real inference (prior check) |
| Google (**Gemma**) | `gemma-4-31b-it` (1122 ms), `gemma-4-26b-a4b-it` | **YES** | real inference this session |
| Google (**Gemini**) | `gemini-2.0-flash`, `-flash-lite`, `gemini-2.5-pro` | **NO — billing/quota (429)** | "You exceeded your current quota, check your plan and billing" |
| Google (Gemini) | `gemini-2.5-flash` | **NO — 404** | model not available to account/version |

Google auth succeeded (41 models advertise `generateContent`); the **only executable
Google text lineage is Gemma** — all Gemini models are quota/billing-blocked (429) or 404.

**Updated gate status:**

- **≥2 providers — NOW MET** (Anthropic + Google, both executable by real inference).
- **≥4 models — reachable** (2 Claude + 2 Gemma).
- **≥3 distinct families — NOT MET.** Exactly **two** executable families: **Claude** and
  **Gemma** (unambiguously distinct lineages; no stretching). Gemini — the only candidate
  third — is **not executable** (billing/quota), and a model counts only after a
  successful inference. (Even if Gemini billing were enabled, whether Gemini and Gemma
  count as two *distinct* families or one shared Google lineage is a definitional call the
  experiment owner must make; the robust path to a third family is a genuinely distinct
  architecture from a distinct provider.)

**Updated verdict: STILL NONVIABLE — now solely on the ≥3-distinct-family requirement
(verified: only Claude + Gemma are executable). STOP stands: no V2 manifest is frozen and
no paid pilot runs.** Failure category for Gemini: **rate-limit/billing restriction**.

**To make V2 viable now:** add a genuinely distinct **third** model family that is both
reachable and executable — e.g. enable billing on the Gemini project **and** obtain the
owner's ruling that Gemini is a family distinct from Gemma; or provide a reachable,
executable distinct-architecture provider (OpenAI GPT, a Bedrock/Llama endpoint, or
Mistral — currently all proxy-denied or uncredentialed). Only ~$0.0004 of verification
inference was spent (Anthropic + Gemma); Gemini 429s were free. Keys were confined to the
session scratchpad, never committed, and deleted after use.

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
one. Executable families here: **{Claude}** only. Google is network-reachable but
unauthenticated, so its account-accessible models, executable model IDs, and qualifying
architectural lineages are **unknown** (not enumerated or verified by real inference). It
may contribute one or more lineages; this has not been established.

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
2. **Only one executable family** (Claude). Fails mandatory **≥3 distinct families** in
   the current (unauthenticated-Google) state. Whether it can be met under valid Google
   credentials is **unknown**: Google's executable models and qualifying family count have
   not been enumerated, so impossibility is **not** established here.
3. Google reachable but **uncredentialed**; OpenAI/Bedrock/others **proxy-denied or
   invalid**.

## Viability verdict — STOP

**Currently NONVIABLE** because only one provider and one distinct model family are
executable. Google is reachable but unauthenticated, so its executable models and
qualifying family count are unknown; a valid Google credential would require a fresh
viability check. If Google contributes only one qualifying lineage, a third reachable
model family would still be required. Per the V2 procedure, **no V2 capability registry, no V2 provider-binding manifest, and
no frozen V2 run manifest are created, and no paid pilot is executed.** Only free /
least-cost verification inference was performed (~$0.0002 total, on Anthropic, for
executability proof); keys were confined to the session scratchpad (outside the repo),
never committed, and deleted after use.

## What would make V2 viable (actionable)

- The cheapest path to a **second provider** is a **valid Google credential** (its
  endpoint is already network-reachable). This requires a **fresh viability check**:
  enumerate Google's account-accessible models and verify executability by real inference,
  then count qualifying architectural lineages. If Google contributes ≥2 qualifying
  lineages the ≥3-family bar may be reachable via Anthropic + Google; if it contributes
  only one, a **third** reachable model family would still be required.
- A third distinct family, if needed, requires an environment whose network policy permits
  another distinct-architecture provider endpoint (e.g. OpenAI, Bedrock/Llama, or Mistral)
  with valid credentials.
- Alternatively, run in an environment matching V1's frozen providers (Anthropic +
  OpenAI + Bedrock) with valid credentials and network access.

Until then the falsification verdict stays **UNRESOLVED**; interim default unchanged
(**Category 2 — retain static routing**); definitive recommendation **deferred**.
