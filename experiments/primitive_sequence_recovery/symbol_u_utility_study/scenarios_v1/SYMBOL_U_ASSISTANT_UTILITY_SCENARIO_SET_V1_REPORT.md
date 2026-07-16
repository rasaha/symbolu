# Symbol-U Assistant Utility — Scenario Corpus V1 Report

`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`
**Status: `UTILITY_SCENARIO_SET_V1_FROZEN`.** Docs/data only (roadmap **M1** of `SYMBOL_U_ASSISTANT_UTILITY_PREREG_V1.md`).
No arm implemented, no prompts, no model run, no assistant response, no scoring. No prior/frozen artifact modified.

- **Final scenario-set SHA-256:** `0e4519925f8bf8208502f98e55fed53b50411a9d92c42acc7eef36596521fb8c`
- **Scenarios:** 50 (from a 75-candidate pool; 25 excluded). **IDs S001–S050.**

## Validation (all pass)
50 scenarios · schema-valid against the frozen `scenario.schema.json` · IDs exactly S001–S050 · every one of the 25
frozen concerns is **primary exactly twice** · all concern IDs exist (none invented) · **40 single-concern / 10
multi-concern** · max 2 concerns per scenario · difficulty **20 DIRECT / 20 CONTEXTUAL / 10 AMBIGUOUS_BUT_RESOLVABLE**
· no exact or ≥0.6-Jaccard near-duplicates · **no** Sanskrit / Symbol-U / varṇa / mapping / reframing terminology in
any message · `expected_bridge_output` concepts match the frozen concern→concept table exactly · no model/arm/prompt/
output/score present.

## Known deviation (one, disclosed)
The task requested IDs **S0001–S0050** (4-digit), but the **frozen** `scenario.schema.json` pins `scenario_id` to
`^S[0-9]{3}$` and the task also forbids modifying the schema. To keep the corpus **fully schema-valid without touching
a frozen artifact**, 3-digit IDs **S001–S050** were used. This is the only deviation; if 4-digit IDs are wanted, widen
the schema pattern to `^S[0-9]{4}$` in a future schema revision and re-mint.

## Distributions
- **Primary concern:** each of the 25 concerns appears as primary in exactly **2** scenarios (50 total).
- **Difficulty:** DIRECT 20 · CONTEXTUAL 20 · AMBIGUOUS_BUT_RESOLVABLE 10.
- **Single/multi:** 40 single · 10 multi (each multi = 1 primary + 1 secondary, secondary in ascending ontology-ID
  order, independently processable, no hybrids).
- **Secondary concerns** (in the 10 multi scenarios): laziness, doubt (×2), burden, duty, anxiety (×2), fear, purpose,
  resentment — each an ordinary co-present concern, never merged into the primary.

## Complete scenario list
| ID | Diff | Primary (+secondary) | Message (truncated) |
|---|---|---|---|
| S001 | D | fear | I've got a flight next week and I'm honestly scared something will go wrong on it. |
| S002 | C | fear | My daughter just started driving to school on her own. She's careful, but every time she… |
| S003 | D | anxiety | I can't stop worrying about the review meeting on Monday — it's honestly all I think abo… |
| S004 | A | anxiety | Work's fine, home's fine, nothing's actually wrong — but my head won't switch off lately… |
| S005 | D | anger | My coworker took credit for my project in front of the whole team today and I'm furious. |
| S006 | C | anger | I asked my landlord three times to fix the heating. Today he showed up, glanced at it, a… |
| S007 | D | resentment | I still can't get past how my brother treated me last year. I just resent him now. |
| S008 | C | resentment | Every time my friend bails on plans last minute I say it's fine, but it's built up over … |
| S009 | C | attachment | We're moving to a bigger place next month — good news — but I keep finding reasons to pu… |
| S010 | A | attachment +laziness | Everyone says sell my dad's old car — it just sits there costing insurance. I keep meani… |
| S011 | D | grief | My mum passed away in March and some days the sadness just flattens me. |
| S012 | C | grief | It's been six months since we had to put our dog down. I thought I'd be okay by now, but… |
| S013 | D | craving | I really want that promotion. I think about it constantly — how it would feel to finally… |
| S014 | C | craving | I keep reopening the listing for a watch I can't really justify. I don't need it. I just… |
| S015 | D | greed | I got the raise I asked for and within a week I was already thinking it wasn't enough. |
| S016 | C | greed | Business is better than I planned, but instead of easing off I keep chasing more account… |
| S017 | D | confusion | I've read the setup instructions three times and I still don't understand what I'm meant… |
| S018 | A | confusion +doubt | Everyone's giving me advice about the reorg and none of it lines up. I can't tell what I… |
| S019 | D | doubt | I've got the job offer but now I'm genuinely unsure whether to take it or stay where I am. |
| S020 | A | doubt | On paper the move makes sense. My gut keeps saying wait. I go back and forth on it every… |
| S021 | D | pride | I know I should apologise, but I really hate admitting I was the one who got it wrong. |
| S022 | C | pride | In the debrief I kept steering it back to what I'd handled well. Afterwards I realised I… |
| S023 | D | shame | I completely blanked during the presentation and now I just want to hide. |
| S024 | C | shame | I forgot my friend's birthday — genuinely forgot. When she mentioned it lightly I went h… |
| S025 | C | separation-longing | My partner's away on a three-month posting. We talk every day, but the flat feels wrong … |
| S026 | A | separation-longing | My best friend moved abroad in spring. We're still close, still text, but there's this a… |
| S027 | D | duty | My parents are getting older and I'm the only one nearby, so looking after them falls to… |
| S028 | C | duty +burden | Nobody else will run the fundraiser, so it's fallen to me again. It's mine to see throug… |
| S029 | D | burden +duty | Between work, the kids, and my mother's appointments, it's all on me and it's just too m… |
| S030 | A | burden | I said yes to chairing another group this week. I don't even remember agreeing. It just … |
| S031 | D | money-concern | I keep checking my bank balance even though nothing's changed. Money's just constantly o… |
| S032 | C | money-concern +anxiety | We got through the month, but the car needs tyres and I've started shuffling which bill … |
| S033 | D | poverty | After rent this month there's basically nothing left for groceries. |
| S034 | C | poverty +fear | The hours got cut at work and now I'm choosing between the electric bill and my kid's sc… |
| S035 | C | diligence | I've got a certification exam in two months and I've mapped out a study plan. Right now … |
| S036 | A | diligence +purpose | Some nights I really push at the side project; other nights I just open the file and sta… |
| S037 | D | laziness | The same three tasks have been on my list for a week and I just can't make myself start … |
| S038 | C | laziness | It's Sunday, the flat's a mess, I meant to meal-prep and do laundry, and instead I've be… |
| S039 | D | purpose | I've got a stable job but I keep asking what I'm actually working toward. |
| S040 | A | purpose +doubt | I ticked every box I set five years ago. Now I'm not sure what the next thing is even fo… |
| S041 | D | curiosity | I've really been wanting to understand how mortgages actually work before we buy. |
| S042 | C | curiosity | My kid asked me why the sky goes red at sunset and I realised I didn't actually know. No… |
| S043 | D | knowledge | After a year of practice I can finally read music fluently — it just clicks now. |
| S044 | C | knowledge | I used to nod along in budget meetings pretending I followed the numbers. This quarter I… |
| S045 | C | patience | We're six months into trying to adopt and it's all waiting — forms, reviews, more waitin… |
| S046 | A | patience +resentment | My teenager barely speaks to me right now. I'm trying to ride it out like everyone says,… |
| S047 | D | contentment | Honestly, things are pretty good right now and I feel settled with where I am. |
| S048 | C | contentment | We didn't get the bigger house, and a year ago that would've stung. Now I look around ou… |
| S049 | C | calm | After the deadline finally passed I took the weekend off-grid, and my mind feels quiet f… |
| S050 | A | calm +anxiety | I don't need anything fixed. I just want ten minutes somewhere my head isn't buzzing and… |

