# DilChat — Astronomy / Astrology Reproducibility Audit

**Auditor role:** Independent verification (astronomy reproducibility & determinism).
**Audit date:** 2026-08-04
**Scope of this document:** Verify that the DilChat astrology/astronomy design specifies each
reproducibility-critical element *unambiguously*, and that a second implementer, given only the
frozen spec + pinned version surface, would produce byte-identical astronomical output.
**Deliverable constraint:** This is an audit only. No code was written; no other file was modified.

**Primary evidence (cited verbatim with line refs):**
- `DILCHAT_ASTROLOGY_ENGINE_SPEC.md` (the engine spec, 1185 lines) — abbreviated **SPEC** below.
- `DILCHAT_DECISION_LOG.md` — abbreviated **LOG** below. Relevant decisions: **DEC-007**
  (ephemeris + Moshier fallback + process pool), **DEC-008** (Lahiri ayanamsa), **DEC-017**
  (geocoding + historical timezone).

**Method:** For each of 14 reproducibility elements I quote the controlling text with a line
reference and assign **PASS** (specified unambiguously; a re-implementer could not diverge),
**PARTIAL** (specified but with a gap, defect, or under-constrained edge that could cause
divergence), or **GAP** (not pinned; divergence possible). Determinism and natal/transit
separation are audited separately. A dedicated section evaluates the Moshier fallback policy for
the immutable classical Guna Milan artifact and records the required recommendation.

---

## 1. Element-by-element verification

### 1.1 Local → UTC conversion — **PASS**

The conversion is a single explicit, machine-locale-independent call.

