# B1.10 — Packet-Aware Audit Pre-Registration (docs-only)

**Freezes the pass/fail criteria for the Stage-3 packet-aware audit of the non-Claude blind contexts
(`B1_10_OFFICIAL_CONTEXTS_v3_QWEN.md`, combined-block sha256
`a0abccb89091578cc6ee81b22143bd2bcd82ee9eb8624ba6855224825a418bfc`) BEFORE any Tier-3 overlap is computed.**
Docs-only: no contexts/packets/runners/items/evidence-freeze/results are changed; no judges are run; the
experiment number is unchanged (B1.10). Resonance / phonetic-fidelity refinement only — **no `GENUTILITY_*`,
no `ONTOLOGICAL_SIGNAL`, no semantic-truth / ontology / Sanskrit-privilege claim.** B1.4b′ remains
`NULL_RETURN_BOTTOM`; original B1.4b blocked; Track B blocked. **Structure, not validated meaning.**

The purpose of pre-registering is anti-tailoring: the auditor (Claude, packet-aware) has seen the Tier-3
paraphrases, so the echo cap and decision rules are fixed here **first**, then the numbers are computed and
compared against them — the thresholds cannot move to fit the observed overlap.

---

## 1. Auditor & permissions

- **Auditor:** Claude, acting as the **packet-aware** reviewer. This is the intended role: Claude is
  disqualified only from being the *blind context author* (it is packet-contaminated) and from being a
  *judge* (self-preference on Claude-authored Tier-3 paraphrases). The audit is explicitly a packet-aware
  step (`B1_10_INDEPENDENT_CONTEXT_GENERATION_PROTOCOL.md` §7: the reviewer "may be non-blind").
- **May now consult:** Tier-1 packets, Tier-2 packets, Tier-3 packets (word-specific v3 renderings + their
  plain-English paraphrases), the varṇa content, and the excluded development context sets (as a diff
  reference only). Files: `frozen/b1_10_control_ext_items.json` (Tier-1/2/3 pools + Tier-3 per-varṇa map),
  and the excluded sets (`EXCLUDED_DEVELOPMENT_CONTEXTS_PACKET_AWARE`, `EXCLUDED_CLAUDE_FAMILY_CONTEXTS`).
- **Audit target:** the 12-sentence canonical block only (the `patience` provenance-echo tail is already
  excluded from the block and is out of scope).

## 2. Checks, in order (all four must be applied to every word)

### 2a. Naturalness
Each of the 12 sentences reads as natural English a good writer would produce. (Surface 12–22-word / target-
word-once rules already passed; not re-litigated.)

### 2b. Sentence-quality & condition-fit
For each sentence: **exactly one stable condition**, no A→B/B→A transition, no moral caricature, and — on an
**independent reading by the auditor** — the sentence's actual condition **matches its intended class**
(A = other-conditioned / dependent; B = inward / non-grasping). The three previously-flagged audit-watch
items are adjudicated here explicitly:
- `freedom` A ("…despite the uncertainty") — decide whether "despite" flips it toward Condition B; if it
  introduces the opposite condition → condition-fit FAIL.
- `control` B ("…autonomous system to control the vehicle") — decide whether this is a credible Condition-B
  (letting-go / non-grasping) reading or a strained one.
- `patience` — confirm the two-sentence block (echo tail excluded) is clean.

### 2c. Context-independence + Tier-3 echo  **(the primary quantitative gate)**
Per word, measure lexical overlap between the word's context (A ∪ B) and the word's **Tier-3 plain-English
paraphrase**, using the frozen method in §3. Decision:
- Jaccard **≤ 0.20** and no human-identified near-paraphrase → **CLEAN** (or `ACCEPTABLE_GENERIC_OVERLAP` if
  the shared tokens are generic valence/source-condition words, not Tier-3-specific facet wording).
- Jaccard **> 0.20**, **or** a context clause is a recognizable restatement of a Tier-3 facet phrase (even
  below cap) → **`SUSPECT_SPECIFIC_ECHO`** → the item is **REJECTED** (§4).

### 2d. Tier-1 / Tier-2 fairness
Per word, confirm a **generic Tier-1 (valence)** packet and a **generic Tier-2 (source-condition)** packet
each remain a **plausible** fit for the context — i.e. the context is *not* answerable only via
Tier-3-specific content. Decision: **FAIR / UNFAIR**. UNFAIR → the item is REJECTED (§4).

## 3. Frozen echo-overlap method (fixed BEFORE computing)

- **Tokenization:** lowercase; strip punctuation; split on whitespace.
- **Stopwords:** removed using a fixed English stopword list (committed with the audit script); the **target
  word itself** is also removed from both sides (it is shared by construction and is not evidence of echo).
- **Stemming:** Porter stemming (deterministic).
- **Context set** for a word = the stem set of its A sentence ∪ its B sentence (self-check lines excluded).
- **Tier-3 set** for a word = the stem set of that word's Tier-3 plain-English paraphrase.
- **Statistic:** Jaccard = |context∩tier3| / |context∪tier3|.
- **Cap:** **0.20** (frozen). Consistent with the prior B1.10 items' observed Tier-2/Tier-3 Jaccard ≤ 0.037
  under a 0.2 cap. The number for every word is reported regardless of pass/fail.
- **Convergence diagnostic (advisory only):** also report Jaccard of each new context vs the corresponding
  excluded Claude / development context; **flag** (not auto-reject) if > 0.50, as a check that the blind
  author did not accidentally converge on packet-aware wording. Advisory because a blind author sharing some
  ordinary wording with a prior set is expected by chance.

## 4. Decision rules (per word) — the audit may REJECT but may NEVER edit

- **PASS** — 2a natural ∧ 2b single-condition & class-correct ∧ 2c CLEAN/ACCEPTABLE_GENERIC_OVERLAP ∧ 2d FAIR.
- **REJECT_ITEM** — fails any of 2a–2d. Do **not** edit the sentence (editing after seeing the packet is
  exactly the tailoring this prevents). Instead regenerate **only that word-pair** via a **fresh per-word
  blind job** (`b1_10_perword_author_run.py`, §per-word workflow) — never a packet-aware edit — update the
  development file, and **re-run this audit** on the new pair. Repeat until all pass.
- **DROP** — a word that cannot pass blind after repeated independent regeneration is dropped from the study,
  not rescued.

**Whole-set decision:** the context set is **APPROVED** only when **all six** words PASS. No partial approval;
no per-word cherry-picking of a "better" version (accept-first-pass already fixed the accepted pair).

## 5. Outputs of the audit (Stage 3 deliverable, when run)

A committed audit report: per word — the four check verdicts, the Tier-3 echo Jaccard number, the convergence
diagnostic, and PASS / REJECT_ITEM / DROP; plus the whole-set decision. If any REJECT_ITEM, the report names
the word(s) to regenerate. The audit script (deterministic Jaccard) is committed alongside so the numbers are
reproducible.

## 6. What the audit does NOT do

No judges; no evidence-freeze declaration; no items-file rebuild; no packet edits; no context edits; no new
experiment number. Those come only **after** whole-set APPROVAL: rebuild `b1_10_control_ext_items.json` with
the approved v3 contexts (`build_b1_10_control_ext.py`), create the single evidence-freeze declaration, then
the real Llama/Gemma judge run (Stage 4) on the pod.

## 7. Guardrails
Docs-only pre-registration. Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no
`ONTOLOGICAL_SIGNAL`; no semantic-truth / ontology / Sanskrit-privilege claim. **B1.4b′ remains
`NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked. Structure, not validated meaning.**
