# B1.3 v3-Authoritative — Judge Model Capability Probe

## Scope

Capability probe only. **No EVIDENCE_FREEZE · no judge-facing packets for the real 371 comparisons · no
scoring · no study run · no v3 stimulus change · no threshold change · no lexicon edit · no v2 overwrite · no
prior-result reinterpretation.** Harmless **synthetic** probe prompts only (never real B1.3 items). Freeze
status unchanged: `FREEZE_REVIEW_V3_AUTHORITATIVE_READY_AWAITING_OPERATOR_CONFIRMATION`.
**Structure, not validated meaning.**

## 1. Reachable models (exact runtime findings)

**Credential / SDK state**
- No scriptable provider API key in env (`ANTHROPIC_API_KEY`, `OPENAI_*`, `GOOGLE_*`, `MISTRAL_*` — **none**).
- Anthropic auth is a **harness-managed OAuth token held in a file descriptor**
  (`CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR`), not a key usable from a standalone script.
- No LLM SDKs installed (`anthropic`, `openai`, `google.generativeai`, `mistralai`, `cohere`, `ollama` — all
  missing; `anthropic` is pip-installable but has **no usable credential**).

**Endpoint reachability (harmless unauthenticated `curl`)**
| endpoint | result | reading |
|---|---|---|
| `api.anthropic.com/v1/models` | **HTTP 401** | reachable, but needs the harness OAuth; **not scriptable** |
| `api.openai.com/v1/models` | connection error (000) | **unreachable** |
| `generativelanguage.googleapis.com/v1/models` | **HTTP 403** | reachable endpoint, **no access** |
| `api.mistral.ai/v1/models` | connection error (000) | **unreachable** |

**Only invokable judge path:** a **Claude subagent via the harness Agent tool** (tiers selectable:
Opus / Sonnet / Haiku / Fable). This is the *sole* callable model path — no standalone API, no second vendor.

**Synthetic compliance probe (Claude general-purpose subagent, Haiku tier, synthetic "widget" A/B item):**
the subagent **REFUSED** to emit the forced-choice letter — it treated the "answer with exactly one letter"
instruction as a suspicious embedded/override instruction and returned an explanation instead of `A`/`B`.
- `success`: **NO** (no parseable answer)
- `json/letter-output compliance`: **FAILED** (refused format)
- `parse_status` equivalent: **refused**
- Caveat: this refusal is an artifact of the **general-purpose subagent's guardrails**, not proof the Claude
  model is unable to judge; a dedicated judge agent with a clean judge system prompt via a credentialed API
  *might* comply — but no such credentialed path is available here.

## 2. Grouped by provider / family

| family / vendor | reachable? | scriptable? | notes |
|---|---|---|---|
| **Anthropic / Claude** | via harness only (401 on raw API) | **no** (OAuth in FD; only subagents) | single vendor; **generator-adjacent** (same family driving this session); synthetic probe **refused** format |
| OpenAI | no (conn error) | no | — |
| Google (Gemini) | endpoint up, **403** | no | no access |
| Mistral | no (conn error) | no | — |
| Cohere / Ollama / others | no | no | not present |

## 3. Does the reachable set satisfy the cross-family requirement?

**No.** Only **one** vendor family (Claude) is reachable at all, and it is only invokable via harness subagents
— which are (a) **single-vendor**, (b) **generator-adjacent** (same family as this session), and (c) in the
synthetic probe **did not comply** with the blinded forced-choice judge format. There is **no** second family
and **no** cross-vendor judge.

## 4. Implication for a proper evidence run

A proper evidence run needs a **stable, credentialed, format-compliant judge** — ideally ≥2 cross-vendor
families. This runtime provides **none scriptably**, and the single invokable path failed the synthetic
compliance probe. Therefore a real run should either:
- **wait for multi-family / credentialed judge access** (preferred — the design's cross-vendor,
  no-single-family-dominance requirement can then be met), **or**
- be explicitly **downgraded to a single-family pilot** *only if* a stable, compliant single-family judge
  configuration can first be established (a dedicated judge agent that reliably emits `A`/`B`) — which is **not**
  the case as of this probe.

Either way, **freeze must not be declared** until a stable judge instrument exists, because a run that returns
mostly `refused`/`invalid` would hit the scorer's invalid-rate cap → `LLM_OBJECT_MODULATION_INVALID_RUN`, and a
single-family result would trigger the single-family-dominance guard.

## 5. Recommendation

```
RECOMMENDATION: NOT_READY_NO_STABLE_JUDGE
```

No stable, credentialed, format-compliant judge instrument is available in this runtime: every provider API is
unreachable or unauthenticated (OpenAI/Mistral down, Google 403, Anthropic 401 with no scriptable key), and the
only invokable path (a single-vendor, generator-adjacent Claude subagent) **refused** the synthetic judge
format. This is not `READY_FOR_MULTI_FAMILY_FREEZE` (zero cross-family access) and not
`ONLY_SINGLE_FAMILY_PILOT_AVAILABLE` (the single family is not currently a *stable/compliant* judge — the
synthetic probe failed). If a dedicated, credentialed judge configuration is later established, this can be
revisited and possibly downgraded to a single-family pilot with a documented weak-blinding caveat.

## 6. Freeze status

**Unchanged.** `FREEZE_REVIEW_V3_AUTHORITATIVE_READY_AWAITING_OPERATOR_CONFIRMATION` (technical artifacts ready;
judge instrument **not** available). EVIDENCE_FREEZE **not** declared. No freeze status was changed by this
probe.

## 7. Final status block

```
document:                    B1.3 v3-authoritative JUDGE MODEL CAPABILITY PROBE (capability probe only)
reachable families:          Claude/Anthropic only (via harness subagents; raw API 401, no scriptable key)
cross-vendor families:       NONE (OpenAI unreachable, Google 403, Mistral unreachable)
scriptable judge API:        NONE
synthetic compliance probe:  FAILED (single-family Claude subagent refused forced-choice format)
cross-family requirement:    NOT satisfied
recommendation:              NOT_READY_NO_STABLE_JUDGE
freeze status:               UNCHANGED (READY_AWAITING_OPERATOR_CONFIRMATION); EVIDENCE_FREEZE not declared
ran/scored study items:      NO (synthetic widget probe only)
v3 stimuli / thresholds / lexicon / v2: UNCHANGED
prior nulls:                 PRESERVED (B1.1 LLM null; B1.2/B1.3 automated; scrambled≈real 0.967; Track G; Track F)
Track B:                     BLOCKED
ONTOLOGICAL_SIGNAL / Sanskrit privilege / truth: NONE
```

**Judge capability probe complete. No evidence freeze declared. Nothing run or scored. Track B remains blocked.
Structure, not validated meaning.**