> SPEC §2.3 L158–160: *"Stage C — convert to UTC [Technical] `dt_utc =
> dt_local_aware.astimezone(timezone.utc)`. Downstream stages consume only `dt_utc`."*

Reinforced in the natal pseudocode:

> SPEC §11.1 L1030: *"`dt_utc = canonical.astimezone(timezone.utc)`"*

The input to this stage is an *aware* datetime produced by Stage B (§2.2), so the offset applied is
the historical offset at the birth instant, not a modern fixed offset. The `astimezone` conversion
is deterministic and carries no wall-clock, RNG, or locale dependence (satisfies INV-D1, L50–52).
**No ambiguity: PASS.**

### 1.2 Historical IANA timezone handling (zoneinfo / tzdata) — **PASS**

The zone *name* (never a numeric offset) is stored, and localization uses pinned tzdata.

> SPEC §2.1 L117–120: *"birthplace string → coordinates via bundled GeoNames `geonames-2025-Q3`;
> coordinates → IANA zone name via `timezonefinder` (offline). The zone name (e.g. `Asia/Kolkata`)
> is stored, never a fixed numeric offset — historical offset/DST rules live in tzdata and must be
> applied at the birth instant, not 'now'."*

> SPEC §2.2 L124–127: *"It is localized with `zoneinfo.ZoneInfo(zone_name)` backed by pinned
> `tzdata-2025b`."*

> SPEC §2.2 L154–156: *"Historically, many zones also have pre-standardization LMT (local mean
> time) intervals and one-off legal offset changes; tzdata encodes these and they are applied
> automatically because we localize at the birth instant through the historical zone, not at a
> fixed modern offset."*

The tzdata snapshot is pinned in the provenance tuple (SPEC §1.3 L87 `tz_dataset_version:
"tzdata-2025b"`; LOG DEC-017 L340–343; LOG §0 L49). Because a tzdata revision can change historical
offsets, pinning it into the version surface is exactly what makes localization reproducible.
Historical-timezone golden tests are mandated (SPEC §10.5 L991–995). **PASS.**

### 1.3 Julian Day convention (swe.julday, UT) — **PASS**

The Julian Day call, its argument construction, and the calendar flag are fully pinned.

> SPEC §2.4 L164–167:
> *"`decimal_hour = dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600 + dt_utc.microsecond/3.6e9`
> `jd_ut = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, decimal_hour, swe.GREG_CAL)`"*

> SPEC §2.4 L170–171: *"`swe.GREG_CAL` selects the proleptic Gregorian calendar."*

> SPEC §2.4 L176–177: *"`swe.julday` returns a Julian Day in UT. Swiss Ephemeris internally applies
> ΔT (`swe.deltat`) when `swe.calc_ut` converts UT→TT; DilChat does not compute ΔT by hand."*

The UT convention is consistent end-to-end: `julday` produces a UT Julian Day and `calc_ut` (not
`calc`) consumes it, so ΔT is handled inside Swiss Ephemeris rather than duplicated. Pre-1582
Gregorian-cutover births are explicitly out of MVP scope and rejected at input validation
(L170–174), removing the one calendar ambiguity. The `microsecond/3.6e9` term makes the hour
fraction exact to the stored precision. **PASS.**

### 1.4 Sidereal mode (FLG_SIDEREAL) — **PASS**

> SPEC §2.5 L187–189:
> *"`flags = swe.FLG_SIDEREAL | swe.FLG_SWIEPH | swe.FLG_SPEED`
> … `xx, ret_flag = swe.calc_ut(jd_ut, swe.MOON, flags)`"*

> SPEC §2.5 L201–203: *"With `FLG_SIDEREAL` set (after `set_sid_mode`), `xx[0]` is the sidereal
> ecliptic longitude — Swiss Ephemeris has already subtracted the Lahiri ayanamsa. DilChat reads
> `xx[0]` and `xx[3]`; it never re-derives them."*

The flag is applied on both the natal path (§2.5, §11.1 L1035) and the transit path (§7.1 L668–670,
§7.2 L687). The spec is explicit that DilChat does **not** perform the tropical→sidereal subtraction
itself (§3.1 L216–219), eliminating a classic source of divergence between implementations. **PASS.**

### 1.5 Lahiri ayanamsa (swe.set_sid_mode / SE_SIDM_LAHIRI) — **PASS**

> SPEC §2.5 L184: *"`swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)  # C name SE_SIDM_LAHIRI; t0=0,
> ayan_t0=0 (defaults)`"*

> SPEC §3.1 L216–219: *"The zodiac is sidereal with Lahiri ayanamsa (DEC-008). … it sets
> `swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)` and requests `FLG_SIDEREAL`, so `swe.calc_ut` returns
> the sidereal value directly."*

> LOG DEC-008 L194–196: *"Default sidereal ayanamsa is Lahiri (`SE_SIDM_LAHIRI`)… The ayanamsa is a
> versioned input (`ayanamsa="lahiri"`) recorded on every chart."*

The `set_sid_mode` call is specified as a **once-per-worker init** step (SPEC §2.5 L182–184; INV-D3
L55–59), which both pins the ayanamsa and satisfies the thread-safety constraint (§1.11 below). The
two extra arguments `(0, 0)` are stated with their meaning, so a re-implementer cannot silently pick
a different reference date. `ayanamsa="lahiri"` is in the provenance tuple (§1.3 L79). **PASS.**

### 1.6 Moon longitude normalization to [0,360) — **PASS**

> SPEC §2.5 L196: *"`moon_sid_lon = xx[0] % 360.0     # degrees in [0,360); already sidereal because
> FLG_SIDEREAL set`"*

Confirmed by the primary auditor and reproduced here: the normalization is the Python modulo
`xx[0] % 360.0`, which for the CPython float semantics yields a result in the half-open interval
`[0.0, 360.0)` (the result takes the sign of the divisor `+360.0`, so negative raw longitudes wrap
up into range). The storage policy pins that the **round to 1e-6 happens exactly once**, immediately
after this modulo, and that rounded value is the sole downstream input:

> SPEC §3.2 L228–232: *"All longitudes stored as decimal degrees rounded half-to-even to 1e-6° …
> The round happens once, immediately after reading `xx[0] % 360`, and the rounded value is the
> sole input to every downstream classification. Downstream code never re-reads the raw float."*

> SPEC §11.1 L1044: *"`lon = round_1e6(xx[0] % 360.0)`"*

The "normalize once, round once, never re-read the raw float" rule is the exact discipline that
makes cross-machine classification deterministic. **PASS.**

### 1.7 Rashi boundaries (30°) — **PASS**

> SPEC §4.1 L262, L269: *"`DEG_PER_RASHI = 30.0`" … "`rashi_index = floor(lon_adj /
> DEG_PER_RASHI)  # 0..11`"*

The full 12-rashi table with explicit spans is pinned, e.g.:

> SPEC §4.3 L335: *"`| 11 | Meena | Pisces | 330–360 |`"* (and L323–334 for the other eleven).

Boundaries are integer multiples of 30°; classification is `floor` after the cusp snap-up and a
`clamp(…, 0, 11)` (L269, L274). Boundary tests at multiples of 30° are mandated (§10.4 L986). **PASS.**

### 1.8 Nakshatra boundaries (13°20′) — **PASS**

> SPEC §4.1 L263: *"`DEG_PER_NAKSHATRA = 40.0 / 3.0          # 13.3333333333...  (27 nakshatras over
> 360°)`"*

Critically, the constant is stored as the **exact fraction `40/3`**, not a truncated decimal
`13.333` — the spec calls this out explicitly to avoid float drift:

> SPEC §4.1 L258–259: *"Constants (exact fractions to avoid float drift; `13°20' = 40/3 =
> 13.333333…`, `3°20' = 10/3 = 3.333333…`)"*

The confirmed-evidence note (`DEG_PER_NAKSHATRA = 40/3`) is reproduced and corroborated. The full 27
nakshatra table with start/end degrees is pinned (SPEC §4.2 L290–318), and the `nakshatras.json`
rule-pack file canonicalizes it (§6.2 L608). Boundaries at multiples of 13°20′ are golden-tested
(§10.4 L986). **PASS.**

