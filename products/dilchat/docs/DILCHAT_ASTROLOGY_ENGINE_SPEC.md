# DilChat — Astrology Engine Specification

> **Hardening update (Phase A/B):** Boundary classification is now exact half-open rational Decimal arithmetic (no 1e-6 snap-up, DEC-033). Birth time is an uncertainty interval evaluated across the interval (DEC-031/032). Fake provider is synthetic/test-only (DEC-029). See `DILCHAT_PHASE_A_B_HARDENING_REPORT.md` and Decision-Log DEC-029…DEC-035.

**Product:** DilChat (consumer) · **Company:** Ugence Labs · **Site:** dilchat.com
**Module:** `astrology`, `guna_milan`, `moon_transits` (see DEC-002 dependency order)
**Status of this document:** Design phase. **DESIGN-ONLY — no production code.**
**Canonical reference:** `DILCHAT_DECISION_LOG.md` (authoritative for all identifiers and versions).

---

## 0. How to read this spec — provenance labels

Every substantive statement in this document carries one of the following labels so a
reviewer can route it correctly. This is a hard requirement of the DilChat design process.

| Label | Meaning |
|-------|---------|
| **[Technical]** | Software/engineering decision, verifiable in code. |
| **[Traditional Vedic rule]** | A classical rule attributed to the Vedic astrology tradition. The rule pack cites its textual source (DEC-009). |
| **[DilChat proprietary interpretation]** | A DilChat product model — a scoring/mapping invented by DilChat. **Not** a classical prediction (DEC-019). |
| **[Unverified astrology-domain assumption — requires domain review]** | A domain claim the spec author is **not certain** about. Must be confirmed by a Vedic-astrology domain expert before the rule pack is frozen (OQ-1). |

**Non-fabrication rule (binding on this document):** where a real ephemeris library
(Swiss Ephemeris / `pyswisseph`) supplies a value, this spec describes the **call and its
inputs/outputs** and never invents the astronomical math. Where a classical rule is applied,
it is labeled and delegated to the versioned rule pack. Where DilChat interprets, it is
labeled proprietary.

---

## 1. Overview, determinism & versioning invariants

### 1.1 What the engine produces

The astrology engine turns a **birth event** (local date, local clock time, place) into:

1. A **natal chart fragment** — for the MVP, principally the **sidereal Moon longitude** and
   everything derived from it: rashi, nakshatra, pada (DEC: Moon-centric because Guna Milan and
   the daily transit model are Moon-driven). Ascendant is **MVP-optional** (OQ-4).
2. A **Guna Milan (Ashtakoota) compatibility report** for a couple (0–36), from two natal Moons
   and the rule pack `ashtakoota_lahiri_classical_v1`.
3. A **daily Moon-transit feature set** (global) plus **per-user derived interest/climate
   scores** [DilChat proprietary interpretation].

These map onto the three **separately versioned, never-merged** score families of DEC-019:
Classical Compatibility (Guna Milan), Daily Emotional & Interest Climate (transit-derived),
and Living Compatibility (behavioral — out of scope for this engine).

### 1.2 Determinism invariants [Technical]

- **INV-D1 (pure function of pinned inputs).** For a fixed input tuple and a fixed version
  tuple, the engine returns a **byte-identical** result. No wall-clock, no RNG, no network, no
  machine-locale dependence enters any calculation.
- **INV-D2 (no LLM in calculation).** No language model participates in any astronomical or
  scoring computation (DEC-014). LLMs only *explain* already-computed, schema-validated values.
- **INV-D3 (single-threaded ephemeris worker).** The Swiss Ephemeris C library holds global
  process state (ayanamsa mode, ephemeris path) and is not safe for concurrent mutation
  (DEC-007). All `swe.*` calls run inside a **dedicated single-threaded calculation process
  pool**; each worker calls `swe.set_ephe_path` and `swe.set_sid_mode` **once at init** and
  never mutates that state mid-request. FastAPI async handlers never call `swe.*` directly.
- **INV-D4 (labeled degradation, never silent).** If the `.se1` files are absent the engine
  degrades to the Moshier analytical ephemeris, stamps `ephemeris_provider="moshier"`, lowers
  confidence, and emits an ops alert. It never returns an unlabeled result (DEC-007).
- **INV-D5 (immutable history).** A computed row is immutable. A version change appends a **new
  row**; it never rewrites an old one (DEC-019, §9).
- **INV-D6 (rounding is part of the contract).** Longitudes are stored to 1e-6°; boundary
  decisions use a defined epsilon (§3.3). The rounding/epsilon policy is versioned with the
  engine so "same inputs + same versions ⇒ identical output" holds across machines.

### 1.3 The provenance tuple stamped on every output [Technical]

Every artifact (chart fragment, Guna Milan report, daily profile) carries the tuple below,
sourced verbatim from `DILCHAT_DECISION_LOG.md §0`:

```
ProvenanceTuple = {
  ephemeris_provider:            "swiss" | "moshier",   # runtime-resolved (INV-D4)
  ephemeris_version:             "swe-2.10.03",
  ayanamsa:                      "lahiri",              # SE_SIDM_LAHIRI
  zodiac:                        "sidereal",
  rule_pack_id:                  "ashtakoota_lahiri_classical_v1",
  transit_model_version:         "dilchat_transit_v1",
  interpretation_pack_version:   "dilchat_interp_v1",
  interest_model_version:        "dilchat_interest_v1",
  living_compat_model_version:   "dilchat_living_v1",   # not produced by this engine
  prompt_pack_version:           "dilchat_prompts_v1",  # not produced by this engine
  geo_dataset_version:           "geonames-2025-Q3",
  tz_dataset_version:            "tzdata-2025b",
  engine_calc_version:           "dilchat_calc_v1",     # this document's algorithm revision
  computed_at:                   <RFC3339 UTC>          # provenance metadata; NOT a calc input
}
```

`computed_at` is metadata only; it is excluded from the determinism hash (INV-D1). The
determinism hash is `sha256(canonical_json(inputs) || canonical_json(version_fields))`.

---

## 2. Astronomy pipeline: birth event → sidereal Moon longitude

Pipeline stages, each a pure function feeding the next:

```
local birth datetime (naive)  ──(A)──►  IANA tz resolution (from birthplace)
        │
        └──(B)──►  localize with zoneinfo/tzdata-2025b  ──►  aware datetime + fold/gap flags
                                │
                                └──(C)──►  convert to UTC (aware)
                                                │
                                                └──(D)──►  Julian Day (UT)  via swe.julday
                                                                │
                                                                └──(E)──►  sidereal Moon longitude
                                                                            via swe.calc_ut
```

### 2.1 Stage A — birthplace → IANA zone [Technical]

Per DEC-017: birthplace string → coordinates via bundled **GeoNames `geonames-2025-Q3`**;
coordinates → IANA zone name via **`timezonefinder`** (offline). The zone **name** (e.g.
`Asia/Kolkata`) is stored, never a fixed numeric offset — historical offset/DST rules live in
tzdata and must be applied at the birth instant, not "now".

### 2.2 Stage B — localize the naive birth clock time [Technical]

Input is a **naive** local datetime — the wall-clock time on the birth certificate. It is
localized with `zoneinfo.ZoneInfo(zone_name)` backed by pinned **`tzdata-2025b`**. Two
edge cases are handled **explicitly** (never guessed), each recorded and each lowering the
`birth_time` confidence component (§8.5):

**Ambiguous local time (DST fall-back).** When clocks are set back, a local wall time occurs
twice (e.g. 01:30 exists in both the pre-transition and post-transition offset). Python models
this with the `fold` attribute: `fold=0` = first (earlier UTC) occurrence, `fold=1` = second.

- Policy **AMB-1 [Technical + Unverified astrology-domain assumption — requires domain review]:**
  DilChat cannot know which occurrence the certificate meant. It computes **both** candidate UTC
  instants, computes the Moon longitude for each, and:
  - if both candidates fall in the **same** rashi *and* nakshatra *and* pada (the only outputs
    the MVP consumes), it picks `fold=0` as canonical and records `ambiguity_resolved="collapsed"`
    (the ambiguity does not affect any consumed output);
  - if they **differ** in any of rashi/nakshatra/pada, it picks `fold=0` as canonical, records
    `ambiguity_resolved="divergent"` with both candidates in the trace, and applies a confidence
    penalty (§8.5). Whether the earlier or later occurrence is the correct classical convention is
    a domain question flagged for review.

