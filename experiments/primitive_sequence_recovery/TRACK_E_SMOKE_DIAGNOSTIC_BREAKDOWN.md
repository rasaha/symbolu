# Track E Smoke Pilot — Diagnostic Breakdown

**Diagnostic analysis of an exploratory-triage result. Not validation.** No `ONTOLOGICAL_SIGNAL`,
no `EXPERIENTIAL_WEATHER_SIGNAL`, no Sanskrit privilege. `frozen/manifest.json` remains NOT_READY;
the base smoke manifest stayed `run_enabled:false` / `NOT_APPROVED` (the run used the separate
approved config); psr runner NOT_RUN; Stage A untouched; four-sphere JSON parked/not integrated;
**Track B remains BLOCKED.** This breakdown cannot convert the result into a positive (see §10).

> Data note: `track_e_smoke_result.json` persists per-case **ranks** of the context-correct
> candidate under each arm (1 = best of 6) plus aggregate MRR/Top-1, but **not** per-candidate raw
> scores. The per-case table below therefore uses ranks; word/context/correct-candidate identities
> are recovered post-hoc from the (now-unblinded) smoke bundle for interpretation.

## 1. Executive diagnosis

The result is **`CONTEXT_ONLY_EXPLAINS`**, **not** a boundary signal. Context-only (X) is the
strongest arm (MRR 0.958); the real varṇa boundary (A, MRR 0.792) is **worse than context alone**
(`A_vs_X = −0.167`, the primary falsifier) and also loses to scrambled (B), etymology (F), and
Barnum (I), beating only the deliberately weak dictionary-only floor (D). There is **no case** where
the real boundary cleanly beats every control. The varṇa boundary adds no incremental
candidate-selection value and is net-negative where its content is domain-mismatched.

## 2. Per-case table (rank of the context-correct candidate; 1 = best of 6)

| case | domain | word (surface / broad) | context (short) | correct candidate | A | X | B | F | D | I | dominant class |
|---|---|---|---|---|---|---|---|---|---|---|---|
| e000 | abstract | sukha / ease·happiness | "fever broke, a quiet loosening" | relief after strain | **1** | 2 | 1 | 2 | 4 | 2 | scramble-equivalent (A=B beat X; not varṇa-specific) |
| e001 | abstract | hrdaya / heart | "he alone stood his ground" | courage / inner resolve | 1 | 1 | 1 | 1 | 2 | 1 | context-saturated (all rank 1) |
| e002 | abstract | shanti / peace | "two families settled their feud" | reconciliation between enemies | 1 | 1 | 1 | 1 | 4 | 1 | context-saturated |
| e003 | abstract | krodha / anger | "official took bread; she rose" | righteous indignation at injustice | 1 | 1 | 1 | 1 | 2 | 1 | context-saturated |
| e004 | abstract | bhaya / fear | "lay awake before the verdict" | anxious dread of what may come | **2** | 1 | 1 | 1 | 1 | 1 | boundary-noise (A uniquely worse) |
| e005 | abstract | bala / power·strength | "lifted the beam off the child" | bodily strength / muscular force | 1 | 1 | 1 | 1 | 2 | 2 | context-saturated |
| e006 | abstract | buddhi / intellect | "saw which plan would fail" | discerning judgment | 1 | 1 | 1 | 1 | 4 | 1 | context-saturated |
| e007 | concrete | nadi / river | "current carried the boat to sea" | a flowing natural watercourse | **6** | 1 | 6 | 1 | 3 | 1 | boundary-distractor (concrete mismatch) |
| e008 | concrete | parvata / mountain | "final ascent to the summit" | a single tall rocky peak | **3** | 1 | 3 | 3 | 1 | 1 | boundary-distractor (concrete) |
| e009 | concrete | grha / house·home | "masons set the roof beams" | a dwelling building | **2** | 1 | 6 | 3 | 1 | 1 | boundary-distractor (concrete) |
| e010 | famous | kama / desire | "fixed on building the bridge" | aspiration toward a chosen goal | 1 | 1 | 1 | 1 | 5 | 2 | context-saturated (exploratory-only) |
| e011 | famous | dharma / duty | "soldier returned to his post" | the obligation of one's role | 1 | 1 | 1 | 1 | 2 | 1 | context-saturated (exploratory-only) |

Tally of dominant classes: **context-saturated 7**, **boundary-distractor (concrete) 3**,
**boundary-noise 1** (e004), **scramble-equivalent/marginal 1** (e000).

## 3. Where context-only won

X **strictly beat** A in **4 cases**: e004 (X1 vs A2), e007 (X1 vs A6), e008 (X1 vs A3), e009
(X1 vs A2). X **tied** A (both rank 1) in **7 cases** (e001–e003, e005, e006, e010, e011), and X
**lost** to A in exactly **1** (e000, X2 vs A1). Reading:

- On the 7 ties, the context was **too easy** — context alone already ranks the correct candidate
  #1, so there was no headroom for the boundary to add anything. This is context saturation, not a
  boundary success.