### 1.9 Pada boundaries (3°20′) — **PASS**

> SPEC §4.1 L264: *"`DEG_PER_PADA      = 10.0 / 3.0          # 3.3333333333...   (4 padas per
> nakshatra)`"*

> SPEC §4.1 L271–272:
> *"`pos_in_nak = lon_adj - nakshatra_index * DEG_PER_NAKSHATRA   # 0..13.333`
> `pada_index = floor(pos_in_nak / DEG_PER_PADA)          # 0..3`"*

Again the exact fraction `10/3` is used, and pada is derived from the residual position within the
nakshatra (not from an independent global grid), so nakshatra and pada indices are guaranteed
consistent. `clamp(…, 0, 3)` guards the top boundary (L276). Pada boundary tests at multiples of
3°20′ are mandated (§10.4 L986). **PASS.**

### 1.10 Ephemeris version pinning (swe-2.10.03) — **PASS**

> SPEC §1.3 L76–77: *"`ephemeris_provider: "swiss" | "moshier",   # runtime-resolved (INV-D4)` …
> `ephemeris_version: "swe-2.10.03",`"*

> LOG §0 L39: *"`| ephemeris_version | swe-2.10.03 | Pinned Swiss Ephemeris release |`"*

The version string is part of the determinism hash version-fields (SPEC §1.3 L93–94: *"The
determinism hash is `sha256(canonical_json(inputs) || canonical_json(version_fields))`"*) and any
change to it produces new rows, never in-place edits (§9.1 L934–938, INV-D5 L63–64). The `.se1`
data files are additionally baked into the container at a pinned checksum:

> LOG DEC-007 L164–166: *"Ephemeris files: `semo_*.se1` (Moon) and `sepl_*.se1` (planets…) covering
> the supported birth-year range, baked into the container image at a pinned checksum."*

Pinning both the library version *and* the data-file checksum closes the two independent axes along
which ephemeris output could drift. **PASS.**

### 1.11 Calculation backend (pyswisseph, single-threaded process pool) — **PASS**

> LOG DEC-007 L159–161: *"Astronomy is computed in-house via `pyswisseph` (Python binding to Swiss
> Ephemeris), running inside the `astrology` module."*

> LOG DEC-007 L174–179: *"the Swiss Ephemeris C library holds global state (ayanamsa mode, ephemeris
> path) and is not thread-safe for concurrent mutation. DilChat wraps it behind a single-threaded
> calculation worker pool (dedicated process pool; each process sets `swe.set_ephe_path` /
> `swe.set_sid_mode` once at init and never mutates mid-request). Calls are submitted to this pool;
> the FastAPI async handlers never call `swe.*` directly."*

> SPEC INV-D3 L55–59: *"All `swe.*` calls run inside a dedicated single-threaded calculation process
> pool; each worker calls `swe.set_ephe_path` and `swe.set_sid_mode` once at init and never mutates
> that state mid-request. FastAPI async handlers never call `swe.*` directly."*

This is the correct architecture for a stateful, non-reentrant C library: because global ephemeris
state (path + ayanamsa) is set once per process and never mutated mid-request, no request can
observe another request's partially-applied `set_sid_mode`, which would otherwise be a nondeterminism
source under concurrency. The backend, its isolation, and its concurrency model are all pinned. **PASS.**

### 1.12 Fallback policy (Moshier) — **PARTIAL**

The *mechanics* of fallback and its provenance labeling are specified rigorously; two issues keep
this from a clean PASS (one editorial, one substantive — the substantive one is the subject of §4).

Specified correctly:

> SPEC INV-D4 L60–62: *"If the `.se1` files are absent the engine degrades to the Moshier analytical
> ephemeris, stamps `ephemeris_provider="moshier"`, lowers confidence, and emits an ops alert. It
> never returns an unlabeled result (DEC-007)."*

> SPEC §2.5 L191–194: *"`except swe.Error:   # .se1 files absent / unreadable`
> `    flags = swe.FLG_SIDEREAL | swe.FLG_MOSEPH | swe.FLG_SPEED   # Moshier analytical fallback`
> … `    provider = "moshier"`"*

> SPEC §2.5 L205–208 (provider cross-check): *"if the caller requested `FLG_SWIEPH` but Swiss
> Ephemeris silently fell back to Moshier internally (it sets a bit in the return flag), DilChat
> treats the result as `provider="moshier"` (INV-D4). No unlabeled Moshier result can escape."*

This is a strong design point, confirmed by the primary auditor: provider is **runtime-resolved**,
and even a *silent internal* Swiss→Moshier fallback (detected via the return-flag bit) is re-stamped
`moshier`. There is no path by which an unlabeled Moshier value reaches storage. Confidence is
lowered by an explicit, versioned multiplier:

> SPEC §8.5 L905–906: *"`ephemeris_provider="moshier"` fallback (INV-D4) → ×0.97 (Moshier is
> arcminute-accurate, ample for boundaries, so the penalty is small but non-zero and explicit)."*
> (constant `PENALTY_MOSHIER`, SPEC §11.1 L1042.)

**Issue A (editorial defect, reproducibility-affecting).** The LOG and SPEC disagree on the Moshier
flag constant. The SPEC uses the correct pyswisseph name `swe.FLG_MOSEPH` (§2.5 L192, §11.1 L1039),
but **DEC-007 L168 writes `swe.FLG_MOSELPH`**:

> LOG DEC-007 L168: *"the built-in Moshier analytical ephemeris (`swe.FLG_MOSELPH`), which needs no
> data files."*

`FLG_MOSELPH` is not a real pyswisseph symbol (the real constant is `FLG_MOSEPH`). Since the LOG is
declared *canonical* ("authoritative for all identifiers", SPEC L6; LOG L7–9), an implementer who
follows the canonical document literally would hit an `AttributeError`. This is a one-character typo
but it lives in the authoritative source and should be corrected to `FLG_MOSEPH`.

**Issue B (substantive — see §4).** The fallback policy is *fallback-with-visible-provenance for all
outputs, including the immutable classical Guna Milan scorecard*. That is safe for the daily climate
model but under-constrained for the binding classical artifact near a segment boundary. Full analysis
and the recommended hybrid policy are in §4.

Because the labeling machinery is airtight but (A) the canonical constant name is wrong and (B) the
binding-artifact edge is under-specified, this element is **PARTIAL**.

### 1.13 Numerical tolerance / epsilon (rounding to 1e-6, boundary epsilon) — **PARTIAL**

Two distinct epsilons exist in the spec and both are individually well-defined; the gap is that
neither is tied to the Moshier error budget.

**Determinism rounding + boundary snap (fully specified):**

> SPEC INV-D6 L66–67: *"Longitudes are stored to 1e-6°; boundary decisions use a defined epsilon
> (§3.3). The rounding/epsilon policy is versioned with the engine so 'same inputs + same versions ⇒
> identical output' holds across machines."*

> SPEC §3.2 L228: *"rounded half-to-even to 1e-6° (~0.0036 arcsec … the rounding is for cross-machine
> determinism, not accuracy)."* Storage type `numeric(9,6)` (L230).

> SPEC §3.3 L240–246: *"Define `EPS = 1e-6` degrees … A value within `EPS` below a boundary is
> snapped up to the boundary… classification operates on `lon_adj = lon + EPS` before the `floor`,
> then indices are clamped."*

The half-to-even rounding rule, the storage granularity, the `EPS = 1e-6` snap-up magnitude and
*direction*, and the version-pinning of that policy are all unambiguous. Boundary golden tests pin
the behavior at `boundary − 2·EPS`, `boundary`, `boundary + 2·EPS` (§10.4 L987), so a future change
to EPS or snap direction *must* break a test and force a version bump. On the determinism axis this
is exemplary.

**The gap — no Moshier safety epsilon.** The `EPS = 1e-6°` snap epsilon is a *determinism* device
sized to the storage granularity; it is roughly **0.0036 arcsec**. Moshier's worst-case Moon
longitude error is described as *arcminutes* (DEC-007 L168–169; SPEC §8.5 L905), and the test plan
relaxes the Moshier tolerance to **≤ 2 arcmin** (SPEC §10.3 L978). That is ~0.033° — about **33,000×
larger than EPS**. So the boundary epsilon protects against *float/rounding* noise but says nothing
about *provider* noise: when the true Moon is within ~2 arcmin of a rashi/nakshatra/pada boundary, a
Moshier computation can land on the *wrong side* of that boundary and the `floor` will assign a
different segment than Swiss would. Nothing in §3.3 or §8.5 sizes any guard to that error, and the
×0.97 confidence penalty does not encode boundary proximity. Because the tolerance framework is fully
specified for determinism but leaves the provider-error-vs-boundary interaction unguarded for the
binding artifact, this element is **PARTIAL** (remedied by the §4 recommendation).

### 1.14 Error handling — ambiguous DST fall-back & nonexistent spring-forward times, with confidence lowering — **PASS**