**Nonexistent local time (spring-forward gap).** When clocks jump forward, a local wall time
never occurs (e.g. 02:30 is skipped). `zoneinfo` will still return a value by projecting through
the gap; DilChat detects the gap by testing whether `dt` round-trips (`dt.astimezone(utc)
.astimezone(zone) == dt`).

- Policy **GAP-1 [Technical]:** on a detected gap, the instant is shifted **forward by the gap
  length** (the standard `zoneinfo` gap resolution — the imaginary time maps to the post-jump
  offset), recorded as `gap_adjusted=true`, and a confidence penalty applied (§8.5). The
  adjustment is deterministic and logged in the trace.

Historically, many zones also have pre-standardization **LMT (local mean time)** intervals and
one-off legal offset changes; tzdata encodes these and they are applied automatically because we
localize at the *birth instant* through the historical zone, not at a fixed modern offset.

### 2.3 Stage C — convert to UTC [Technical]

`dt_utc = dt_local_aware.astimezone(timezone.utc)`. Downstream stages consume only `dt_utc`.

### 2.4 Stage D — Julian Day (UT) [Technical — swe call, not fabricated]

```
# swe.julday(year, month, day, decimal_hour, calendar_flag) -> float (Julian Day, UT)
decimal_hour = dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600 + dt_utc.microsecond/3.6e9
jd_ut = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, decimal_hour, swe.GREG_CAL)
```

`swe.GREG_CAL` selects the proleptic Gregorian calendar. For birthdates before the 1582
Gregorian cutover in a given locale, calendar handling is a **[Unverified astrology-domain
assumption — requires domain review]**: the MVP supported birth-year range (baked into the
`.se1` file selection, DEC-007) is expected to be well after the cutover, so `GREG_CAL` is used
uniformly; pre-cutover births are out of MVP scope and rejected at input validation.

`swe.julday` returns a Julian Day in **UT**. Swiss Ephemeris internally applies ΔT
(`swe.deltat`) when `swe.calc_ut` converts UT→TT; DilChat does **not** compute ΔT by hand.

### 2.5 Stage E — sidereal Moon longitude [Technical — swe calls, not fabricated]

```
# One-time per worker process (INV-D3):
swe.set_ephe_path(EPHE_PATH)                 # directory holding semo_*.se1 / sepl_*.se1
swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)      # C name SE_SIDM_LAHIRI; t0=0, ayan_t0=0 (defaults)

# Per calculation:
flags = swe.FLG_SIDEREAL | swe.FLG_SWIEPH | swe.FLG_SPEED
try:
    xx, ret_flag = swe.calc_ut(jd_ut, swe.MOON, flags)     # xx[0] = sidereal ecliptic longitude (deg)
    provider = "swiss"
except swe.Error:                                          # .se1 files absent / unreadable
    flags = swe.FLG_SIDEREAL | swe.FLG_MOSEPH | swe.FLG_SPEED   # Moshier analytical fallback
    xx, ret_flag = swe.calc_ut(jd_ut, swe.MOON, flags)
    provider = "moshier"                                   # stamp + lower confidence (INV-D4)

moon_sid_lon = xx[0] % 360.0     # degrees in [0,360); already sidereal because FLG_SIDEREAL set
moon_speed   = xx[3]             # deg/day, used later for transit root-finding sign checks
```

`swe.calc_ut` returns a 6-tuple `xx = (lon, lat, dist, speed_lon, speed_lat, speed_dist)` plus a
return-flag. With `FLG_SIDEREAL` set (after `set_sid_mode`), `xx[0]` is the **sidereal**
ecliptic longitude — Swiss Ephemeris has already subtracted the Lahiri ayanamsa. DilChat reads
`xx[0]` and `xx[3]`; it never re-derives them.

**Provider cross-check.** The return flag `ret_flag` is inspected: if the caller requested
`FLG_SWIEPH` but Swiss Ephemeris silently fell back to Moshier internally (it sets a bit in the
return flag), DilChat treats the result as `provider="moshier"` (INV-D4). No unlabeled Moshier
result can escape.

---

## 3. Sidereal configuration, ayanamsa & rounding policy

### 3.1 Ayanamsa application [Traditional Vedic rule + Technical]

The zodiac is **sidereal** with **Lahiri** ayanamsa (DEC-008). The conversion tropical→sidereal
is `sidereal_lon = (tropical_lon − ayanamsa(jd)) mod 360`. **DilChat does not perform this
subtraction itself** — it sets `swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)` and requests
`FLG_SIDEREAL`, so `swe.calc_ut` returns the sidereal value directly. For diagnostics/traces
only, the ayanamsa magnitude at the instant may be recorded via:

```
ayan = swe.get_ayanamsa_ut(jd_ut)   # degrees; recorded in trace for auditability, not re-applied
```

### 3.2 Precision & storage policy [Technical]

- All longitudes stored as decimal degrees **rounded half-to-even to 1e-6°** (~0.0036 arcsec —
  far finer than any ephemeris uncertainty; the rounding is for cross-machine determinism, not
  accuracy). Storage type: Postgres `numeric(9,6)` (range 0.000000–359.999999).
- The **round happens once**, immediately after reading `xx[0] % 360`, and the rounded value is
  the sole input to every downstream classification. Downstream code never re-reads the raw float.
- Speeds and ayanamsa magnitudes are trace-only and stored to 1e-6 as well.

### 3.3 Boundary epsilon & tie-breaking [Technical]

Rashi/nakshatra/pada assignment is a `floor` on a segmented circle. A longitude that lands
*exactly* on a segment boundary (e.g. 13.333333° at the Ashwini/Bharani cusp) must resolve
deterministically. Rule:

- Define `EPS = 1e-6` degrees (equal to the storage granularity).
- A value within `EPS` **below** a boundary is snapped **up** to the boundary (assigned to the
  higher segment), because the stored value is already rounded and a sub-EPS deficit is rounding
  noise, not a real position. Concretely: classification operates on
  `lon_adj = lon + EPS` before the `floor`, then indices are clamped to valid ranges. **[Technical
  — determinism device, not an astrological claim.]**
- This snap-up direction is a documented convention, versioned with `engine_calc_version`.
  Whether the classical convention treats an exact cusp as belonging to the lower or higher
  segment is **[Unverified astrology-domain assumption — requires domain review]**; the golden
  boundary tests (§10.4) pin the chosen behavior so any future change is a version bump.

---

## 4. Natal Moon derivation

### 4.1 Segment math [Technical + Traditional Vedic rule for the segmentation]

Constants (exact fractions to avoid float drift; `13°20' = 40/3 = 13.333333…`, `3°20' = 10/3 =
3.333333…`):

```
DEG_PER_RASHI     = 30.0
DEG_PER_NAKSHATRA = 40.0 / 3.0          # 13.3333333333...  (27 nakshatras over 360°)
DEG_PER_PADA      = 10.0 / 3.0          # 3.3333333333...   (4 padas per nakshatra)

lon = round_1e6(moon_sid_lon)           # canonical stored longitude, [0,360)
lon_adj = lon + EPS                      # cusp snap-up (§3.3)

rashi_index     = floor(lon_adj / DEG_PER_RASHI)            # 0..11
nakshatra_index = floor(lon_adj / DEG_PER_NAKSHATRA)        # 0..26
pos_in_nak      = lon_adj - nakshatra_index * DEG_PER_NAKSHATRA   # 0..13.333
pada_index      = floor(pos_in_nak / DEG_PER_PADA)          # 0..3

rashi_index     = clamp(rashi_index, 0, 11)
nakshatra_index = clamp(nakshatra_index, 0, 26)
pada_index      = clamp(pada_index, 0, 3)
```

The segmentation itself (27 × 13°20′, 4 × 3°20′, 12 × 30°) is **[Traditional Vedic rule]**; the
`floor`/`EPS`/`clamp` mechanics are **[Technical]**.

### 4.2 The 27 nakshatras (index → name → sidereal span → rashi span) [Traditional Vedic rule]

Spans are sidereal ecliptic longitude. "Rashi span" shows how a nakshatra can straddle two
rashis (nakshatra and rashi grids are not aligned). Names are the common Sanskrit forms; exact
transliteration is fixed in `nakshatras.json` (§6). **Nakshatra→rashi straddles are
[Unverified astrology-domain assumption — requires domain review] only for spelling, not for
the numeric spans, which follow directly from the 13°20′ segmentation.**

