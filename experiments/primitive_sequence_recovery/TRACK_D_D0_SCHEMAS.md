# Track D — D0 Real Pilot Schemas (docs only; NOT frozen artifacts)

**Schema documentation for a future D0 run. No data created, no scoring, no run.** These are
**not** frozen artifacts and are unrelated to `frozen/manifest.json` (which remains NOT_READY and
must not be edited). Shapes are `additionalProperties:false` in intent. Track B remains BLOCKED.

## 1. Word list — `d0_words.jsonl`
Real Sanskrit words live here **only** (never in a Stage-2 packet).
```
{"word_id":"d000","spelling":"<IAST>","dictionary_meaning":"<english>",
 "pos":"noun|verb|adj","domain":"abstract|concrete_control","sense_id":"0"}
```

## 2. Profile-generation input — `d0_profilegen_input.jsonl`
What Stage 1 sees. **No spelling, no varṇa sequence, no vṛtti glosses.**
```
{"gen_id":"g000","dictionary_meaning":"<english>","pos":"noun",
 "controlled_vocabulary_ref":"<hash/id of the closed descriptor lexicon>"}
```
Note: `word_id` is deliberately **absent** from what the generator sees; a private map
`gen_id → word_id` is kept separately (like the hidden keys).

## 3. Anonymized scoring packet — `d0_packets.jsonl`
What Stage 2 sees. **No Sanskrit word, no dictionary meaning, no arm/profile names.**
```
{"packet_id":"p000",
 "compositions":[{"comp_id":"comp_1","text":"<gloss tokens>"}, ...],   // arms A/B/C shuffled
 "profiles":[{"profile_id":"prof_1","descriptors":["...", ...]}, ...]} // target + I1..I4 shuffled
```
Hidden key (SEPARATE file, never sent): `d0_hidden_keys.jsonl`
```
{"packet_id":"p000","word_id":"d000","seed":<int>,
 "comp":{"comp_1":"A|B|C", ...},"prof":{"prof_1":"target|I1|I2|I3|I4", ...}}
```

## 4. Judge response — `d0_responses.jsonl`
Structured JSON only; no free-text rationale in the scoring call.
```
{"packet_id":"p000",
 "scores":{"comp_1":{"prof_1":0.0-1.0, ...}, ...},   // every comp × every prof
 "ranking":{"prof_1":["comp_k","comp_j", ...], ...}, // optional
 "judge_notes":"",                                   // should be empty; scanned for contamination
 "contamination_identified":false}                   // from the separate word-id probe
```
Validation (harness `validate_response`): `scores` covers all comp×prof; values in `[0,1]`;
malformed → repair once → else drop.

## 5. Pilot report — `d0_report.json`
```
{"schema_version":"1.0","toy":false,"run_approved":true,
 "generator_model":"<id@version>","scorer_model":"<id@version>","models_distinct":true,
 "seeds":[...],"output_drop_rate":0.0,
 "per_word":[
   {"word_id":"d000","domain":"abstract","target_profile_id":"prof_x",
    "comp_ids":["comp_1","comp_2","comp_3"],
    "A":0.0,"B":0.0,"C":0.0,"max_barnum":0.0,"A_rank":1,
    "A_vs_B":0.0,"A_vs_C":0.0,"A_vs_barnum":0.0,
    "contamination":false,"label":"LLM_PILOT_..."}],
 "abstract_vs_concrete":{"abstract_mrr":0.0,"concrete_control_mrr":0.0},
 "contamination_summary":{"flagged":0,"probe_identified":0},
 "excluded_leakage_words":[...],
 "overall_label":"LLM_PILOT_SUGGESTIVE|NO_SIGNAL|INCONCLUSIVE|CONTAMINATED",
 "note":"profiles are LLM-generated; exploratory triage only; not validation"}
```
`overall_label` is constrained to the four `LLM_PILOT_*` values; forbidden labels
(`EXPERIENTIAL_WEATHER_SIGNAL`, `ONTOLOGICAL_SIGNAL`, `SANSKRIT_PRIVILEGE`) may never appear.

---

Real D0 pilot package prepared only. No real scoring has occurred. Track B remains blocked.
Structure, not validated meaning.
