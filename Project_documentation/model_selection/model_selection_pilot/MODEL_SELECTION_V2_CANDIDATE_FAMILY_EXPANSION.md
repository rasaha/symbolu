# Model Selection V2 — Candidate-Family Expansion (pre-freeze)

*A narrowly scoped, controlled pre-freeze amendment to Version 2 viability. It expands the
set of **candidate** executable model families so the frozen ≥3-family gate can be met; it
is **not** an experiment redesign. It is registered **before** the registry is frozen and
**before** any development-pilot or shadow outcome has been observed.*

**Lineage:** V1 (UNRESOLVED, blocked) → V2 amendment (re-bind to executable endpoints) →
V2 viability (Anthropic/Claude + Google/Gemma executable; Gemini a distinct family but
non-executable on an exhausted free-tier project) → **this expansion** (add Qwen as a
candidate family to satisfy ≥3 executable families).

---

## Declarations

1. **Qwen is added as a candidate model family.**
2. **Alibaba Cloud Model Studio is added as a candidate execution provider** (serving
   provider), distinct from the model developer (Alibaba/Qwen team) and the model family
   (Qwen).
3. **Gemini remains an eligible, experiment-owner-ruled distinct family, but is currently
   non-executable** — the governing project/key is on an exhausted free-tier Gemini quota
   (billing not active; verified via `-FreeTier` quota IDs). It is not enabled in the
   registry until it executes.
4. **Qwen counts toward the family gate only after a successful real inference** (valid
   text returned). Model-list enumeration alone does not qualify it.
5. **This expansion occurs before registry freeze and before any development outcomes are
   inspected.** No pilot or shadow result exists or has been observed.
6. **No scientific methodology changes are authorized** by this amendment.
7. **Unchanged and immutable:** the routing protocol and logic, the utility function, the
   hard quality gates, the corpus and dev/shadow split, the scorers, the thresholds, the
   statistical methodology and multiplicity handling, the family-count rule, the
   commercial gates, and the spend caps. This amendment touches only the **candidate set
   of executable families/providers**, which is an execution-binding concern, not a design
   concern.
8. **Executability-test model selection basis:** a Qwen model is chosen for probing on
   **general-purpose text capability, API availability, pricing transparency, and protocol
   compatibility** — **not** on observed benchmark or corpus performance. Selection is
   documented before inference.
9. **Kimi is a conditional fallback only:** it may be considered **only if** the Qwen path
   is conclusively classified as unavailable. Qwen and Kimi are **not** both tested merely
   to maximize family count.
10. **Freeze discipline:** once one additional qualifying family executes and the viability
    gates pass (≥2 providers, ≥4 models, ≥3 executable families), the **minimum compliant
    registry** is frozen **before** any pilot outcome is observed.

## Candidate family / provider ledger (post-expansion)

| Family | Serving provider | Model developer | Executable now? |
|---|---|---|---|
| Claude | Anthropic | Anthropic | **Yes** (verified) |
| Gemma | Google (Generative Language API) | Google | **Yes** (verified) |
| Gemini | Google (Generative Language API) | Google | No — free-tier quota exhausted |
| **Qwen** | **Alibaba Cloud Model Studio** | Alibaba / Qwen team | **Pending** — counts only after real inference |
| *(Kimi)* | *(Moonshot)* | *(Moonshot)* | *fallback only if Qwen unavailable* |

## Viability gate (unchanged rule; recomputed on Qwen execution)

- ≥2 executable providers · ≥4 executable models · **≥3 distinct executable families**.
- Currently 2 executable families (Claude, Gemma). A successful Qwen inference makes it 3
  (Claude, Gemma, Qwen) → **V2 VIABLE**, at which point the minimum compliant registry is
  built and frozen.

*No credentials or account identifiers appear in this document.*