| Idx | Nakshatra | Start° | End° | Rashi(s) spanned |
|----:|-----------|-------:|-----:|------------------|
| 0 | Ashwini | 0.000 | 13.333 | Mesha |
| 1 | Bharani | 13.333 | 26.667 | Mesha |
| 2 | Krittika | 26.667 | 40.000 | Mesha → Vrishabha |
| 3 | Rohini | 40.000 | 53.333 | Vrishabha |
| 4 | Mrigashira | 53.333 | 66.667 | Vrishabha → Mithuna |
| 5 | Ardra | 66.667 | 80.000 | Mithuna |
| 6 | Punarvasu | 80.000 | 93.333 | Mithuna → Karka |
| 7 | Pushya | 93.333 | 106.667 | Karka |
| 8 | Ashlesha | 106.667 | 120.000 | Karka |
| 9 | Magha | 120.000 | 133.333 | Simha |
| 10 | Purva Phalguni | 133.333 | 146.667 | Simha |
| 11 | Uttara Phalguni | 146.667 | 160.000 | Simha → Kanya |
| 12 | Hasta | 160.000 | 173.333 | Kanya |
| 13 | Chitra | 173.333 | 186.667 | Kanya → Tula |
| 14 | Swati | 186.667 | 200.000 | Tula |
| 15 | Vishakha | 200.000 | 213.333 | Tula → Vrishchika |
| 16 | Anuradha | 213.333 | 226.667 | Vrishchika |
| 17 | Jyeshtha | 226.667 | 240.000 | Vrishchika |
| 18 | Mula | 240.000 | 253.333 | Dhanu |
| 19 | Purva Ashadha | 253.333 | 266.667 | Dhanu |
| 20 | Uttara Ashadha | 266.667 | 280.000 | Dhanu → Makara |
| 21 | Shravana | 280.000 | 293.333 | Makara |
| 22 | Dhanishta | 293.333 | 306.667 | Makara → Kumbha |
| 23 | Shatabhisha | 306.667 | 320.000 | Kumbha |
| 24 | Purva Bhadrapada | 320.000 | 333.333 | Kumbha → Meena |
| 25 | Uttara Bhadrapada | 333.333 | 346.667 | Meena |
| 26 | Revati | 346.667 | 360.000 | Meena |

### 4.3 The 12 rashis (index → name → tropical-equivalent → span) [Traditional Vedic rule]

| Idx | Rashi (Sanskrit) | Western equivalent | Span° |
|----:|------------------|--------------------|-------|
| 0 | Mesha | Aries | 0–30 |
| 1 | Vrishabha | Taurus | 30–60 |
| 2 | Mithuna | Gemini | 60–90 |
| 3 | Karka | Cancer | 90–120 |
| 4 | Simha | Leo | 120–150 |
| 5 | Kanya | Virgo | 150–180 |
| 6 | Tula | Libra | 180–210 |
| 7 | Vrishchika | Scorpio | 210–240 |
| 8 | Dhanu | Sagittarius | 240–270 |
| 9 | Makara | Capricorn | 270–300 |
| 10 | Kumbha | Aquarius | 300–330 |
| 11 | Meena | Pisces | 330–360 |

### 4.4 Optional ascendant (MVP-optional per OQ-4) [Technical — swe call]

Ascendant needs birth **latitude/longitude and exact time** (not just UTC instant). It is
captured now, interpreted later (OQ-4). Derivation, when computed:

```
# swe.houses_ex(jd_ut, geolat, geolon, hsys, flags) -> (cusps, ascmc)
cusps, ascmc = swe.houses_ex(jd_ut, geolat, geolon, b'W', swe.FLG_SIDEREAL)
ascendant_sid_lon = ascmc[0] % 360.0    # ascmc[0] = Ascendant; FLG_SIDEREAL => sidereal
asc_rashi = floor((round_1e6(ascendant_sid_lon)+EPS) / 30.0)
```

`hsys=b'W'` (Whole-sign houses) is the **[Unverified astrology-domain assumption — requires
domain review]** default for Vedic whole-sign practice; the house system is a versioned field on
the chart and is not consumed by any MVP scorer. Ascendant confidence collapses to 0 when birth
time is unknown; such charts store `ascendant=null`.

---

## 5. Guna Milan (Ashtakoota) — the 8 scorers

### 5.1 Design invariants [Technical]

- **INV-G1.** Each of the 8 kootas is an **independent, deterministic, pure function** with a
  fixed integer (or half-integer, Vashya only) maximum. Total maximum = **36**.
- **INV-G2.** No koota reads another koota's result. Scorers may be evaluated in any order.
- **INV-G3.** All classical data (varna class per rashi, yoni per nakshatra, the compatibility
  matrices, dosha lists, exception toggles) live in the **versioned rule pack** JSON files, not
  in code. Code contains only the lookup/aggregation logic; changing a table is a rule-pack
  version bump, never a code change.
- **INV-G4 (neutral roles).** Partners are `seeker` and `partner`. The rule pack's
  `manifest.json` declares, per directional koota, which neutral role maps to the classical
  **groom** and which to **bride** (DEC-009a, OQ-2). Symmetric kootas ignore the mapping.
- **INV-G5 (no silent cancellation).** Dosha cancellations (Nadi, Bhakoot) apply **only** when
  `exceptions.json` explicitly enables the specific exception; every applied exception id is
  recorded in the trace (§5.11).

Maxima table (fixed):

| # | Koota | Max | Driven by | Symmetric? |
|--:|-------|----:|-----------|-----------|
| 1 | Varna | 1 | rashi (Moon sign) | Directional |
| 2 | Vashya | 2 | rashi | Directional (matrix) |
| 3 | Tara | 3 | nakshatra | Bidirectional count |
| 4 | Yoni | 4 | nakshatra | Symmetric matrix |
| 5 | Graha Maitri | 5 | rashi lord | Directional (matrix) |
| 6 | Gana | 6 | nakshatra | Directional |
| 7 | Bhakoot | 7 | rashi | Symmetric |
| 8 | Nadi | 8 | nakshatra | Symmetric |
| | **Total** | **36** | | |

All classification logic below is **[Traditional Vedic rule]** in *structure*; the exact cell
values are pinned in the rule pack and remain **[Unverified astrology-domain assumption —
requires domain review]** until a domain expert signs off the cited source (DEC-009, OQ-1).

### 5.2 Koota 1 — Varna (max 1) · directional [Traditional Vedic rule]

- **Inputs:** each partner's rashi index → varna class via `varna.json`. Classical mapping
  (water=Brahmin, fire=Kshatriya, earth=Vaishya, air=Shudra), ranked Brahmin(4) > Kshatriya(3)
  > Vaishya(2) > Shudra(1).
- **Rule:** score 1 if the **groom-role** varna rank ≥ **bride-role** varna rank, else 0.
  Directional (uses INV-G4 mapping).
```
def varna(seeker, partner, pack):
    g, b = role_map(seeker, partner, koota="varna", pack)        # groom, bride per manifest
    rank_g = pack.varna.rank_by_rashi[g.rashi_index]
    rank_b = pack.varna.rank_by_rashi[b.rashi_index]
    return 1 if rank_g >= rank_b else 0
```

### 5.3 Koota 2 — Vashya (max 2) · directional matrix [Traditional Vedic rule]

- **Inputs:** each partner's rashi → vashya group (Chatushpada/quadruped, Manava/human,
  Jalachara/watery, Vanachara/wild, Keeta/insect) via `vashya.json`.
- **Rule:** matrix lookup `vashya_matrix[group(groom)][group(bride)]` yielding {2, 1, 0.5, 0}.
  Vashya is the one koota with a **half-integer** cell (0.5). Directional.
```
def vashya(seeker, partner, pack):
    g, b = role_map(seeker, partner, "vashya", pack)
    gg = pack.vashya.group_by_rashi[g.rashi_index]
    gb = pack.vashya.group_by_rashi[b.rashi_index]
    return pack.vashya.matrix[gg][gb]          # in {2, 1, 0.5, 0}
```

### 5.4 Koota 3 — Tara (max 3) · bidirectional count [Traditional Vedic rule]

- **Inputs:** both nakshatra indices (0..26).
- **Rule:** count forward from bride's nakshatra to groom's (1-based, wrapping) and from groom's
  to bride's; each count mod 9 gives a **tara** (1..9); taras {3,5,7} (Vipat, Pratyari, Vadha)
  are inauspicious. Classical scoring — full credit when both directions are auspicious. The
  exact fractional scheme (e.g. 3 if both good, 1.5 if one) is pinned in `tara.json`.
