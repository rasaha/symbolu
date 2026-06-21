# C×R×S MATCH-Filter Wrapper — Design

> **Name:** *C×R×S MATCH-filter wrapper* (a.k.a. *CSR Match-Filter Wrapper*).
> This is **not** the full CSR field. It is a pairwise **(term, domain)** compatibility gate that
> constrains the answer-space of a base LLM. The LLM stays the token generator; the match-filter
> only **selects / rejects / reranks / rewrites** the frame it answers within.

## 1. Three things that must not be conflated

| Object | What it is | Shape |
|---|---|---|
| **MATCH-filter** (this doc) | pairwise term/domain compatibility | `MATCH(term, domain) = C × R × S` |
| **CSR field** (out of scope) | global coherence over `(Bhava, Context, Semantic, Resonance)` | a field, not a pairwise gate |
| **STL** (out of scope) | temporal `Signal → Transformation → Laya` | a trajectory, not a score |

The goal of this module is **only** the MATCH-filter. It does not revive the CSR field, STL,
governance/trust, or any generation-injection path. It is an API-mode wrapper (no logits required).

## 2. The formula

```
MATCH(term, domain) = C × R × S
```

| Symbol | Name | Question | Phonemic? |
|---|---|---|---|
| **C** | ontological allowance | *Can this concept fit this ontology lane at all?* | yes (from the 12D profile) |
| **R** | structural realization strength | *Is the phonemic/structural expression of the lane strong?* | yes (from the 12D profile) |
| **S** | external semantic coherence | *Does ordinary, non-phonemic meaning agree?* | **no — firewall** |

Multiplicative means **any factor near zero vetoes the match**. That is the whole point: C, R, S are
*gates in series*, not a weighted vote.

### The phonemic boundary (critical)
```
term  ──phonemic──▶ 12D ontological profile ──┬─▶ C  (allowance vs ontology rules)
                                              └─▶ R  (cosine vs domain 12D template)

term/domain DEFINITIONS ──non-phonemic──▶ S  (semantic firewall, external meaning)
```
The 12D profile is **not the meaning**. `doctor`'s profile is a phonemic-ontological *realization*,
not "healing." **S** — computed from external definitions/taxonomy/embeddings, never from sound —
is what confirms or vetoes meaning. **Phonemes alone never determine meaning.**

## 3. C, R, S — exact definitions

**12D layers** (same order everywhere):
`Potential, Identity, Execution, Structure, Cognition, Agency, Reasoning, Purpose, Witness, Unifying, Integration, Absolving`.

- **C — `compute_constraint(term_vec, domain)`**
  ```
  required_score  = mean(term_vec[domain.required_high])
  blocked_score   = mean(term_vec[domain.blocked_high])   # 0 if none blocked
  blocked_penalty = 1 − blocked_score
  consistency     = on_target / (on_target + off_target)   # mass on required+allowed vs elsewhere
  C = clip( required_score × blocked_penalty × (0.5 + 0.5×consistency), 0, 1 )
  ```
  C is **permission**: it falls when a domain's *blocked* layers are lit, or its *required* layers are dark.

- **R — `compute_realization(term_vec, domain)`** — *group-aware* (see §4a)
  ```
  R = Σ_g w_g · group_match_g  −  pen_w · mean(term[blocked_lanes])
  ```
  R is **strength**: how well the realized profile points along the lane. Flat 12D cosine was
  non-discriminative (all-positive templates ⇒ cosine 0.96–0.999); group-aware R compares per-family
  emphasis weighted per domain and penalises blocked lanes, so R now separates domains by *which*
  family of structure is active.

- **S — `compute_semantic_coherence(term, domain)`** *(non-phonemic firewall)*
  ```
  S = semantic_similarity(definition(term), definition(domain))
  ```
  Computed from **words/definitions/taxonomy/embeddings** — never from phonemes. This is the firewall
  that prevents phoneme-only claims. The backend is a pluggable `SemanticCoherenceAdapter`: term text
  via a `definition_provider`, similarity via `embed_fn` (real embeddings in production; a built-in
  deterministic hashing embedder offline; explicit `lexical` mode for the simplest tests). It needs
  **no per-word dictionary** — see §5b. Production should use sentence embeddings or RAG metadata.

## 4. Zero-kill (veto) rules and thresholds

Decisions are evaluated **in this order** (a veto short-circuits):

```
if C < reject_C  →  reject_ontological      # impossible mapping
if S < reject_S  →  reject_semantic         # firewall: phonemic overreach blocked
if MATCH ≥ primary_match    →  primary
if MATCH ≥ secondary_match  →  secondary
else                        →  weak          # ignore unless user asks
```

Default thresholds (calibrated to the C×R×S product scale on a real embedder; see
`RESULTS_MATCH_FILTER_EVAL.md`):

```python
reject_C = 0.20
reject_S = 0.20
primary_match = 0.20      # F1-optimal on the real-embedder MATCH distribution (was 0.60, miscalibrated)
secondary_match = 0.05    # separates true-secondary (~0.086) from unlabeled 'other' (~0.038)
rewrite_if_answer_alignment_below = 0.40
```

