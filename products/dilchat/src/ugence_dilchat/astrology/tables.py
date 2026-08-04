"""Rashi and nakshatra name tables (indices match the rule-pack manifest).

These are neutral astronomical labels (sign/lunar-mansion names), not Guna Milan
rules. Indices align with
``rules/ashtakoota_lahiri_classical_v1/manifest.json`` (rashi 0..11 = Aries..Pisces,
nakshatra 0..26 = Ashwini..Revati).
"""

from __future__ import annotations

RASHI_NAMES: tuple[str, ...] = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)

NAKSHATRA_NAMES: tuple[str, ...] = (
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta",
    "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
)

assert len(RASHI_NAMES) == 12
assert len(NAKSHATRA_NAMES) == 27

DEGREES_PER_RASHI = 30.0
DEGREES_PER_NAKSHATRA = 360.0 / 27.0  # 13.333... == 13°20'
DEGREES_PER_PADA = 360.0 / 108.0      # 3.333...  == 3°20'