Both edge cases are handled *explicitly* (the spec's word), never guessed, and each maps to a named,
versioned confidence penalty.

**Ambiguous local time (DST fall-back):**

> SPEC §2.2 L129–132: *"When clocks are set back, a local wall time occurs twice… Python models this
> with the `fold` attribute: `fold=0` = first (earlier UTC) occurrence, `fold=1` = second."*

> SPEC §2.2 L133–142 (Policy AMB-1): *"It computes both candidate UTC instants, computes the Moon
> longitude for each, and: if both candidates fall in the same rashi and nakshatra and pada … it
> picks `fold=0` as canonical and records `ambiguity_resolved="collapsed"` …; if they differ in any
> of rashi/nakshatra/pada, it picks `fold=0` as canonical, records `ambiguity_resolved="divergent"`
> with both candidates in the trace, and applies a confidence penalty (§8.5)."*

**Nonexistent local time (spring-forward gap):**

> SPEC §2.2 L144–147: *"When clocks jump forward, a local wall time never occurs… DilChat detects
> the gap by testing whether `dt` round-trips (`dt.astimezone(utc).astimezone(zone) == dt`)."*

> SPEC §2.2 L149–152 (Policy GAP-1): *"on a detected gap, the instant is shifted forward by the gap
> length … recorded as `gap_adjusted=true`, and a confidence penalty applied (§8.5). The adjustment
> is deterministic and logged in the trace."*

**Confidence mapping (each edge lowers a specific, versioned multiplier):**

> SPEC §8.5 L903–904: *"DST fall-back ambiguity with divergent candidates (§2.2 AMB-1) → ×0.85;
> spring-forward gap adjustment (§2.2 GAP-1) → ×0.9"*

The natal pseudocode ties it together deterministically (SPEC §11.1 L1019–1055): `gap` and `amb` are
computed from `fold=0`/`fold=1` offset comparison and the round-trip test; `PENALTY_GAP`,
`PENALTY_AMBIGUOUS`, `PENALTY_TIME_UNKNOWN` are applied; and for the ambiguous case the *alternate*
candidate is re-classified and only penalized if it actually diverges (L1053–1055). Canonical choice
is always `fold=0`, so the output is deterministic regardless of which candidate is "astrologically
correct" (that correctness question is honestly flagged as a domain-review item, L142, Appendix B
item 1 L1173). The confidence-penalty behavior is itself golden-tested (§10.5 L991–995). **PASS.**

---

## 2. Determinism invariant — same inputs + same versions ⇒ identical output — **VERIFIED**

The determinism contract is stated as a first-class invariant and is threaded consistently through
the pipeline:

> SPEC INV-D1 L50–52: *"For a fixed input tuple and a fixed version tuple, the engine returns a
> byte-identical result. No wall-clock, no RNG, no network, no machine-locale dependence enters any
> calculation."*

> SPEC INV-D2 L53–54: *"No language model participates in any astronomical or scoring computation."*
> (LLMs *explain* already-computed values only — L918, DEC-014 L296–297.)

Supporting mechanics that make the invariant hold across machines:
- **No hidden inputs:** `computed_at` is explicitly excluded from the hash — *"metadata only; it is
  excluded from the determinism hash (INV-D1)"* (SPEC §1.3 L93). The hash is
  `sha256(canonical_json(inputs) || canonical_json(version_fields))` (L94).
- **Rounding is part of the contract:** INV-D6 L66–67; round-once discipline §3.2 L231–232.
- **Frozen version surface:** §9.1 L934–938 — any change to `ephemeris_version`, `ayanamsa`,
  `rule_pack_id`, `transit_model_version`, `interpretation_pack_version`, `interest_model_version`,
  or `engine_calc_version` yields new rows, never in-place edits.
- **Executable enforcement:** golden vectors store `(input_tuple, version_surface) → expected_output
  + expected_trace` and CI asserts byte-equality (§9.2 L940–944); the `CalculationTrace` is
  replayable and diffable byte-for-byte (§5.12 L565–571).
- **Exact-fraction constants** (`40/3`, `10/3`) avoid decimal-truncation drift (§4.1 L258–264).
- **Concurrency determinism:** single-threaded process pool prevents interleaved global-state
  mutation (INV-D3; §1.11 above).

The one residual determinism dependency is the *floating-point reproducibility of the Swiss
Ephemeris / Moshier C routines themselves* across CPU architectures. The spec mitigates this at the
observable layer by rounding to 1e-6° and snapping within EPS before any `floor`, which absorbs
sub-microdegree cross-arch float differences — but it does **not** absorb a provider *switch* (Swiss
vs Moshier), which the §4 recommendation addresses. Subject to that, the determinism invariant is
**well-specified and enforceable. VERIFIED.**

---

## 3. Natal vs transit separation — **VERIFIED (kept distinct)**

Natal and transit Moon values are computed by the same *astronomy* primitive but are stored in
distinct records and are never conflated:

- **Natal** Moon is produced by `derive_natal_moon(...)` → `NatalMoon(sid_lon, rashi, nakshatra,
  pada, provider, confidence, trace)` (SPEC §11.1 L1057–1058) and persisted as a natal chart
  fragment (§1.1 L34–38).