The **S veto sits above MATCH magnitude**: a high C and R can never rescue a semantically incoherent
mapping. The **C veto** rejects ontologically impossible domains — but is **S-gated**: because C's
blocked-lane penalty is computed from the *phoneme* profile, a strong semantic match (high S)
suppresses it so C does not veto a semantically-correct domain on a phoneme false alarm (e.g.
`fire→heat`). When S is low, the full penalty stands and C still vetoes impossible domains
(`doctor→fruit`).

## 5. Wrapper pipeline (Mode A — API, no logits)

```
User query
  → A. extract terms / candidate concepts
  → B. propose candidate domains
  → C. score MATCH = C×R×S for each (term, domain)
  → D. build trace → primary / secondary / rejected domains
  → E. build CSR-selected prompt frame
  → F. LLM answers within the frame   (base model = token generator)
  → G. post-check answer alignment; rewrite if it drifts
  → Final response + audit trace
```

The base LLM is never asked to decide ontology. **CSR constrains the answer-space; the LLM verbalizes
within it.**

## 4a. Group-aware R (resonance groups)

Flat 12D cosine fails because all-positive, structured templates are near-collinear (off-diagonal
cosine **mean 0.923, max 0.999**) — it answers "are both vectors generally positive and structured?"
(yes) instead of "**which type of structure is active?**". Group-aware R fixes this.

**Resonance groups** (families of the 12 layers): `ground` (Potential, Identity), `force` (Execution,
Agency, Structure), `intellect` (Cognition, Reasoning), `telos` (Purpose, Integration), `field`
(Witness, Unifying, Absolving).

```
tp, dp        = L1-normalised group activations of term / domain   (relative emphasis, not magnitude)
group_match_g = min(tp_g, dp_g) / max(tp_g, dp_g)
R = Σ_g w_g · group_match_g  −  pen_w · mean(term[domain.blocked_lanes])
```

- **w_g** are **per-domain group weights** (`DOMAIN_GROUP_WEIGHTS`, normalised) — explicit override if
  present, else derived from the domain's own group activations. E.g. medicine = intellect 0.35 /
  telos 0.30 / force 0.20 / ground 0.15; authority = ground 0.35 / force 0.50 / intellect 0.15.
- **penalty** docks R when the domain's blocked lanes are lit (e.g. fruit penalises high
  Reasoning/Agency/Purpose), so phonemically-busy terms cannot "realize" a structurally-forbidden lane.
- Every score carries a **per-group R trace** (`CSRMatchScore.r_groups`): term/domain emphasis,
  weight, match, and contribution per group, plus reward and penalty.

**Effect (template-vs-template, 20 domains):** off-diagonal R drops from flat **mean 0.923 / std
0.054** to grouped **mean 0.670 / std 0.225** (4× the spread) — genuinely-different domains separate
(doctor→fruit R 0.99→0.27) while true twins (authority/finance) stay appropriately close. Inspect with
`eval_match_filter.py --template-audit`.

## 5a. Scaling — no per-domain hand tagging, dominant-theme focus

Two costs would otherwise blow up: authoring `required/allowed/blocked` for every domain, and scoring
every query token × every domain.

- **Ontology rules are derived, not tagged.** A domain's allowance is already implied by its 12D
  template — high layers are required/allowed, low layers are blocked. `derive_ontology_rule(domain)`
  recovers this (it reproduces the hand-tagged `medicine`/`authority` required lanes exactly), so a new
  domain needs only a template (which can itself come from a definition/embedding). Hand-tagged rules
  remain as **optional overrides** (`ONTOLOGY_OVERRIDES`) where precision matters; `ontology_rule()`
  resolves override-else-derived.
- **Score the dominant theme, not every token.** `dominant_terms(query)` selects the head word(s)/
  theme (multi-word known concepts first, then content words by salience, dropping filler/question
  words). This keeps the term axis small (latency) and on-topic (relevance). Candidate domains can be
  similarly pre-filtered by retrieval before scoring.

## 5b. Scalable S — no per-word dictionary required

S is **external semantic coherence, not phonemic**. It is built so it never needs a hand-maintained
per-word gloss table:

- **Term meaning comes from a `definition_provider(term) → text`** (a dictionary / KB / WordNet / LLM
  gloss). If none is supplied, the raw term text is used. There is **no required per-term curated
  dictionary**.
- **Similarity comes from `embed_fn`** (a real sentence embedder) in production:
  `S = cos(embed(definition(term)), embed(domain_definition))`. Offline/CPU falls back to a built-in
  **deterministic hashing embedder** (signed feature-hash of stemmed tokens) so unknown terms are
  still scored without the automatic over-rejection that exact-token overlap causes; a pure `lexical`
  overlap mode remains available for the simplest deterministic tests.