```
def tara_count(from_nak, to_nak):
    return ((to_nak - from_nak) % 27) + 1        # 1..27, classical 1-based count

def tara(seeker, partner, pack):
    g, b = role_map(seeker, partner, "tara", pack)
    t_bg = ((tara_count(b.nakshatra_index, g.nakshatra_index) - 1) % 9) + 1
    t_gb = ((tara_count(g.nakshatra_index, b.nakshatra_index) - 1) % 9) + 1
    good_bg = t_bg not in pack.tara.inauspicious_taras     # e.g. {3,5,7}
    good_gb = t_gb not in pack.tara.inauspicious_taras
    return pack.tara.score_table[(good_bg, good_gb)]        # e.g. (T,T)->3 (T,F)/(F,T)->1.5 (F,F)->0
```
The remainder-of-9 tara scheme and the {3,5,7} inauspicious set are **[Unverified
astrology-domain assumption — requires domain review]**; some schools use different divisors and
remainder conventions.

### 5.5 Koota 4 — Yoni (max 4) · symmetric matrix [Traditional Vedic rule]

- **Inputs:** each nakshatra → animal yoni (14 animals, e.g. Horse, Elephant, Sheep, Serpent,
  Dog, Cat, Rat, Cow, Buffalo, Tiger, Deer, Monkey, Mongoose, Lion) via `yoni.json`.
- **Rule:** `yoni_matrix[yoni_a][yoni_b]` → {4 (same/friendly), … , 0 (natural enemies)}.
  Symmetric matrix, so role order is irrelevant. Governed by DEC-021: Yoni is presented only as
  romantic-context compatibility, never sexualized outside consensual adult context.
```
def yoni(seeker, partner, pack):
    ya = pack.yoni.yoni_by_nakshatra[seeker.nakshatra_index]
    yb = pack.yoni.yoni_by_nakshatra[partner.nakshatra_index]
    return pack.yoni.matrix[ya][yb]     # symmetric: matrix[ya][yb] == matrix[yb][ya] (validated at load)
```

### 5.6 Koota 5 — Graha Maitri (max 5) · directional matrix [Traditional Vedic rule]

- **Inputs:** each rashi → its lord (planet) via `graha_maitri.json` (Mesha→Mars, Vrishabha→
  Venus, … Meena→Jupiter), then the mutual friendship of the two lords.
- **Rule:** `friendship_matrix[lord(a)][lord(b)]` → {5 friends-both-ways, 4, 3, 1, 0.5, 0} per
  the classical five-fold friendship (friend/neutral/enemy) evaluated both directions. Directional
  in schools that weight groom→bride vs bride→groom differently; role map applied.
```
def graha_maitri(seeker, partner, pack):
    g, b = role_map(seeker, partner, "graha_maitri", pack)
    lg = pack.graha_maitri.lord_by_rashi[g.rashi_index]
    lb = pack.graha_maitri.lord_by_rashi[b.rashi_index]
    return pack.graha_maitri.friendship_score[lg][lb]     # combined bidirectional score in {0,0.5,1,3,4,5}
```
The exact friendship table and how the two one-directional friendships combine into a single
score is **[Unverified astrology-domain assumption — requires domain review]**.

### 5.7 Koota 6 — Gana (max 6) · directional [Traditional Vedic rule]

- **Inputs:** each nakshatra → gana (Deva / Manushya / Rakshasa) via `gana.json`.
- **Rule:** `gana_matrix[gana(groom)][gana(bride)]` → {6, 5, 1, 0}. Classically directional: a
  Rakshasa groom with a Deva bride scores worse than the reverse.
```
def gana(seeker, partner, pack):
    g, b = role_map(seeker, partner, "gana", pack)
    gg = pack.gana.gana_by_nakshatra[g.nakshatra_index]
    gb = pack.gana.gana_by_nakshatra[b.nakshatra_index]
    return pack.gana.matrix[gg][gb]      # directional: matrix need NOT be symmetric
```

### 5.8 Koota 7 — Bhakoot (max 7) · symmetric [Traditional Vedic rule]

- **Inputs:** both rashi indices.
- **Rule:** compute the two-way rashi distance. Certain relative positions — **6/8 (Shadashtaka),
  5/9 (Nabhi/Navam-Pancham), 2/12 (Dwir-Dwadash)** — constitute **Bhakoot dosha** → 0 points;
  otherwise 7. Symmetric.
```
def bhakoot(seeker, partner, pack):
    a, b = seeker.rashi_index, partner.rashi_index
    fwd = ((b - a) % 12) + 1        # 1..12
    rev = ((a - b) % 12) + 1
    pair = frozenset({fwd, rev})
    if pair in pack.bhakoot.dosha_pairs:      # e.g. {6,8},{5,9},{2,12} encoded as sets
        return 0
    return 7
```

### 5.9 Koota 8 — Nadi (max 8) · symmetric [Traditional Vedic rule]

- **Inputs:** both nakshatra indices → nadi (Adi / Madhya / Antya) via `nadi.json`.
- **Rule:** **same nadi ⇒ Nadi dosha ⇒ 0**; different nadi ⇒ 8. Symmetric. Highest-weighted
  koota. Governed by DEC-021: Nadi is **never** rendered in medical/genetic/fertility language —
  only as "traditional constitutional compatibility."
```
def nadi(seeker, partner, pack):
    na = pack.nadi.nadi_by_nakshatra[seeker.nakshatra_index]
    nb = pack.nadi.nadi_by_nakshatra[partner.nakshatra_index]
    return 0 if na == nb else 8
```

### 5.10 Dosha cancellation (Nadi / Bhakoot) — OPTIONAL, explicit-only [Traditional Vedic rule + Technical]

Classical texts list **exceptions** that cancel Nadi or Bhakoot dosha (e.g. same nakshatra but
different pada; same rashi different nakshatra; specific rashi-lord relationships). DilChat treats
every cancellation as **opt-in per rule pack**:

- A cancellation applies **only** if `exceptions.json` contains an enabled rule whose predicate
  matches (`"enabled": true`). There is **no built-in/implicit cancellation** (INV-G5).
- When applied, the affected koota's score is recomputed per the exception's `awarded_points`,
  the exception `id` is appended to `applied_exceptions`, and the trace records the predicate that
  matched and the before/after score.
```
def apply_dosha_exceptions(koota_name, raw_score, seeker, partner, pack, trace):
    if raw_score != 0:                      # exceptions only ever RESTORE a zeroed dosha
        return raw_score
    for ex in pack.exceptions.rules_for(koota_name):
        if ex.enabled and ex.predicate.matches(seeker, partner):
            trace.record_exception(ex.id, koota_name, before=0, after=ex.awarded_points, predicate=ex.predicate.repr)
            return ex.awarded_points        # e.g. restore full 8 (Nadi) or 7 (Bhakoot)
    return 0
```
Which exceptions ship enabled in `..._v1` is **[Unverified astrology-domain assumption —
requires domain review]** and **Requires founder approval** (DEC-009); the MVP default is
**all exceptions `enabled:false`** (conservative — no silent leniency) until domain sign-off.

### 5.11 Guna Milan report structure [Technical]

```
GunaMilanReport = {
  provenance: ProvenanceTuple,                    # §1.3 (rule_pack_id, ephemeris_version, ayanamsa, ...)
  computed_at: <RFC3339 UTC>,
  seeker_ref: <birth_profile_id>, partner_ref: <birth_profile_id>,
  input_confidence: {                             # min of the two natal confidences feeds downstream
     seeker: <0..1>, partner: <0..1>, combined: <0..1>
  },
  components: [                                    # one per koota, order fixed 1..8
    { koota: "varna", max: 1, raw: <n>, awarded: <n>, directional: true,
      inputs: { seeker_rashi:.., partner_rashi:.., groom_role:"partner", varna_g:.., varna_b:.. } },
    ... (vashya, tara, yoni, graha_maitri, gana, bhakoot, nadi) ...
  ],
  total: <0..36>,
  applied_exceptions: [ "nadi_same_nakshatra_diff_pada_v1", ... ],   # empty by default
  trace: CalculationTrace,                         # §5.12 — fully reproducible
  disclaimers: [ "not medical/legal ...", ... ]    # DEC-021
}
```

### 5.12 Calculation trace [Technical]

A `CalculationTrace` is an ordered, JSON-serializable list of steps sufficient to **replay** the
computation offline: the two stored longitudes, derived rashi/nakshatra/pada for each partner,
each koota's inputs → looked-up classifications → matrix cell → raw score, each exception check
(matched or not), and the final sum. Stored in Postgres `jsonb`. A golden test can diff a fresh
trace against a stored one byte-for-byte (INV-D1).

