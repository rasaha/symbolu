# B1.10 — Independent Context-Generation Protocol (docs-only)

**Purpose:** provide a protocol by which an **independent, packet-naive author** (a human, or a fresh LLM session
with no exposure to this work) generates the **official, freeze-ready** context sentences for the six B1.10
control-extension words (pride, freedom, patience, courage, control, doubt), so that the contexts cannot mirror the
Tier-3 packets (the context→specific-facet **echo confound**).

Docs-only. No code, no rebuild, no frozen-artifact modification, no evidence freeze, no real judge run, no new
experiment number. Stays under B1.10. Resonance / phonetic-fidelity refinement only — **no `GENUTILITY_*`, no
`ONTOLOGICAL_SIGNAL`, no semantic-truth / ontology / Sanskrit-privilege claim.** B1.4b′ remains
`NULL_RETURN_BOTTOM`; original B1.4b blocked; Track B blocked. **Structure, not validated meaning.**

---

## 1. Objective

Produce official contexts whose fit to a word's Tier-3 packet is earned by the word's ordinary meaning, not by the
author having seen the packet. To that end, **the author must NEVER see**:
- the Tier-3 packets (word-specific v3 renderings or their plain-English paraphrases),
- the varṇa sequences,
- any previous context set (including the three packet-aware development sets — see §10),
- any packet audit or overlap/echo analysis,
- any weak/strong or off-axis facet discussion,
- any previous experiment results (B1.10 pilot margins or otherwise).

The author works from §2 inputs only. Anyone who has seen any item above — **including the current session** — is
disqualified from authoring the official contexts.

## 2. Inputs allowed

The author may be given ONLY:
- the **target word**,
- the **Condition A definition** (verbatim, §3),
- the **Condition B definition** (verbatim, §3),
- the **sentence-writing rules** (§3).

No facet text, no varṇa content, no example sentences derived from packets, no expected-answer hints, no scoring
rubric, no theory.

## 3. Exact author prompt

> You are an independent stimulus author for a blinded experiment. Write natural example sentences for six words.
> You have not seen, and must not ask for, any hidden representation, mapping, prior sentence, audit, or result.
>
> Words: pride, freedom, patience, courage, control, doubt
>
> Condition A: The state depends on comparison, approval, possession, control, fear of loss, rivalry, outside
> results, or other people's reactions.
>
> Condition B: The state arises from inward steadiness, non-comparison, autonomy, non-grasping, clarity,
> self-possession, or action without dependence on approval or outcome.
>
> For each word, write:
> - one sentence expressing Condition A
> - one sentence expressing Condition B
>
> Rules:
> - use the target word naturally;
> - 12–22 words per sentence;
> - express one stable condition only — do NOT describe a transition from A to B or B to A;
> - avoid "but", "however", "although", "even though", "yet", "despite" when they would introduce the opposite
>   condition;
> - avoid moral caricature; write realistic people and settings;
> - vary sentence structure and setting across the twelve sentences;
> - do not explain any theory;
> - do not use the labels "binding", "liberating", "source-condition", "self-grounded", or "other-conditioned".
>
> For each sentence report: intended class (A or B); confidence (high/medium/low); mixed-condition detected
> (yes/no); naturalness (natural/slightly forced/forced). If mixed-condition is "yes" or naturalness is "forced",
> DISCARD that sentence and generate a new one (never truncate or patch it).
>
> Return exactly 12 accepted sentences, two per word.

*(The prompt is deliberately identical in content to the three development runs so that only the author's blindness
differs. The author must receive nothing beyond this prompt.)*

## 4. Acceptance checklist (per sentence)

Verify every sentence:
- [ ] target word used **naturally** (not forced or shoehorned),
- [ ] **one dominant source-condition** only,
- [ ] **no transformation** A→B or B→A,
- [ ] **natural English**,
- [ ] **12–22 words**,
- [ ] **no forbidden labels** (binding / liberating / source-condition / self-grounded / other-conditioned),
- [ ] **no moral caricature**.

A sentence is accepted only if all seven boxes hold.