- **Transit** Moon is produced for the day's reference instant and stored in a *separate* record:
  > SPEC §7.1 L668–670: *"compute the transit sidereal Moon exactly as in §2.5 … then derive transit
  > rashi / nakshatra / pada via §4.1."*
  > SPEC §7.7 L777–786: `DailyGlobalTransit = { … moon: { sid_lon, rashi_index, nakshatra_index,
  > pada_index, speed_deg_per_day }, sun: {...}, next_rashi_transition_utc, … }`.
- The two are combined only through **integer whole-sign counting from the natal value**, which
  reads both but modifies neither:
  > SPEC §7.3 L711–712: *"`def house_from_natal(natal_rashi_index, transit_rashi_index): return
  > ((transit_rashi_index - natal_rashi_index) % 12) + 1`"*
  > SPEC §11.3 L1090–1092: house and tara-count are computed from `natal.rashi` /
  > `natal.nakshatra` against `global_transit.moon.*`.

The transit record is *global* (same for everyone, Redis-cached per DEC-005; SPEC §7 L662–665, §7.7
L788), whereas natal is per-birth-profile — structurally they cannot be the same row. This also aligns
with the score-family separation invariant DEC-019 (LOG L358–372; SPEC §1.1 L44–46), under which
classical (natal-driven) and daily-climate (transit-driven) families are *"stored and versioned
separately and never merged."* Natal and transit are kept distinct: **VERIFIED.**

---

## 4. Moshier fallback review & recommendation *(required section)*

### 4.1 The question

The spec currently applies **one** fallback policy — *fallback-with-visible-provenance* (stamp
`ephemeris_provider="moshier"`, multiply confidence ×0.97) — to **every** output, including the
**immutable, binding classical Guna Milan scorecard** (SPEC INV-D4 L60–62; §8.5 L905–906; §11.1
L1042). The scorecard is an immutable stored artifact (INV-D5 L63–64; DEC-019 L360–362: *"Immutable
once computed for a given version tuple. AI may explain, never alter."*). This section evaluates
whether one uniform policy is appropriate for an immutable artifact.

### 4.2 Why Moshier is *usually* safe but not *always* safe here

Moshier Moon longitude is arcminute-accurate — SPEC §8.5 L905 (*"Moshier is arcminute-accurate,
ample for boundaries"*), DEC-007 L168–169 (*"Moon longitude accuracy (~arcminutes) is more than
sufficient for rashi/nakshatra/pada boundaries"*), and the test plan sets the Moshier oracle
tolerance at **≤ 2 arcmin** (SPEC §10.3 L978). For the overwhelming majority of birth times, a
2-arcmin (~0.033°) error is far from any segment boundary and the derived rashi/nakshatra/pada are
identical to Swiss — so the ×0.97-labeled result is genuinely equivalent.

The failure mode is **narrow but real**: the classical Guna Milan kootas are computed *entirely* from
the discrete rashi and nakshatra indices (and pada for some exceptions), never from the continuous
longitude — e.g. Nadi reads `nadi_by_nakshatra[...]` (SPEC §5.9 L512–515), Bhakoot reads rashi
indices (§5.8 L495–502), Yoni/Gana/Tara read nakshatra (§5.4–5.7). If the natal Moon's *true*
longitude sits within Moshier's worst-case error (~2 arcmin) of a **nakshatra** boundary, Moshier can
place it in the adjacent nakshatra. That single-index shift can flip a high-weight dosha — **Nadi is
worth 8 of 36 points** (§5.1 L385) and toggles entirely on same-vs-different nadi class (§5.9
L514–515) — turning a same-nadi 0 into a different-nadi 8 (or vice versa). An 8-point swing on a
36-point classical scorecard, then frozen immutably, is a materially wrong binding artifact. The
existing `EPS = 1e-6°` snap (§3.3) does **not** defend against this: it is ~33,000× smaller than the
Moshier error (see §1.13). And the ×0.97 confidence tag communicates *"Moshier was used"* but not
*"this Moon is near a boundary where Moshier could be on the wrong side"* — the two situations are
indistinguishable to a downstream consumer.

### 4.3 Options compared

| Option | Binding Guna Milan behavior when `.se1` absent | Correctness near boundary | Availability | Reproducibility / immutability posture | Verdict |
|--------|-----------------------------------------------|---------------------------|--------------|----------------------------------------|---------|
| **A. Fail-closed to Swiss** | Refuse to emit any binding scorecard without Swiss ephemeris; queue/deny | Cannot emit a wrong-side classical score | Lowest — a missing-`.se1` outage blocks *all* new Guna Milan reports | Strongest — every stored classical artifact is Swiss-grade; no provider ambiguity ever frozen | Safe but operationally brittle |
| **B. Fallback-with-provenance for everything (current spec)** | Compute on Moshier, stamp `moshier`, ×0.97, freeze | Can freeze a wrong nakshatra/nadi within ~2 arcmin of a boundary | Highest — always produces a number | Weakest for the *binding* artifact: a labeled-but-possibly-wrong immutable score, indistinguishable near-boundary from a safe one | Fine for non-binding, risky for binding |
| **C. Fallback only for non-binding previews** | Never Moshier for binding; Moshier allowed only for daily climate / previews | No wrong-side binding score | Medium — daily features stay live; binding reports wait for Swiss | Strong for binding; pragmatic for daily | Good, but coarse (blocks *all* Moshier binding even far from boundaries) |

### 4.4 Recommendation — adopt a boundary-aware hybrid

**Record the following as the audit's conclusion.**

- **Daily Moon climate (non-binding, transit-derived — DEC-019 family 2):** *fallback-with-provenance
  is ACCEPTABLE.* Daily climate is regenerated every local midnight (SPEC §7.8 L791–798), is not an
  immutable legal-style artifact, and already carries the ×0.97 confidence and `moshier` stamp. No
  change needed here.

- **Classical Guna Milan binding scorecard (the immutable stored artifact — DEC-019 family 1):**
  adopt a **boundary-aware hybrid**:
  1. **Fail-closed to Swiss Ephemeris** when the natal Moon (of *either* partner) is within a
     **safety-epsilon** of *any* rashi, nakshatra, or pada boundary. The safety-epsilon must be
     **sized to Moshier's empirical worst-case Moon longitude error** — recommend **≥ a few arcminutes**
     (a defensible starting value is ~3–5 arcmin, i.e. comfortably above the ≤ 2 arcmin oracle
     tolerance of §10.3 L978, with the exact value confirmed empirically in golden tests). Within this
     band the binding report is **not** emitted from Moshier; it waits for Swiss.
  2. **Otherwise** (natal Moon comfortably inside a segment, > safety-epsilon from every boundary),
     Moshier **MAY** be used, but the emitted report must be marked **`provisional`** with
     **`recompute_pending_swiss = true`**, so a versioned recompute sweep (arq, DEC-006; SPEC §9.3
     L946–955) regenerates it from Swiss once the ephemeris is available. This preserves availability
     without freezing a Moshier value as the permanent record.
  3. **Never** emit an **unlabeled** Moshier-based binding classical score — this already holds under
     INV-D4 / the return-flag cross-check (§2.5 L205–208) and must be retained.

This hybrid keeps the daily product fully available, guarantees no *wrong-side* classical score is
ever frozen, and keeps a clean, reproducible immutability story (a provisional Moshier score is
explicitly a placeholder pending Swiss recompute, not a competing permanent artifact). It is a
strict refinement of the current spec: it changes only the *binding* path and only *near boundaries*.

### 4.5 Note on the safety-epsilon vs the determinism EPS

These are two different epsilons and must not be conflated. `EPS = 1e-6°` (§3.3) is a *cross-machine
float-determinism* snap and stays as-is. The proposed *safety-epsilon* (a few arcmin) is a
*provider-error guard* used only to decide **fail-closed-vs-Moshier for the binding artifact**; it is
not applied to the `floor` classification and does not alter any Swiss-computed result. It should be a
new versioned field (e.g. under `engine_calc_version`) and pinned by golden boundary tests against
Moshier's measured worst-case error (extend §10.4 L984–989 to assert the fail-closed trigger fires).

---

## 5. Minor defects & follow-ups noted during audit

1. **Canonical constant typo (should fix):** DEC-007 L168 writes `swe.FLG_MOSELPH`; the correct
   pyswisseph symbol used everywhere in the SPEC is `swe.FLG_MOSEPH` (§2.5 L192, §11.1 L1039). Since
   the LOG is the canonical identifier source, correct it there. *(Reproducibility impact: literal
   follow of the canonical doc would raise `AttributeError`.)*
2. **Safety-epsilon undefined (see §4):** no epsilon is sized to Moshier's Moon error; the binding
   artifact has no near-boundary guard. Adopt the §4.4 hybrid and pin the value empirically.
3. **Cross-architecture float reproducibility of the C ephemeris** is assumed, not asserted. The
   1e-6 round + EPS snap absorb sub-µ° differences, but the golden-vector CI (§9.2) should run on the
   same architecture(s) as production, or the tolerance argument should be documented explicitly.
4. **Licensing is a separate, tracked blocker, not an astronomy-reproducibility defect.** Swiss
   Ephemeris is AGPL-or-commercial (DEC-007 L181–188, OQ-10 L445). This does not affect *whether the
   math reproduces*; it is flagged only so it is not mistaken for an in-scope pass/fail here.

---

## 6. Status table (14 items)

| # | Element | Controlling evidence | Status |
|--:|---------|----------------------|:------:|
| 1 | Local → UTC conversion | SPEC §2.3 L158–160; §11.1 L1030 | **PASS** |
| 2 | Historical IANA tz (zoneinfo/tzdata) | SPEC §2.1 L117–120; §2.2 L124–127, L154–156; DEC-017 L340–343 | **PASS** |
| 3 | Julian Day (swe.julday, UT) | SPEC §2.4 L164–177 | **PASS** |
| 4 | Sidereal mode (FLG_SIDEREAL) | SPEC §2.5 L187–189, L201–203 | **PASS** |
| 5 | Lahiri ayanamsa (set_sid_mode / SE_SIDM_LAHIRI) | SPEC §2.5 L184; §3.1 L216–219; DEC-008 L194–196 | **PASS** |
| 6 | Moon longitude normalization to [0,360) | SPEC §2.5 L196; §3.2 L228–232; §11.1 L1044 | **PASS** |
| 7 | Rashi boundaries (30°) | SPEC §4.1 L262,L269; §4.3 L323–335 | **PASS** |
| 8 | Nakshatra boundaries (13°20′ = 40/3) | SPEC §4.1 L258–263; §4.2 L290–318 | **PASS** |
| 9 | Pada boundaries (3°20′ = 10/3) | SPEC §4.1 L264, L271–272 | **PASS** |
| 10 | Ephemeris version pinning (swe-2.10.03) | SPEC §1.3 L76–77; DEC-007 L164–166; LOG §0 L39 | **PASS** |
| 11 | Backend (pyswisseph, single-threaded pool) | DEC-007 L159–179; SPEC INV-D3 L55–59 | **PASS** |
| 12 | Fallback policy (Moshier) | SPEC INV-D4 L60–62; §2.5 L191–208; §8.5 L905–906 — **but** DEC-007 L168 constant typo + binding-artifact edge (§4) | **PARTIAL** |
| 13 | Numerical tolerance/epsilon (1e-6, boundary EPS) | SPEC INV-D6 L66–67; §3.2 L228–232; §3.3 L240–246 — determinism EPS solid; no Moshier safety-epsilon (§1.13) | **PARTIAL** |
| 14 | Error handling (ambiguous DST / spring-forward gap + confidence) | SPEC §2.2 L129–152; §8.5 L903–904; §11.1 L1019–1055 | **PASS** |

**Supplementary invariants:** Determinism (INV-D1/D6, §9) — **VERIFIED.** Natal vs transit kept
distinct (§7.1/§7.3/§7.7, DEC-019) — **VERIFIED.**

Tally: **12 PASS · 2 PARTIAL · 0 GAP.**

---

## 7. Overall verdict

# **ASTRONOMY_REPRODUCIBLE_WITH_CONDITIONS**

The astronomy pipeline is specified to a genuinely reproducible standard: every stage from
local-clock-time → IANA zone → UTC → Julian Day (UT) → sidereal Lahiri Moon longitude →
rashi/nakshatra/pada is pinned to concrete `swe.*` calls, exact-fraction segment constants, a
once-only 1e-6 rounding rule, a versioned boundary-snap epsilon, an explicit determinism hash over
inputs+versions, a single-threaded process pool that removes the C library's concurrency
nondeterminism, and golden-vector CI that makes the determinism invariant executable. DST fall-back
and spring-forward errors are handled explicitly with deterministic canonicalization and named
confidence penalties. Natal and transit values are structurally separate. A competent second
implementer, given the frozen version surface, would reproduce Swiss-provider output.

The verdict is **conditional**, not clean, on the following:

1. **Adopt the boundary-aware fail-closed policy for the binding classical Guna Milan report** (§4.4):
   fail-closed to Swiss when either natal Moon is within a safety-epsilon of any rashi/nakshatra/pada
   boundary; otherwise Moshier is permitted only if the report is marked `provisional` with
   `recompute_pending_swiss=true`. This closes the one path by which an *immutable* classical
   scorecard could freeze a wrong-side (e.g. Nadi 8↔0) value. Daily non-binding climate may keep
   fallback-with-provenance unchanged.
2. **Confirm the boundary safety-epsilon against Moshier's empirical worst-case Moon error in golden
   tests** (§4.4/§4.5, extending §10.4) — recommend ≥ a few arcminutes, validated, not assumed.
3. **Fix the canonical constant typo** `swe.FLG_MOSELPH` → `swe.FLG_MOSEPH` in DEC-007 L168 (§5.1).
4. **Swiss Ephemeris licensing** (AGPL-vs-commercial, DEC-007 / OQ-10) is a **separate launch blocker
   tracked elsewhere** and is explicitly *not* a factor in this astronomy-reproducibility verdict.

Once conditions 1–3 are folded into the spec and pinned by tests, the binding-artifact edge closes
and the engine would qualify as unconditionally `ASTRONOMY_REPRODUCIBLE`.

*End of DILCHAT_ASTRONOMY_REPRODUCIBILITY_AUDIT.md*