- On the 4 losses, A **added noise** — worst on the concrete controls (e007–e009), where the
  affliction-vṛtti boundary actively dragged the scorer off *river / mountain / house*, and on
  e004 where the boundary uniquely mis-ranked "fear." So where the boundary moved the result at
  all, it moved it the **wrong way**.

## 4. Where the real boundary helped

**None.** There is **no case** where A beats X, B, F, D, **and** I. The closest is e000, where A
ranks the correct candidate #1 while X ranks it #2 — but the **scrambled** boundary (B) also ranks
it #1 there, so A does **not** beat B. A clean boundary win (A strictly best across all five
controls) does not occur in any of the 12 cases. Stated directly: the real varṇa boundary never
demonstrated a case-level advantage attributable to the specific varṇa content.

## 5. Where Barnum beat the real boundary

I (Barnum) **beat** A in the same **4 cases** (e004, e007, e008, e009) and **tied** A elsewhere.
Interpretation: this is **not** because the generic internal-boundary language was "too strong." On
the concretes, Barnum ranked the correct answer #1 precisely because the generic boundary is
**bland/inert** — it does not inject affliction semantics, so context dominates and wins. The real
boundary loses to Barnum by being an **active distractor**, not by Barnum being powerful. A generic
"internal constraint" that says nothing specific is safer than the real vṛtti composition here.

## 6. Where scramble beat/tied the real boundary

B is **≥ A in 11 of 12 cases**: B **tied** A in 10 (e000–e003, e005–e008, e010, e011) and **beat**
A in 1 (e004). A beat B in only 1 (e009, where the scramble happened to crater to rank 6). This
matches the aggregate `A_vs_B = −0.0139` ≈ 0. Conclusion: the **specific varṇa→gloss mapping added
no advantage** over a scrambled mapping of the same glosses — case-level `SCRAMBLE_EQUIVALENT`. What
little the boundary does (mostly harm on concretes) is a property of the affliction-gloss *bag*, not
of the specific assignment.

## 7. Where dictionary-only was weak

D was the **weakest arm by far** (Top-1 0.25, MRR 0.524; ranks 2–5 on most cases), because D is
**dictionary-only by design** — it shows the scorer the broad dictionary gloss with **no context**
and no boundary. A's positive `A_vs_D = +0.268` therefore only says "boundary + context beats a
context-free dictionary lookup," which is expected and **insufficient**: Track E's primary bar is
`A_vs_X` (incremental over **context**), which A **fails**. Beating an intentionally weak baseline
is not evidence of a boundary constraint.

## 8. Design diagnosis

Ranked by fit to the evidence:

1. **Contexts too informative (primary).** X ranks the correct candidate #1 in 11/12 cases
   (MRR 0.958) — the test is near-ceiling and has almost no headroom to detect boundary value. This
   is the dominant structural issue; "scoring model overweights context" is the same phenomenon
   from the model's side.
2. **Real boundary too noisy (secondary).** Where the boundary does change the ranking (concretes,
   e004) it makes it **worse** — the flat affliction-vṛtti composition behaves as a domain-mismatched
   distractor, not a constraint.
3. **Scrambled boundary equivalent (confirmed).** B ≈ A everywhere; the specific mapping is inert.

Not well supported: *candidate set too easy* (hard negatives are semantically adjacent, and D's poor
showing indicates the sets are not trivially separable without context); *Barnum too strong* (Barnum
was inert, not strong — see §5).

## 9. Next-step recommendation

**Revise context/candidate difficulty and rerun the smoke once — with a pre-committed stop rule.**
Rationale: the primary finding is confounded by context saturation (§8.1), so the current negative
cannot cleanly separate "boundary is useless" from "test had no headroom." One cheap rerun with
**harder, more ambiguous contexts** (target a lower X baseline, e.g. X MRR ≲ 0.75, so context does
not pre-solve the item) would resolve the confound. **Stop rule (pre-committed):** if the real
boundary still does not beat context-only (`A_vs_X ≤ 0` / CI includes 0) on the harder set, **stop
the flat-boundary Track E path.** Expectations are low given the concrete-distractor behavior, so
this is a single confound-resolving check, **not** a fishing expedition.

This is the recommended single next step over the alternatives (*stop now* is also defensible given
§8.2; *four-sphere Track E-FS* would be a **separate new pre-registration**, not a rescue of this
result; *abandon semantic-boundary testing* is premature until the ceiling confound is resolved).

## 10. No-rescue rule

This diagnostic **cannot** convert `CONTEXT_ONLY_EXPLAINS` into a positive, a
`BOUNDARY_CONSTRAINT_SIGNAL`, or any support for Symbol-U. The recommended rerun (if run) is a
**new measurement with its own pre-commitment and stop rule** — it does not reinterpret, soften, or
overturn this result, and it does not touch the Track C / D0 negatives or the Track B block. A
positive would only ever be found in a *future* pre-registered test, never retrofitted here.

## 11. Boundary statement

Diagnostic breakdown only. Track E smoke result remains CONTEXT_ONLY_EXPLAINS. Track B remains blocked. Structure, not validated meaning.