---

## 6. Rule-pack schema (`ashtakoota_lahiri_classical_v1`)

Location: `products/dilchat/rules/ashtakoota_lahiri_classical_v1/`. **The JSON files are authored
separately; this section specifies only their schema.** Files:
`manifest.json`, `varna.json`, `vashya.json`, `tara.json`, `yoni.json`, `graha_maitri.json`,
`gana.json`, `bhakoot.json`, `nadi.json`, `nakshatras.json`, `exceptions.json`, `sources.json`.

### 6.1 `manifest.json` [Technical]

```
{
  "id": "ashtakoota_lahiri_classical_v1",
  "version": "1.0.0",
  "ayanamsa": "lahiri",
  "zodiac": "sidereal",
  "tradition": "north_indian_ashtakoota",          // school label; cited in sources.json
  "draft": true,                                    // DEC-009: cannot be used for user-facing report until false
  "role_mapping": {                                 // INV-G4 / DEC-009a / OQ-2
     "groom": "partner", "bride": "seeker"          // neutral roles -> classical ordering
  },
  "directional_flags": {                            // which kootas consume role_mapping
     "varna": true, "vashya": true, "tara": true, "yoni": false,
     "graha_maitri": true, "gana": true, "bhakoot": false, "nadi": false
  },
  "maxima": { "varna":1,"vashya":2,"tara":3,"yoni":4,"graha_maitri":5,"gana":6,"bhakoot":7,"nadi":8 },
  "total_max": 36,
  "content_hash": "sha256:...",                     // over the canonicalized set of table files
  "created_at": "...", "frozen_at": null            // set when draft flips false (immutability, §6.5)
}
```

### 6.2 Table files — shapes [Technical]

- **`nakshatras.json`** — canonical `index → {name, start_deg, end_deg}` (the §4.2 table).
- **`varna.json`** — `{ "rank_by_rashi": [int × 12] }` (4=Brahmin … 1=Shudra).
- **`vashya.json`** — `{ "group_by_rashi": [str × 12], "matrix": { group: { group: number } } }`
  with cells in {2,1,0.5,0}.
- **`tara.json`** — `{ "inauspicious_taras": [int], "score_table": { "TT":3,"TF":1.5,"FF":0 } }`.
- **`yoni.json`** — `{ "yoni_by_nakshatra": [str × 27], "matrix": { yoni: { yoni: 0..4 } } }`;
  loader asserts symmetry.
- **`graha_maitri.json`** — `{ "lord_by_rashi": [str × 12], "friendship_score": { planet: { planet: number } } }`.
- **`gana.json`** — `{ "gana_by_nakshatra": [str × 27], "matrix": { gana: { gana: 0..6 } } }`
  (need not be symmetric).
- **`bhakoot.json`** — `{ "dosha_pairs": [[6,8],[5,9],[2,12]] }` (unordered pairs of counts).
- **`nadi.json`** — `{ "nadi_by_nakshatra": [str × 27] }` (values Adi/Madhya/Antya).

### 6.3 `exceptions.json` [Technical]

```
{
  "rules": [
    { "id": "nadi_same_nakshatra_diff_pada_v1", "koota": "nadi", "enabled": false,
      "predicate": { "type": "same_nakshatra_diff_pada" },
      "awarded_points": 8,
      "citation_ref": "src_raman_muhurta_p123" }        // -> sources.json
  ]
}
```
Predicate `type`s are a closed, code-recognized vocabulary (e.g. `same_nakshatra_diff_pada`,
`same_rashi_diff_nakshatra`, `rashi_lords_are_friends`, `same_rashi_lord`). An unknown predicate
type fails rule-pack load (fail-closed, INV-G5). Default: all `enabled:false` (§5.10).

### 6.4 `sources.json` (citations) [Technical + Requires domain review]

```
{
  "citations": [
    { "id": "src_raman_muhurta_p123", "author": "B. V. Raman", "work": "Muhurta",
      "edition": "...", "pages": "...", "applies_to": ["nadi","exceptions"] }
  ],
  "reviewed_by": null,          // domain expert name/date — must be set before draft:false (DEC-009/OQ-1)
  "review_notes": ""
}
```

### 6.5 Versioning & immutability [Technical]

- A rule pack is identified by its **id** (`..._v1`). Any change to a table cell, an enabled
  exception, or the role mapping requires a **new id** (`..._v2`) — packs are **append-only**;
  `..._v1` is never edited after `frozen_at` is set (INV-D5, DEC-019).
- `content_hash` in the manifest is computed over the canonicalized union of table files at load
  and verified at runtime; a mismatch fails startup (tamper/version-skew detection).
- `draft:true` packs are usable only in tests, never in a user-facing report (DEC-009). The
  transition to `draft:false` requires `sources.json.reviewed_by` set and founder approval.

---

## 7. Moon transit engine (`moon_transits`, `transit_model_version=dilchat_transit_v1`)

Two layers: (7.1–7.4) a **global** daily transit computation (same for everyone, cacheable in
Redis per DEC-005), and (7.5–7.7) **per-user** derivations relative to a natal Moon.

### 7.1 Global daily transit position [Technical — swe call]

For the day's reference instant `jd_ut` (§7.8), compute the **transit** sidereal Moon exactly as
in §2.5 (`swe.calc_ut(jd_ut, swe.MOON, FLG_SIDEREAL|…)`), then derive transit rashi / nakshatra /
pada via §4.1. The Sun's sidereal longitude is computed the same way (`swe.SUN`) for tithi (§7.7).

### 7.2 Next rashi & next nakshatra transition times [Technical — root-finding, not fabricated math]

We need the next UTC instant at which the transit Moon **crosses** the next rashi boundary
(multiple of 30°) and the next nakshatra boundary (multiple of 13°20′). The Moon moves ~12–15°/day
and is monotonic in longitude over the short horizon, so:

- **Approach = sample + bisection on a Swiss-Ephemeris-evaluated function.** DilChat does **not**
  model lunar motion analytically; it evaluates `swe.calc_ut` at sample instants and brackets the
  crossing, then bisects. Longitude wrap at 360°→0° is handled by unwrapping relative to the
  target boundary.
```
def next_boundary_crossing(jd_start, boundary_deg, horizon_days=2.0, step_hours=1.0):
    # f(t) = signed angular distance from Moon longitude to the target boundary, in (-180,180]
    def f(jd):
        lon = swe.calc_ut(jd, swe.MOON, SID_FLAGS)[0][0] % 360.0
        d = (boundary_deg - lon + 540.0) % 360.0 - 180.0     # wrap into (-180,180]
        return d
    # scan forward for a sign change of f as the Moon approaches the boundary from below
    t0 = jd_start; f0 = f(t0); step = step_hours/24.0
    t = t0 + step
    while t <= jd_start + horizon_days:
        f1 = f(t)
        if crosses_boundary(f0, f1):          # f goes from small-positive toward 0 / sign flip
            return bisect(f, t - step, t, tol_days = 1.0/86400)   # ~1-second tolerance
        t0, f0 = t, f1; t += step
    return None                                # no crossing within horizon (should not happen for Moon)
```
`crosses_boundary` accounts for the fact that as the Moon approaches a boundary from below, `f`
decreases toward 0 then flips sign; `bisect` is standard bisection (deterministic given the same
`swe` evaluations). Tolerance ~1 s. The **next rashi** boundary is
`(floor(lon/30)+1)*30 mod 360`; the **next nakshatra** boundary is
`(floor(lon/(40/3))+1)*(40/3) mod 360`. Retrograde Moon does not occur (the Moon is never
retrograde in longitude), so monotonicity holds; the sign-check still guards against sampling
artifacts.

### 7.3 House of transit Moon **from natal Moon** (1..12) [Traditional Vedic rule]

```
def house_from_natal(natal_rashi_index, transit_rashi_index):
    return ((transit_rashi_index - natal_rashi_index) % 12) + 1     # 1 = same sign as natal Moon
```
Whole-sign counting from the natal Moon's rashi. Optionally the same count **from ascendant**
(OQ-4) is computed when ascendant is present; MVP consumes the from-Moon value.

### 7.4 Tara Bala (9-fold) [Traditional Vedic rule]

Counting from the **natal** nakshatra to the **transit** nakshatra, 1-based and wrapping, mod 9
gives one of nine taras, each with a fixed favorable/unfavorable classification:

| Tara # | Name | Classical class |
|-------:|------|-----------------|
| 1 | Janma | mixed/neutral |
| 2 | Sampat | favorable |
| 3 | Vipat | unfavorable |
| 4 | Kshema | favorable |
| 5 | Pratyari | unfavorable |
| 6 | Sadhaka | favorable |
| 7 | Vadha (Naidhana) | unfavorable |
| 8 | Mitra | favorable |
| 9 | Ati-Mitra (Parama Mitra) | favorable |

```
def tara_bala(natal_nak, transit_nak, pack_or_table):
    count = ((transit_nak - natal_nak) % 27) + 1     # 1..27
    tara  = ((count - 1) % 9) + 1                     # 1..9
    return { "tara_number": tara,
             "tara_name":  TARA_NAMES[tara],
             "favorable":  tara in FAVORABLE_TARAS }  # e.g. {2,4,6,8,9}; {3,5,7} unfavorable, 1 neutral
```
The favorable/unfavorable partition {2,4,6,8,9 favorable; 3,5,7 unfavorable; 1 neutral} is the
common scheme but **[Unverified astrology-domain assumption — requires domain review]** as to
Janma's treatment; it is stored in the interpretation pack (`dilchat_interp_v1`), not hard-coded.

### 7.5 Chandra Bala [Traditional Vedic rule]

Chandra Bala evaluates the transit Moon's **house from the natal Moon** (§7.3). Favorable houses
are classically **1, 3, 6, 7, 10, 11** and unfavorable **4, 8, 12** (with 2, 5, 9 mixed). The
exact favorable set is stored in `dilchat_interp_v1` and is **[Unverified astrology-domain
assumption — requires domain review]**.
```
def chandra_bala(house_from_natal, interp):
    return { "house": house_from_natal,
             "favorable": house_from_natal in interp.chandra_favorable_houses }
```

### 7.6 Tithi & lunar phase (compute now, score post-MVP per OQ-5) [Traditional Vedic rule]

```
def tithi_and_phase(sun_sid_lon, moon_sid_lon):
    elong = (moon_sid_lon - sun_sid_lon) % 360.0       # Moon minus Sun elongation
    tithi_index = floor(elong / 12.0)                  # 0..29 (30 tithis of 12deg each)
    paksha = "shukla" if tithi_index < 15 else "krishna"   # waxing / waning
    phase_fraction = (1 - cos(radians(elong))) / 2     # 0=new,1=full illumination proxy [DilChat display only]
    return { "tithi_index": tithi_index, "paksha": paksha,
             "elongation_deg": elong, "phase_fraction": phase_fraction }
```
The 30-tithi/12° segmentation and shukla/krishna split are **[Traditional Vedic rule]**;
`phase_fraction` is a **[DilChat proprietary interpretation]** display convenience (not a
classical quantity) and is not used in any classical score. Sidereal vs tropical longitudes give
the **same** elongation (ayanamsa cancels in the difference), so the Lahiri choice is immaterial
to tithi. Per OQ-5, tithi/phase are **computed and stored now** but **not scored** in the MVP.

### 7.7 Global daily transit record [Technical]

```
DailyGlobalTransit = {
  provenance: ProvenanceTuple, date: <YYYY-MM-DD>, ref_instant_utc: <RFC3339>,
  moon: { sid_lon, rashi_index, nakshatra_index, pada_index, speed_deg_per_day },
  sun:  { sid_lon },
  next_rashi_transition_utc: <RFC3339|null>,
  next_nakshatra_transition_utc: <RFC3339|null>,
  tithi: { tithi_index, paksha, elongation_deg, phase_fraction },
  trace: CalculationTrace
}
```
Cached in Redis keyed by `(date, provenance-relevant versions)`; source of truth persisted in
Postgres. Per-user derivations (§7.3–7.5) are computed on top and are cheap (pure integer math).

### 7.8 Refresh boundary (OQ-7) [Product + Technical]

The user-facing daily profile refreshes at the user's **local midnight** (primary boundary,
OQ-7). The reference instant for the global transit computation is a fixed convention
(recommendation: local midnight of the user's coarse current zone, or a fixed UTC anchor for the
global record) — the exact anchor is versioned with `dilchat_transit_v1`. Within-day rashi/
nakshatra transition times (§7.2) are surfaced so the user sees upcoming shifts before the next
midnight refresh.

---

## 8. Interest-theme & daily-climate derivation [DilChat proprietary interpretation]

> **Everything in §8 is a DilChat product model, NOT a classical formula (DEC-019).** These
> equations map already-computed transit features onto DilChat's 12-interest ontology and 8 daily
> dimensions. They are versioned as `dilchat_interest_v1` / `dilchat_interp_v1`. Behavioral
> calibration may nudge **presentation** within clamped bounds but never rewrites classical
> results (DEC-019).

### 8.1 Input feature vector [DilChat proprietary interpretation]

From §7, per user per day:

```
features = {
  house_from_moon:  1..12,          # §7.3
  transit_nakshatra: 0..26,         # §7.1
  transit_rashi:     0..11,
  tara_favorable:    {-1,0,+1},     # unfavorable / neutral / favorable  (§7.4)
  chandra_favorable: {0,1},         # §7.5
  paksha_sign:       {-1 (krishna) ... +1 (shukla)},   # waxing bias (§7.6)
  phase_fraction:    0..1
}
```

### 8.2 The 12 interests (canonical ontology) [DilChat proprietary interpretation]

`RELATIONSHIP_AFFECTION, HOME_FAMILY, CAREER_ACHIEVEMENT, MONEY_SECURITY, HEALTH_ROUTINE,
FRIENDS_COMMUNITY, LEARNING_COMMUNICATION, TRAVEL_EXPLORATION, CREATIVITY_ENTERTAINMENT,
INTIMACY_TRUST, SPIRITUALITY_REFLECTION, REST_SOLITUDE`.

### 8.3 Interest scoring equation [DilChat proprietary interpretation]

Each interest `k` gets a raw score from a **linear combination of feature contributions**, then a
squashing to [0,100]. All weights live in a **config table** (versioned, not hard-coded):

```
raw_k = base_k
      + W_house[k][house_from_moon]        # house affinity table (12 interests x 12 houses)
      + W_nak[k][transit_nakshatra]        # nakshatra affinity (12 x 27), small nudges
      + w_tara[k]    * tara_favorable      # +/- tilt from Tara Bala
      + w_chandra[k] * chandra_favorable
      + w_paksha[k]  * paksha_sign
score_k = clamp01( sigmoid( (raw_k - mu_k) / s_k ) ) * 100    # sigmoid keeps it smooth & bounded
```

`W_house`, `W_nak`, `w_*`, `base_k`, `mu_k`, `s_k` are all entries of the interest-model config
(`dilchat_interest_v1`). Illustrative **initial weights** (product-tunable, not classical):

| Interest | strongest positive house(s) | tara wt | chandra wt | paksha wt |
|----------|------------------------------|:------:|:----------:|:---------:|
| RELATIONSHIP_AFFECTION | 7, 11 | +0.6 | +0.5 | +0.3 |
| HOME_FAMILY | 4, 2 | +0.3 | +0.6 | +0.1 |
| CAREER_ACHIEVEMENT | 10, 6 | +0.5 | +0.4 | +0.3 |
| MONEY_SECURITY | 2, 11 | +0.4 | +0.4 | +0.2 |
| HEALTH_ROUTINE | 6, 1 | +0.5 | +0.5 | 0.0 |
| FRIENDS_COMMUNITY | 11, 3 | +0.4 | +0.3 | +0.3 |
| LEARNING_COMMUNICATION | 3, 5 | +0.4 | +0.3 | +0.2 |
| TRAVEL_EXPLORATION | 9, 3, 12 | +0.4 | +0.2 | +0.2 |
| CREATIVITY_ENTERTAINMENT | 5, 3 | +0.4 | +0.3 | +0.4 |
| INTIMACY_TRUST | 8, 7 | +0.5 | +0.5 | +0.2 |
| SPIRITUALITY_REFLECTION | 12, 9 | +0.3 | +0.2 | −0.2 |
| REST_SOLITUDE | 12, 4 | −0.2 | +0.3 | −0.3 |

House numbers reference §7.3 whole-sign houses from the natal Moon. These starting values are a
DilChat product hypothesis to be tuned against feedback (`feedback` module), never a classical
claim.

### 8.4 The 8 daily-climate dimensions [DilChat proprietary interpretation]