- **Curated `(term, domain)` scores and curated glosses are DEMO/TEST fixtures only**
  (`DEMO_CURATED_SEMANTIC`, `DEMO_TERM_GLOSSES`), opt-in via `use_curated`. They make the canonical
  doctor example deterministic; they are never on the production path. The default adapter uses no
  curated tables.

**What you DO curate — the ontology, not a dictionary.** The only required curation is a **small
domain registry**: per lane a 12D **template** and a short **definition**. Ontology allowance rules
are then *derived* from the template (§5a). That registry *is* your ontology — a bounded, deliberate
artifact — not an open-ended word list.

**Worked contrast** (`demo_unknown_term.py`, term `surgeon`, absent from all fixtures):
lexical `S(medicine)=0.000` → over-rejects; embedding `S(medicine)=0.387` → kept (`weak`); `fruit`
and unrelated lanes are vetoed by the S firewall. The term is scored entirely from its provided
definition — no curated gloss, no curated S.

## 6. Behavior hooks (what makes it behavioral, not decoration)

1. **Retrieval filtering** — drop domains with `MATCH < secondary_match` (or any `reject_*`) from RAG,
   so a "doctor" query does not pull fruit/commerce material unless explicitly asked.
2. **Prompt framing** — inject primary / secondary / rejected domains into the system context with the
   instruction to answer in the primary frame and not introduce rejected domains.
3. **Candidate reranking** — score `n` drafts by
   `0.60·llm_relevance + 0.25·csr_domain_alignment + 0.15·factuality`, pick the best.
4. **Post-generation correction** — if `csr_alignment(answer) < rewrite_if_answer_alignment_below`,
   rewrite using the primary frame.

## 7. Worked example — "Is a doctor a healer or an authority figure?"

| Domain | C | R | S | MATCH | Decision |
|---|---:|---:|---:|---:|---|
| medicine / healing | high | high | 0.97 | **≥0.60** | **primary** |
| authority | mid | mid | 0.48 | ~0.25 | secondary / weak |
| commerce | low | mid | 0.12 | ~0.01 | reject (S) |
| fruit | low | mid | 0.02 | ~0.000 | reject (S/C) |

**Frame handed to the LLM:** *primary = medicine/healing; secondary = authority/responsibility;
rejected = fruit, commerce.* The answer: a doctor is primarily a healer/clinician; authority is
secondary (institutional responsibility around the healing core). `fruit` never appears — vetoed by
the **S** firewall, not by suppressing the phoneme profile.

## 8. What this module must NOT claim

- **No phoneme→meaning.** "doctor sounds like healing, therefore it means healing" is forbidden. The
  pipeline is `phoneme → 12D profile → C/R allowance & realization → S confirms via external meaning`.
- **No AGI / consciousness claim.** This is a semantic-control wrapper, nothing more.
- **No semantic authority from sound alone.** S (non-phonemic) always holds veto power over C and R.

## 9. Evaluation plan (short)

**Comparison:** base LLM vs. match-filter-framed LLM, same prompts.

**Tasks**
1. *Domain framing* — does the answer lead with the correct primary domain?
2. *Irrelevant-domain rejection* — are rejected domains (fruit/commerce for "doctor") absent unless asked?
3. *Ambiguous-term handling* — terms with two valid lanes (e.g. "bank" → finance vs. river) framed sanely?
4. *Post-generation correction* — when an answer drifts, does the rewrite hook restore the primary frame?

**Metrics**
- correct-primary-frame rate
- rejected-domain-avoidance rate
- factuality preserved (no degradation vs. base)
- no-phoneme-overreach (S veto fired where it should; no sound-only meaning claims)
- trace completeness (every answer carries a serialisable C/R/S/decision audit)

**Continue the wrapper if:** framed answers improve correct-primary-frame and rejected-domain-avoidance
without hurting factuality, *and* S vetoes prevent phoneme-overreach on adversarial terms.
**Park it if:** framing gives no lift over the base model, or the S firewall fails to stop
phoneme-only mappings (then S/templates need rework before any further investment).

## 10. Module map

```
scripts/cg_wrapper_ablation/csr_match_filter/
  registry.py   — LAYERS_12, OntologyRule, DomainTemplate, DOMAIN_REGISTRY, glosses/keywords
  profile.py    — compute_12d_profile(term)  (phoneme/letter → varna-ish → 12D)
  resonance.py  — group-aware R: resonance groups, per-domain weights, blocked-lane penalty, R trace
  semantic.py   — SemanticCoherenceAdapter (non-phonemic): definition_provider + embed_fn,
                  hashing_embed (offline), lexical fallback, make_demo_adapter (fixtures)
  match.py      — CSRMatchScore/Trace/Decision dataclasses, scoring, thresholds,
                  build_trace, build_prompt_frame, csr_alignment, CSRMatchFilterWrapper
  demo_doctor.py        — canonical example (uses demo fixtures)
  demo_unknown_term.py  — scalable S: unknown term scored via definition_provider + embeddings
```

No governance/trust, no generation-injection, no logit access. CPU-only (numpy), API-mode wrapper.
