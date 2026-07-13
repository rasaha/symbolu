# B1.12 — Gate G1 Ordered Component-Descriptor Instrument V1.2 (normalized labels)

Second G1 repair iteration. Builds the coverage-complete semantic ordered-component instrument with descriptors
**normalized to shorter standalone labels** (addressing the length/narrative failures of the v1 attempt,
`d48ae9f`), a full descriptor-quality audit, deterministic leakage checks, and A/B/D render examples. Remains
**B1.12** (same H2 question; the opaque task was an instrument failure). **No B1.13.** Prior G1 artifacts
(opaque `9e8da86`, reassessment `bb2051e`, semantic-v1 `d48ae9f`) preserved unchanged.

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`. No judges, no run, no evidence freeze. No change to
the selected six, G0, pool, parser, lexicon, or thresholds. B1.10/B1.11 unchanged.

**Outcome: `G1_BLOCKED_DESCRIPTOR_QUALITY`.** Coverage is 100% and the A/B/D design is sound, but the only frozen
descriptor source (affliction/tendency glosses) cannot be turned — even by normalization — into neutral,
length-parity, referent-matchable component labels.

---

## 1. Selected six (frozen, unchanged) & instrument shape
W03 asthi · W15 grīvā · W20 jñāna · W23 keśa · W30 nadī · W35 sūrya. Instrument: one fixed descriptor per atomic
varṇa identity; arms A (true order) / B (seeded scramble) / D (canonical unordered) share the exact descriptor
multiset, count, and `position i:` template; only order differs (A vs B). Primary task: candidate-relative
semantic matching to the hidden word's ordinary meaning; primary contrast `Δ_order = Acc(A) − Acc(B)`, secondary
`Δ_inventory = Acc(A) − Acc(D)`.

## 2. Descriptor tiers & firewall
Tier A (source-backed, mandatory where a frozen mapping exists): exact `binding_vritti` verbatim, fixed pole,
plus a mechanical normalization (drop post-colon examples + trailing parentheticals, keep the term–gloss head;
no paraphrase). Tier B (developmental gap-fill): **not reached — coverage is 100% source-backed.** Firewall: Role
A inventory (no word meanings) → Role B authoring (keyed only by `(type,unit)`) → Role C audit — three sequential
commits.

## 3. Why the instrument is nonetheless blocked (three independent failures + a headroom problem)

1. **`DESCRIPTOR_NEUTRALITY_FAILURE` — domain mismatch (dominant, irreducible).** 17/18 normalized descriptors
   are affliction/psychological-tendency labels (peevishness, grasping hope, moha/attachment, kāma/desire,
   self-doubt, melancholy, defeat, hypocrisy…). They are semantically **disjoint** from the ordinary concrete
   referents (bone, river, sun, hair, knowledge, neck) the task must match, so there is **no principled basis**
   for an evaluator to choose a referent from them — in any order → **the task is not identifiable** and has
   **no headroom** for an order effect. Example (`asthi` = bone) renders as *"restless starting without
   sustaining / the sentient sattvic impulse clung to… / viśāda — melancholy… / self-absorption"* — unrelated to
   bone. This is **unfixable**: Tier A is mandatory for all 18 covered identities (no coverage gap permits
   Tier-B referent descriptors), and re-authoring to referent-neutral labels would require inspecting the words'
   meanings (firewall violation) or softening/reinterpreting the frozen mappings (forbidden).
2. **`DESCRIPTOR_LENGTH_LEAKAGE` — persists after normalization.** Normalized vowel labels 24–36 chars vs
   consonant labels 37–121 chars remain **disjoint** → descriptor length still exposes each word's
   consonant/vowel skeleton before any judge. Deeper truncation (cut at em-dash) would collapse several
   consonants to bare Sanskrit terms (moha, sarvanāśa, kāma…) — non-uniform and reinterpretive.
3. **`DESCRIPTOR_SOURCE_TIER_LEAKAGE` + residual narrative + raw Sanskrit.** DEVELOPMENT (vowel) vs CONFIRMATORY
   (consonant) lengths remain disjoint; 11/12 consonant labels retain em-dash elaboration (process-phrase, not a
   standalone label); 7 embed raw Sanskrit terms (āśā, moha, sarvanāśa, sattvic, viśāda, aviśvāsa, kāma) — a raw
   Sanskrit/transliteration vector in evaluator-facing text.

**Headroom problem (independent of descriptors):** all six words have **distinct varṇa inventories**, so the
**unordered inventory (arm D) already uniquely identifies each word**, and the **first descriptor is unique per
word** — meaning that even with referent-diagnostic descriptors, order would add little detectable signal, and
first-position/inventory shortcuts would leak. (This echoes the G0/G1 `INVENTORY_DOMINATED` finding.)

## 4. What passes (to isolate the block)
Coverage 100%; exact-duplicate descriptors 0; no prohibited progression terms; A/B/D multiset parity exact; A≠B
order; D canonical; identical template footprint; content-masked arms identical; no target-word transliteration
in renders. The **design and mechanics are sound**; the block is the **descriptor content**.

## 5. Verdict & resolution
**`G1_BLOCKED_DESCRIPTOR_QUALITY`.** A usability probe is **not** meaningful with these descriptors. Resolution
(separate pre-registration; not taken here): author a **referent-neutral, length-parity, non-narrative,
Sanskrit-term-free, coverage-adequate** component-descriptor set authorable **without** inspecting the selected
words' meanings, on a word set whose inventories are **not** individually identifying (to give order headroom).
If no such frozen source exists, the honest conclusion is that **H2 via a leakage-safe evaluator instrument is
not testable with the current frozen varṇa mappings** — the frozen "meanings" are affliction-tendency glosses,
not referent descriptors — which is itself consistent with B1.10's null and the arbitrariness-of-the-sign prior.
Structure, not validated meaning.