## 5. Rejection rules

Discard and **regenerate** (never edit in place) if any of:
- mixed source-condition,
- forced wording,
- transition sentence (begins one condition, resolves into the other),
- unnatural dialogue or contrived phrasing,
- obvious repetition of a template/setting already used.

Regeneration is a **fresh sentence** from the same prompt — never a patch of the rejected one.

## 6. Freeze procedure (BEFORE any packet comparison)

Freeze happens **before** anyone (author or reviewer) has compared the sentences to the Tier-3 packets:
1. Collect the 12 accepted sentences + the author's per-sentence self-check table.
2. Record provenance (§9): author identity, date, prompt hash, context hash, acceptance checklist.
3. Write the sentences into a **new, separately-labeled** items file (e.g. `b1_10_control_ext_items_v2.json`) —
   the current `b1_10_control_ext_items.json` and all other B1.10 artifacts remain **byte-unchanged**.
4. Compute and record the sha256 of the frozen contexts.
5. Only after this freeze is the packet content allowed to be placed alongside the contexts.

The ordering is the whole point: contexts are committed **blind**, so no packet knowledge can retroactively shape
them.

## 7. Independent review procedure (ONLY after freeze)

In this order, never earlier:
1. **Naturalness review** — a reviewer (may be non-blind) confirms each sentence reads as natural English.
2. **Sentence-quality review** — confirms 12–22 words, single condition, no transition, no caricature, expected
   class matches an independent reader's reading.
3. **Packet comparison** — only now are the Tier-3 packets brought alongside the frozen contexts.
4. **Echo audit** — measure context↔specific-facet overlap (lexical Jaccard + human check for near-paraphrase),
   per word, against a pre-registered cap.

Steps 1–2 gate on the frozen text; steps 3–4 may reject items but may **not** edit them.

## 8. If an echo is discovered

Do **NOT** edit the offending sentence (editing after seeing the packet is exactly the tailoring this protocol
prevents). Instead:
1. **Reject** the item (that word's context for that pole),
2. **Regenerate** it with **another independent, packet-naive author** (fresh session/person), given only §2/§3,
3. **Repeat the freeze** (§6) for the regenerated item before any new comparison,
4. Re-run the echo audit (§7.4). Repeat until the item passes blind.

An item that cannot pass blind after repeated independent regeneration is **dropped from the study**, not rescued.

## 9. Provenance (record for each generation round)

- **author identity:** human (name/role) or fresh LLM session (model + a note that it was a clean session with no
  exposure to any §1 material),
- **date** (UTC),
- **prompt hash:** sha256 of the exact §3 prompt text delivered,
- **context hash:** sha256 of the frozen 12-sentence set,
- **acceptance checklist:** the completed §4 table + §5 rejection log (how many discarded/regenerated),
- **blindness attestation:** an explicit statement that the author saw none of the §1 items.

## 10. Classification of the existing development sets

The **three** context sets already produced in packet-aware sessions (the original frozen
`b1_10_control_ext_items.json` contexts, plus the two additional within-session drafts generated during
development) are permanently classified as:

**`EXCLUDED_DEVELOPMENT_CONTEXTS_PACKET_AWARE`**

They were authored with knowledge of the Tier-3 packets / audits / prior sets and therefore carry the echo
confound. They **must never become official experimental stimuli**. They may be retained only as development
history and as a **diff reference** (to check that an independent set did not accidentally converge on packet-echoing
wording) — never as the frozen contexts a real run rates against.

## 11. Status

- Docs-only protocol. No official contexts generated here; no code, no rebuild, no frozen-artifact modification, no
  evidence freeze, no real judge run, no new experiment number. Stays under B1.10.
- The current frozen artifact (`b1_10_control_ext_items.json`) is unchanged and remains
  `EXCLUDED_DEVELOPMENT_CONTEXTS_PACKET_AWARE` with respect to its contexts.

## 12. Guardrails
Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no semantic-truth /
ontology / Sanskrit-privilege claim. **B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked.
Structure, not validated meaning.**
