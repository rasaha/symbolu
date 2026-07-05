# B1.1 Bridge-Pool Review & Prereg Decision

## 1. Scope and non-claims

**Review / decision memo only.** Reviews the generated B1.1 bridge-pool draft and decides how the B1.1
prereg should handle the blocked embedding gate. **No model run · no B1.1 freeze · no generation / scoring /
judging.** Does **not** modify B1, change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B
(**BLOCKED**). No ontology validation, Sanskrit privilege, or semantic-truth claim. **Structure, not
validated meaning.**

## 2. Current artifact status

- **Resolved lexicon** — 34 consonants, binding/liberating schema, `deferred_count=0`; validator **18/18**.
- **Local lexical audit + adjudication** — exact-dup 0, hard 0, soft 2 (Ka~Sa, Ḍha~La), both
  `ACCEPT_WITH_RATIONALE`; local status **`PASS_LOCAL_SURFACE_ONLY`** (surface only).
- **Bridge pool draft** (`3e49583`) — 68 phrases, gate **`PASS_BRIDGE_DRAFT`**, status **DRAFT /
  FALLBACK_QUALIFIED**.
- **Embedding gate** — **`BLOCKED_DEPENDENCY_UNAVAILABLE`** (huggingface.co egress-denied); **still owed**.
- **Track B** — **BLOCKED**. **B1 verdict** — **`RANDOM_OR_SCRAMBLED_MATCHES`** (unchanged).

## 3. Bridge pool review (verified against `b1_1_bridge_pool_draft.json`)

| review item | result |
|---|---|
| 68 bridge phrases exist | ✓ (34 binding + 34 liberating) |
| all distinct | ✓ (68/68 unique after normalization) |
| forbidden language clean | ✓ (0 hits; good/bad/positive/negative/vice/virtue absent) |
| one-to-one source mapping preserved | ✓ (each phrase → one source expression) |
| binding/liberating language preserved | ✓ (no good/bad framing) |
| Ca / Va distinct | ✓ (falsehood-discernment vs accepting-as-true/order) |
| Ha / Kṣa distinct | ✓ (realized knowing vs instrumental knowledge) |
| Sa / Ra distinct (Sa guṇa-aware, Ra dual-source) | ✓ (Sa "owned…"; Ra vitality **and** destructive-collapse) |
| Ḍha / La distinct | ✓ (social malice/maligned vs physical harm/weak) |
| Ka / Sa non-identical | ✓ (distinct full phrases; "without attachment to X" is shared surface template only) |
| manual/heuristic per-entry alteration | none (uniform template derivation) |

**Review verdict:** the bridge draft is internally clean and contrastive **at the surface/structural level**.
This does **not** establish semantic (embedding) contrastivity — see §4.

## 4. Embedding-gate fork

- **A. Preferred path** — obtain embedding-model access (allow-list `huggingface.co` / supply a cached
  `all-MiniLM-L6-v2`) and **re-run `B1_1_NON_SYNONYM_EMBEDDING_GATE`**. This is the scientifically correct
  route; it tests deep paraphrase synonymy the local audit cannot see.
- **B. Fallback path** — proceed with B1.1 prereg using the **local lexical audit as weaker contrastivity
  assurance**, with the limitation and elevated risk explicitly disclosed.
- **C. Hold** — do not proceed until the embedding gate is solved.

## 5. Decision

**`PROCEED_TO_PREREG_UNDER_FALLBACK_QUALIFICATION`** (path B).

Meaning:
- the bridge draft **may be used for prereg drafting**;
- the prereg **must explicitly disclose** that embedding contrastivity was **blocked**;
- the local lexical audit is **weaker and surface-only**;
- the **elevated R-risk must be named**;
- this **does not freeze B1.1**;
- this **does not authorize** generation / scoring / judging.

**Standing preference:** path A remains preferred; if embedding access is restored before freeze, the real
gate should be run and its result supersedes the fallback qualification.

## 6. Required prereg caveat language (verbatim, to embed in the B1.1 prereg)

> - "The planned sentence-embedding non-synonym gate could not be executed because the required model host
>   was unavailable under the environment's egress policy."
> - "A local lexical/phrase-similarity audit was used as an interim weaker screen."
> - "This fallback detects surface overlap but not deep paraphrase synonymy."
> - "Therefore the experiment retains elevated risk that R_same, R_deranged, or R_domain may remain strong
>   for reasons not eliminated by the fallback audit."
> - "A positive result, if any, must be interpreted only as LIMITED_GENERATION_UTILITY under this frozen
>   design, not ontology validation."

## 7. B1.1 prereg requirements

The prereg (`B1_1_PREREG_DRAFT`) must define:
- **hypothesis** (H2-specific: word-derived varṇa mapping beats controls);
- **arms**: A · D (dictionary) · S (scrambled) · **R_same** · **R_deranged** · **R_domain** · C (surface) ·
  X (neutral);
- **co-primaries** and the rule that **A must beat ALL** at the corrected CI lower bound > 0.5 (Holm);
- **tasks** (the T1–T6 family or a pre-registered set);
- **seeds** (generation, output-randomization, packet, bootstrap — frozen);
- **generation model(s)**;
- **judge panel** (declared allowlist) + attention-check exclusion rule;
- **scoring plan** (item-clustered paired bootstrap → Holm → verdict map);
- **leak scan** (structural blinding);
- **persistence sample** (commit 30–50 leak-scanned packets incl. R-beats-A / A-beats-R; hash-bind full set);
- **kill criteria** (§8);
- **allowed verdict labels** (incl. the B1 kill labels + `LIMITED_GENERATION_UTILITY`);
- **the fallback caveat** (§6).

## 8. Kill criteria

- **If A fails to beat `R_deranged` and `R_domain`**, H2-specific generation utility remains **unsupported**
  (word-specific fit shows no signal). `R_deranged` is the crux.
- **If R controls match A again**, the result remains **random / generic resonance**
  (`RANDOM_OR_SCRAMBLED_MATCHES`-type) — consistent with B1 and Track G.
- **If correctness degrades** (e.g. the T4-style accuracy task), report it **separately**
  (`CORRECTNESS_DEGRADED` / accuracy caveat).
- **No rescue language.** A pre-committed kill stands; "it would work with a better lexicon/embedding" is
  **not** a rescue — at most it motivates a *new*, separately-pre-registered study. Two independent negatives
  (Track G, B1) already weigh against the prior.

## 9. Next gate

**`B1_1_PREREG_DRAFT`** — draft the full pre-registration incorporating the §6 caveat, §7 requirements, and
§8 kill criteria. (Draft only; freeze is a later, separate gate.)

## 10. Final status block

```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
Bridge status:         PASS_BRIDGE_DRAFT / FALLBACK_QUALIFIED
Embedding gate:        BLOCKED_DEPENDENCY_UNAVAILABLE (still owed)
Decision:              PROCEED_TO_PREREG_UNDER_FALLBACK_QUALIFICATION
B1.1 frozen:           NO
Generation authorized: NO
Scoring/judging:       NO
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` · Track F `CORRECTNESS_DEGRADED`. Contrastivity /
non-synonymy repair remains **necessary but not sufficient**; **`R_deranged` remains the crux**.

**Structure, not validated meaning.** Review/decision memo only; the B1 verdict stands and Track B remains
BLOCKED.
