# MILESTONE_A_PRIME_EXECUTION_STATUS

> **STATUS — A′ execution attempt: NOT EXECUTED (blocked by data availability).**
> Documentation only. No analysis run, no A1.3 selection, no A1.8 freeze, no Stage A /
> structural_v1 change, ⊥ preserved. Records the outcome of attempting to source the A′ inputs
> under `MILESTONE_A_PRIME_PREREGISTRATION.md` + `…_AMENDMENT_1.md`. **No third-party data is
> committed** (no license supplied). Date: 2026-06-29. **structure, not validated meaning.**

## 1. What this records
A′ (the existing-data conditional-MI falsifier, estimand `I(Y ; E | Phonology)`) requires an
admissible, mutually-available, **construct-aligned** pairing of a gloss-free sound-symbolism
`E` source and a real-word semantic observable `Y`. This document records that **no such pairing
could be assembled** from the supplied/reachable data, and therefore A′ was **not executed**.
This is **not** an inferential outcome (not `⊥`, not INCONCLUSIVE, not PASS/FAIL) — those require
a completed run. It is a **feasibility/acquisition outcome**.

## 2. Artifacts supplied (verified; provenance only, no rating values inspected)
| File | sha256 | Identity | Verdict |
|---|---|---|---|
| `SoS_Pseudoword_Database.xlsx` | `957ea2c3…dc11` | McCormick, Kim, List & Nygaard (2015), bouba-kiki; 537 CVCV pseudowords, **per-stimulus SHAPE (roundedness–pointedness) ratings**, IPA segment columns | Valid gloss-free per-stimulus `E` source — **SHAPE only** |
| `Explanation_of_Stimulus_Set_Variables.pdf` | `316266c1…ba78c` | Codebook for the above | Codebook only |
| `media1.docx` | `2b48599f…32b8` | Lacey, Matthews, Sathian & Nygaard — C2 paper **Supplementary Material** | **Summary statistics** (anchor words, VIF, Durbin-Watson, per-domain regression β's, top-10 feature counts). Confirms the C2 study rated 8 domains **incl. SIZE**, but contains **no per-pseudoword ratings** |

**License:** none of the three files carries a redistribution/derivative license (A1.2 criterion
5 unmet). Therefore the data is **not committed** to this repository.

## 3. The binding obstacle — no construct-aligned `E`×`Y` pairing
| Dimension | `E` (gloss-free sound-symbolism) | `Y` (real-word semantic norm) | Pairing usable? |
|---|---|---|---|
| **SIZE** | **unavailable** — C2 per-pseudoword size ratings not in released form (only summary stats in `media1.docx`) | Glasgow SIZE exists (but host-blocked) | **No** — `E` missing |
| **SHAPE** | **available** — McCormick `SoS_Pseudoword_Database.xlsx` | **none exists** — no standard real-word semantic shape/roundedness norm (Glasgow, Lancaster, MRC carry size/valence/sensorimotor/concreteness, **not** shape) | **No** — `Y` missing |

The two halves never meet: a SIZE `Y` with no SIZE `E`; a SHAPE `E` with no SHAPE `Y`. Searches
for a real-word shape/roundedness semantic norm returned none. Using the C2 regression β's as
`E` is inadmissible (a phonetic-feature→rating model — the path-2 phonology collapse — and not
the pre-registered A1.4 per-stimulus projection). Pairing the McCormick shape `E` with any
non-shape `Y` (e.g., size) would be **construct-misaligned and result-seeking**, which A1.3/A1.7
forbid.

## 4. Outcome

> **A′ NOT EXECUTED — blocked by data availability.** No admissible, construct-aligned,
> mutually-available `E`×`Y` pairing exists with current data. No selection, no freeze, no
> feasibility test, no analysis, no decision emitted. `⊥` is **not** asserted (no run occurred).

This is consistent with the program's standing premise that **data, not code, is the binding
constraint**. Recording an honest "cannot run for lack of an admissible pairing" is the roadmap
operating as designed, not a failure to be worked around. (External published context, not an A′
result: the C2 supplement reports SIZE as the **weakest** phonetics-predicted domain — Small
R²=.12, Big R²=.29 — consistent with the negative priors for any size-based signal.)

## 5. What would unblock A′ (each separately authorized; none taken)
1. **SIZE route (preferred, construct-aligned):** obtain the **C2 per-pseudoword multi-domain
   ratings table** (one row per pseudoword incl. a mean SIZE column) **with a redistribution
   license**, plus reachable access to a size `Y` (Glasgow SIZE) — i.e., egress to the blocked
   hosts or out-of-band delivery of both `E` and `Y` + licenses.
2. **SHAPE route (only if a `Y` appears):** adopt the McCormick shape `E` **and** source an
   admissible real-word semantic **shape** norm `Y` (none currently known) **and** supply the
   McCormick data license; then log the construct-aligned endpoint amendment per A1.7.
3. **Engineering de-risk (optional, no decision value):** with the McCormick file used locally
   (not redistributed), build and **bit-freeze the per-phoneme SHAPE `E′`** via the A1.4
   deterministic projection to verify the projection pipeline end-to-end. This produces no A′
   decision (no `Y`), and any committed artifact still requires a license.
4. **Accept the documented feasibility-halt** as the honest current endpoint of the cheap-test
   phase until an admissible pairing becomes available.

## 6. Constraints honored
No raw third-party data committed (no license); no code that yields a result was run; no rating
values inspected (schema/headers/labels only); no A1.3 selection; no A1.8 freeze; no feasibility
or confirmatory analysis; `⊥` semantics preserved; **Stage A / structural_v1 untouched**
(empty diff vs `2d42bf6`).

---
> **A′ not executed · data-availability blocked · no decision emitted · no data redistributed ·
> ⊥ preserved · Stage A untouched.** **structure, not validated meaning.**