Dimensions: **emotional comfort, sensitivity, expression tendency, conversation receptivity, need
for space, decision steadiness, couple tension risk, couple synchronization.** Each is scored to
[0,1] by an analogous linear-then-clamp equation over the same features (plus, for the two
*couple* dimensions, both partners' features):

```
emotional_comfort   = clamp01( a0 + a_chandra*chandra_favorable + a_tara*tara_favorable + a_phase*phase_fraction )
sensitivity         = clamp01( b0 + b_paksha*(-paksha_sign) + b_nak*nak_sensitivity[transit_nakshatra] )
expression_tendency = clamp01( c0 + c_paksha*paksha_sign + c_house*house_expressive[house_from_moon] )
conversation_receptivity = clamp01( d0 + d_house*house_social[house_from_moon] + d_tara*tara_favorable )
need_for_space      = clamp01( e0 + e_house*house_withdrawn[house_from_moon] + e_paksha*(-paksha_sign) )
decision_steadiness = clamp01( f0 + f_chandra*chandra_favorable + f_house*house_stable[house_from_moon] )

# couple dimensions take BOTH partners' features (subscripts A,B):
couple_tension_risk       = clamp01( g0 + g_bhakoot*bhakoot_flag_AB + g_gap*|comfort_A - comfort_B|
                                     + g_house*house_friction(house_A, house_B) )
couple_synchronization    = clamp01( h0 + h_sync*(1 - |comfort_A - comfort_B|)
                                     + h_house*house_harmony(house_A, house_B) )
```

`bhakoot_flag_AB` reuses the **classical** Bhakoot dosha result (§5.8) as a *feature* — the
classical score is read, never modified (DEC-019). All `a*/b*/…/h*` coefficients live in
`dilchat_interp_v1` config.

### 8.5 Confidence [Technical + DilChat proprietary interpretation]

```
confidence = birth_time_confidence * data_completeness
```
- **`birth_time_confidence`** starts at 1.0 and is multiplied by penalties:
  - unknown/estimated birth clock time → e.g. ×0.5 (chart still usable for rashi if the Moon
    doesn't change sign that day, else lower);
  - DST fall-back ambiguity with divergent candidates (§2.2 AMB-1) → ×0.85;
  - spring-forward gap adjustment (§2.2 GAP-1) → ×0.9;
  - `ephemeris_provider="moshier"` fallback (INV-D4) → ×0.97 (Moshier is arcminute-accurate,
    ample for boundaries, so the penalty is small but non-zero and **explicit**).
- **`data_completeness`** = fraction of required inputs present (place resolved to real
  coordinates, time present, both partners for couple scores, etc.).

Exact penalty multipliers are config in `dilchat_interp_v1` and are **product** values, not
classical. Confidence is surfaced with every score and never silently hidden.

### 8.6 Explanation traces [DilChat proprietary interpretation]

Each score carries an ordered list of its top feature contributions (feature name, its value, its
weight, its signed contribution to `raw`), so the UI/AI can say *"receptivity is high today mainly
because the Moon transits your 3rd house-from-Moon (+0.4) and Tara Bala is favorable (+0.3)."* The
LLM only renders this pre-computed trace; it does not compute the score (INV-D2, DEC-014).

### 8.7 Consented behavioral calibration [DilChat proprietary interpretation]

If the user has consented, a **presentation-layer** calibration may re-rank or re-emphasize which
themes are surfaced first, within clamped bounds, based on behavioral signal (`dilchat_living_v1`).
It **cannot** alter any classical Guna Milan value, any stored transit feature, or the raw
score equations — only the ordering/emphasis of what is shown (DEC-019). The applied calibration
version is recorded so a presentation can be reproduced.

---

## 9. Versioning & reproducibility

### 9.1 Pinned version surface [Technical]

The determinism contract (INV-D1) holds only against a **frozen version surface**: the entire
provenance tuple (§1.3). Any change to `ephemeris_version`, `ayanamsa`, `rule_pack_id`,
`transit_model_version`, `interpretation_pack_version`, `interest_model_version`, or
`engine_calc_version` is a new version surface producing **new rows**, never an in-place edit
(INV-D5, DEC-019).

### 9.2 Golden-vector storage [Technical]

A `golden_vectors` store holds `(input_tuple, version_surface) → expected_output + expected_trace`
for a curated set of reference charts (§10). CI recomputes and asserts byte-equality. Golden
vectors are the executable form of the determinism invariant.

### 9.3 Recalculation strategy on version change [Technical]

When a new ephemeris/rule/model version ships:
- **Old rows stay immutable.** A new computation row is appended under the new version surface,
  time-ordered. Users see the latest by default; history is queryable/auditable (DEC-019, `audit`).
- Recalculation is a **versioned sweep** (arq job, DEC-006): iterate affected natal charts /
  couples, compute under the new surface, insert new rows. Idempotent (re-running the sweep
  produces identical new rows and no duplicates, keyed by `(subject, version_surface)`).
- A rule-pack change (`..._v1`→`..._v2`) never mutates a report computed under `..._v1`; both
  coexist, each self-describing via its provenance tuple.

---

## 10. Golden-test methodology (per DEC-020)

### 10.1 Reference charts [Technical]

A fixed set of birth events spanning: modern and historical dates; multiple IANA zones incl.
zones with historical LMT and one-off legal offset changes; DST fall-back ambiguity cases;
spring-forward gap cases; both hemispheres; and Moon positions deliberately placed near rashi,
nakshatra, and pada boundaries.

### 10.2 Cross-validation oracle (tests only) [Technical — DEC-020]

Per DEC-020, an external astrology API / panchang / Swiss Ephemeris published test vectors are
used **only in the test suite** as an independent oracle for the reference charts' Moon longitude,
nakshatra, and pada. Oracles are **never** called from production code paths.

### 10.3 Tolerance thresholds [Technical]

- **Moon sidereal longitude:** DilChat's value must agree with the oracle within a defined
  tolerance — recommendation **≤ 30 arcsec** for Swiss-provider charts, relaxed to **≤ 2 arcmin**
  for Moshier-provider comparisons (Moshier is analytically approximate). Exact thresholds are
  test config.
- **Classification (rashi/nakshatra/pada):** must match the oracle **exactly** except within a
  guarded band of ±(tolerance) around a boundary, where the boundary tests (§10.4) govern.
- **Tithi index:** exact match to oracle.

### 10.4 Boundary tests [Technical]

For each rashi boundary (multiples of 30°), nakshatra boundary (multiples of 13°20′), and pada
boundary (multiples of 3°20′), craft inputs whose Moon longitude lands at `boundary − 2·EPS`,
`boundary`, and `boundary + 2·EPS`, and assert the §3.3 snap-up convention deterministically. Any
future change to the epsilon/snap direction must break these tests (forcing a version bump).

### 10.5 Historical-timezone tests [Technical]

Assert that a birth in, e.g., a zone with a historical half-hour offset, or during a
one-time DST anomaly, localizes correctly under `tzdata-2025b` and that ambiguous/gap cases apply
the AMB-1/GAP-1 policies (§2.2) with the expected confidence penalties (§8.5).

### 10.6 Guna Milan golden reports [Technical]

Curated couples with hand-verified koota-by-koota expected values (against the cited rule-pack
source, DEC-009) — including at least one Nadi-dosha pair, one Bhakoot-dosha pair, and one pair
that would be cancelled **only** if an exception is enabled (to prove no silent cancellation,
INV-G5).

---

## 11. Full calculation pseudocode

> All `swe.*` calls are cited by name; no ephemeris internals are fabricated (non-fabrication
> rule). Integer/segment/scoring logic is fully specified.

### 11.1 Natal derivation

```
def derive_natal_moon(birth_local_naive, iana_zone, geolat, geolon, birth_time_known):
    # --- Stage B: localize with historical tz rules (tzdata-2025b) ---
    zone = ZoneInfo(iana_zone)
    dt0  = birth_local_naive.replace(tzinfo=zone, fold=0)
    dt1  = birth_local_naive.replace(tzinfo=zone, fold=1)
    gap  = not round_trips(birth_local_naive, zone)          # spring-forward detection
    amb  = (dt0.utcoffset() != dt1.utcoffset()) and not gap  # fall-back ambiguity

    conf = 1.0
    if gap:
        dt0 = shift_forward_by_gap(birth_local_naive, zone)  # GAP-1
        conf *= PENALTY_GAP
    canonical = dt0                                          # fold=0 canonical (AMB-1)
    if not birth_time_known: conf *= PENALTY_TIME_UNKNOWN

    # --- Stage C/D: UTC -> Julian Day (UT) ---
    dt_utc = canonical.astimezone(timezone.utc)
    hour   = dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600 + dt_utc.microsecond/3.6e9
    jd_ut  = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, hour, swe.GREG_CAL)

    # --- Stage E: sidereal Moon longitude (worker already did set_sid_mode(SIDM_LAHIRI)) ---
    flags = swe.FLG_SIDEREAL | swe.FLG_SWIEPH | swe.FLG_SPEED
    try:
        xx, ret = swe.calc_ut(jd_ut, swe.MOON, flags); provider = "swiss"
    except swe.Error:
        xx, ret = swe.calc_ut(jd_ut, swe.MOON, swe.FLG_SIDEREAL|swe.FLG_MOSEPH|swe.FLG_SPEED)
        provider = "moshier"
    if moshier_bit_set(ret): provider = "moshier"
    if provider == "moshier": conf *= PENALTY_MOSHIER

    lon = round_1e6(xx[0] % 360.0)

    # --- classification (Traditional segmentation; Technical mechanics) ---
    a = lon + EPS
    rashi = clamp(floor(a / 30.0), 0, 11)
    nak   = clamp(floor(a / (40.0/3.0)), 0, 26)
    pin   = a - nak * (40.0/3.0)
    pada  = clamp(floor(pin / (10.0/3.0)), 0, 3)

    if amb:                                    # check divergence of the two DST candidates
        alt = classify(round_1e6(dt1.astimezone(utc) -> moon lon))
        if alt != (rashi,nak,pada): conf *= PENALTY_AMBIGUOUS

    return NatalMoon(sid_lon=lon, rashi=rashi, nakshatra=nak, pada=pada,
                     provider=provider, confidence=conf, trace=...)
```

### 11.2 The 8 Guna scorers (aggregator)

```
def guna_milan(seeker, partner, pack):
    trace = CalculationTrace()
    comp = {}
    comp["varna"]        = varna(seeker, partner, pack)                       # §5.2
    comp["vashya"]       = vashya(seeker, partner, pack)                      # §5.3
    comp["tara"]         = tara(seeker, partner, pack)                        # §5.4
    comp["yoni"]         = yoni(seeker, partner, pack)                        # §5.5
    comp["graha_maitri"] = graha_maitri(seeker, partner, pack)               # §5.6
    comp["gana"]         = gana(seeker, partner, pack)                        # §5.7
    bhak = bhakoot(seeker, partner, pack)                                     # §5.8
    comp["bhakoot"]      = apply_dosha_exceptions("bhakoot", bhak, seeker, partner, pack, trace)  # §5.10
    nad  = nadi(seeker, partner, pack)                                        # §5.9
    comp["nadi"]         = apply_dosha_exceptions("nadi", nad, seeker, partner, pack, trace)      # §5.10
    total = sum(comp.values())            # max 36
    assert 0 <= total <= 36
    return GunaMilanReport(components=comp, total=total,
                           applied_exceptions=trace.exception_ids,
                           input_confidence=combine(seeker.confidence, partner.confidence),
                           trace=trace, provenance=PROVENANCE)
```
(Individual scorer bodies `varna`…`nadi` are given verbatim in §5.2–5.9.)

### 11.3 Transit house / Tara Bala / Chandra Bala

```
def user_daily_transit(natal, global_transit, interp):
    house = ((global_transit.moon.rashi_index - natal.rashi) % 12) + 1        # §7.3

    count = ((global_transit.moon.nakshatra_index - natal.nakshatra) % 27) + 1
    tara_no = ((count - 1) % 9) + 1                                           # §7.4
    tara = { "number": tara_no, "name": TARA_NAMES[tara_no],
             "favorable": tara_no in interp.favorable_taras }

    chandra = { "house": house, "favorable": house in interp.chandra_favorable_houses }   # §7.5

    tara_feat    = +1 if tara["favorable"] else (-1 if tara_no in interp.unfavorable_taras else 0)
    chandra_feat = 1 if chandra["favorable"] else 0

    return UserDailyTransit(house_from_moon=house, tara=tara, chandra=chandra,
                            tara_feature=tara_feat, chandra_feature=chandra_feat,
                            transit_nakshatra=global_transit.moon.nakshatra_index,
                            paksha_sign=(+1 if global_transit.tithi.paksha=="shukla" else -1),
                            phase_fraction=global_transit.tithi.phase_fraction)
```

### 11.4 Interest-score equation [DilChat proprietary interpretation]

```
def interest_scores(feat, model):        # model = dilchat_interest_v1 config
    out = {}
    for k in INTERESTS_12:
        raw = ( model.base[k]
              + model.W_house[k][feat.house_from_moon]
              + model.W_nak[k][feat.transit_nakshatra]
              + model.w_tara[k]    * feat.tara_feature
              + model.w_chandra[k] * feat.chandra_feature
              + model.w_paksha[k]  * feat.paksha_sign )
        score = clamp01( sigmoid((raw - model.mu[k]) / model.s[k]) ) * 100
        out[k] = { "score": score,
                   "explanation": top_contributions(k, feat, model) }   # §8.6
    return out
```

### 11.5 Daily-climate equation (single + couple) [DilChat proprietary interpretation]

```
def daily_climate(featA, featB_or_none, interp):    # interp = dilchat_interp_v1 config
    A = per_person_climate(featA, interp)            # 6 single-person dims via §8.4 linear-clamp forms
    if featB_or_none is None:
        return { **A }                               # single-user preview (OQ-3), no couple dims
    B = per_person_climate(featB_or_none, interp)
    couple = {
      "tension_risk": clamp01( interp.g0
                     + interp.g_bhakoot * bhakoot_flag(featA, featB_or_none)   # reads CLASSICAL result, unmodified
                     + interp.g_gap     * abs(A.emotional_comfort - B.emotional_comfort)
                     + interp.g_house   * house_friction(featA.house_from_moon, featB_or_none.house_from_moon) ),
      "synchronization": clamp01( interp.h0
                     + interp.h_sync  * (1 - abs(A.emotional_comfort - B.emotional_comfort))
                     + interp.h_house * house_harmony(featA.house_from_moon, featB_or_none.house_from_moon) )
    }
    return { "seeker": A, "partner": B, "couple": couple }
```

---

## Appendix A — Open-question & decision cross-reference

| This spec | Depends on | Note |
|-----------|-----------|------|
| §2.1 geo/tz | DEC-017, `geonames-2025-Q3`, `tzdata-2025b` | offline datasets |
| §2.2 AMB-1/GAP-1 | DEC-017 | explicit ambiguity/gap handling, confidence penalties |
| §2.5 provider | DEC-007, INV-D4 | Moshier fallback labeled, never silent |
| §3.1 ayanamsa | DEC-008 | Lahiri, applied by swe, not by DilChat |
| §4.4 ascendant | OQ-4 | MVP-optional, captured now |
| §5 role mapping | DEC-009a, OQ-2 | neutral seeker/partner → classical groom/bride |
| §5.10 exceptions | DEC-009, INV-G5 | opt-in only, all disabled by default |
| §6 rule pack draft | DEC-009, OQ-1 | `draft:true` until domain sign-off |
| §7.6 tithi | OQ-5 | compute now, score post-MVP |
| §7.8 refresh | OQ-7 | local-midnight primary boundary |
| §8 interest/climate | DEC-019 | proprietary, never merged with classical |
| §8.7 calibration | DEC-019, OQ-9 | presentation-only, clamped |
| §5.5/5.9 Yoni/Nadi | DEC-021 | safety constraints on interpretation |
| §10.2 oracle | DEC-020 | tests only |

## Appendix B — Items flagged for domain review (consolidated)

The following carry **[Unverified astrology-domain assumption — requires domain review]** and
**must** be confirmed before `manifest.json.draft` flips to `false` (DEC-009 / OQ-1):

1. DST fall-back convention: earlier vs later occurrence as canonical (§2.2 AMB-1).
2. Exact-cusp membership direction (lower vs higher segment) (§3.3).
3. Nakshatra name transliterations (§4.2) — numeric spans are certain.
4. House system for ascendant (Whole-sign assumed) (§4.4).
5. All rule-pack cell values: varna ranks, vashya matrix, tara scheme & inauspicious set, yoni
   matrix, graha-maitri friendship combination, gana matrix, bhakoot dosha pairs, nadi mapping
   (§5.2–5.9).
6. Which dosha-cancellation exceptions ship enabled (default: none) (§5.10).
7. Tara Bala Janma treatment and the favorable partition (§7.4).
8. Chandra Bala favorable-house set (§7.5).

*End of DILCHAT_ASTROLOGY_ENGINE_SPEC.md*