## Candidate pool & exclusions (25)
75 candidates authored; 25 excluded by the deterministic filter order (schema/field validity → concern-definition
fidelity → safety scope → realism → duplication → primary balance → difficulty quotas → single/multi limits →
deterministic ordering). Reasons used: OUTSIDE_SAFETY_SCOPE (self-harm, violence intent, medical emergency, diagnosis
request, regulated financial transaction), NEAR_DUPLICATE_TEMPLATE, CONCERN_MISMATCH, EXCESSIVE_AMBIGUITY,
LEADING_TO_DESIRED_RESPONSE, UNREALISTIC_USER_LANGUAGE, OVER_CATEGORY_QUOTA, MULTI_CONCERN_LIMIT, SCHEMA_INVALID.
Full list: `scenario_exclusions_and_rewrites_v1.json`.

## Selection firewall
Scenarios were authored **only** from concern definitions, inclusion/exclusion rules, synonyms/clarification cues,
ordinary personal-assistant situations, linguistic realism, and safety/duplication checks. **Not used:** Sanskrit
concept decomposition, varṇa identities/meanings, mapping glosses, mapping coverage beyond the already-frozen
eligibility, relationship families, B1.12 stability rankings, Tier-1 mappings, expected symbolic reframing, or any
hypothesis about which arm will perform better. The concern→concept table was read **only** to populate
`expected_bridge_output`; the parser and varṇa mapping table were **not** read.

## Realism
Messages vary across work, family, relationships, money pressure, responsibility, learning, uncertainty, habits,
identity, emotional regulation, and life direction; and vary in length, tone, explicitness, and whether the user asks
for advice or simply describes a situation. Not every scenario is dramatic or therapeutic. Concern labels are not
planted in the wording except where they would arise naturally.

## Safety
No scenario primarily involves imminent self-harm, imminent violence, severe medical emergency, acute psychosis,
abuse emergency, legal crisis, regulated financial transaction, or a request for professional diagnosis (such items
were authored only as **excluded** candidates to document the safety filter). Ordinary non-crisis fear, anxiety,
grief, anger, money stress, relationship tension, shame, doubt, and low motivation are included.

## Interpretation limits
This corpus does **not** demonstrate Symbol-U utility, does **not** validate the varṇa mappings, does **not** test
concern extraction, and does **not** represent every user population or concern. It only provides a **fixed evaluation
corpus** for the preregistered four-arm study.

## Artifacts (`symbol_u_utility_study/scenarios_v1/`)
`scenario_candidate_pool_v1.json`, `scenario_set_v1.json`, `scenario_exclusions_and_rewrites_v1.json`,
`scenario_difficulty_audit_v1.json`, `scenario_balance_audit_v1.json`, `scenario_contamination_audit_v1.json`,
`scenario_manifest_v1.json`, and this report.
