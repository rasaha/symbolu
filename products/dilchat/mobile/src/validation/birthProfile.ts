/**
 * Client-side birth-profile validation. This is a UX convenience only — the
 * backend remains the authoritative validator. Deliberately does NOT compute any
 * natal Moon, Nakshatra, or Guna value; it only checks shape/range before submit.
 */
import type { BirthProfileCreateRequest, BirthTimePrecision } from "@/api/types";

export interface DraftBirthProfile {
  preferred_name: string;
  birth_date: string; // YYYY-MM-DD
  birth_time_precision: BirthTimePrecision;
  birth_time_local: string; // HH:MM (may be empty when UNKNOWN)
  uncertainty_minutes: string; // string from a text field
  birthplace_label: string;
  iana_timezone: string;
  latitude: string;
  longitude: string;
}

export type FieldErrors = Partial<Record<keyof DraftBirthProfile, string>>;

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;

export function validateDraft(d: DraftBirthProfile): FieldErrors {
  const e: FieldErrors = {};
  if (!d.preferred_name.trim()) e.preferred_name = "Enter a name to display.";

  if (!DATE_RE.test(d.birth_date)) {
    e.birth_date = "Use the format YYYY-MM-DD.";
  } else {
    const dt = new Date(`${d.birth_date}T00:00:00Z`);
    if (Number.isNaN(dt.getTime())) e.birth_date = "That date is not valid.";
  }

  if (d.birth_time_precision !== "UNKNOWN") {
    if (!TIME_RE.test(d.birth_time_local)) {
      e.birth_time_local = "Enter the time as HH:MM (24-hour).";
    }
  }
  if (d.birth_time_precision === "APPROXIMATE") {
    const n = Number(d.uncertainty_minutes);
    if (!Number.isInteger(n) || n < 1 || n > 720) {
      e.uncertainty_minutes = "Enter an uncertainty of 1–720 minutes.";
    }
  }

  if (!d.birthplace_label.trim()) e.birthplace_label = "Enter the birthplace.";
  if (!d.iana_timezone.trim()) {
    e.iana_timezone = "Enter the birthplace time zone (e.g. Asia/Kolkata).";
  } else if (!d.iana_timezone.includes("/")) {
    e.iana_timezone = "Use an IANA zone like Asia/Kolkata — not the device zone.";
  }

  const lat = Number(d.latitude);
  if (!Number.isFinite(lat) || lat < -90 || lat > 90) e.latitude = "Latitude must be between -90 and 90.";
  const lon = Number(d.longitude);
  if (!Number.isFinite(lon) || lon < -180 || lon > 180) e.longitude = "Longitude must be between -180 and 180.";

  return e;
}

export function hasErrors(e: FieldErrors): boolean {
  return Object.keys(e).length > 0;
}

/** Convert a validated draft into the backend request body. */
export function toRequest(d: DraftBirthProfile): BirthProfileCreateRequest {
  const precision = d.birth_time_precision;
  return {
    preferred_name: d.preferred_name.trim(),
    birth_date: d.birth_date,
    birth_time_precision: precision,
    birth_time_local: precision === "UNKNOWN" ? null : d.birth_time_local,
    uncertainty_minutes: precision === "APPROXIMATE" ? Number(d.uncertainty_minutes) : null,
    birthplace_label: d.birthplace_label.trim(),
    iana_timezone: d.iana_timezone.trim(),
    latitude: Number(d.latitude),
    longitude: Number(d.longitude),
  };
}
