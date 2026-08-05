import { type DraftBirthProfile, hasErrors, toRequest, validateDraft } from "@/validation/birthProfile";

function baseDraft(overrides: Partial<DraftBirthProfile> = {}): DraftBirthProfile {
  return {
    preferred_name: "Asha",
    birth_date: "1990-05-14",
    birth_time_precision: "EXACT",
    birth_time_local: "08:30",
    uncertainty_minutes: "",
    birthplace_label: "Pune, India",
    iana_timezone: "Asia/Kolkata",
    latitude: "18.52",
    longitude: "73.85",
    ...overrides,
  };
}

describe("validateDraft", () => {
  it("returns no errors for a valid EXACT draft", () => {
    const e = validateDraft(baseDraft());
    expect(hasErrors(e)).toBe(false);
    expect(e).toEqual({});
  });

  it("flags a missing preferred name", () => {
    const e = validateDraft(baseDraft({ preferred_name: "   " }));
    expect(e.preferred_name).toBeTruthy();
  });

  it("flags a badly formatted birth date", () => {
    const e = validateDraft(baseDraft({ birth_date: "14/05/1990" }));
    expect(e.birth_date).toBeTruthy();
  });

  it("flags a calendar-invalid date that matches the format", () => {
    const e = validateDraft(baseDraft({ birth_date: "1990-13-40" }));
    expect(e.birth_date).toBeTruthy();
  });

  it("flags a bad time when precision is not UNKNOWN", () => {
    const e = validateDraft(baseDraft({ birth_time_local: "25:99" }));
    expect(e.birth_time_local).toBeTruthy();
  });

  it("flags out-of-range latitude and longitude", () => {
    const e = validateDraft(baseDraft({ latitude: "-91", longitude: "181" }));
    expect(e.latitude).toBeTruthy();
    expect(e.longitude).toBeTruthy();
  });

  it("requires uncertainty 1..720 when APPROXIMATE", () => {
    expect(validateDraft(baseDraft({ birth_time_precision: "APPROXIMATE", uncertainty_minutes: "0" })).uncertainty_minutes).toBeTruthy();
    expect(validateDraft(baseDraft({ birth_time_precision: "APPROXIMATE", uncertainty_minutes: "721" })).uncertainty_minutes).toBeTruthy();
    expect(validateDraft(baseDraft({ birth_time_precision: "APPROXIMATE", uncertainty_minutes: "abc" })).uncertainty_minutes).toBeTruthy();
    const ok = validateDraft(baseDraft({ birth_time_precision: "APPROXIMATE", uncertainty_minutes: "30" }));
    expect(ok.uncertainty_minutes).toBeUndefined();
  });

  it("does not require a time when precision is UNKNOWN", () => {
    const e = validateDraft(baseDraft({ birth_time_precision: "UNKNOWN", birth_time_local: "" }));
    expect(e.birth_time_local).toBeUndefined();
    expect(hasErrors(e)).toBe(false);
  });

  it("flags a device-style timezone without a region slash", () => {
    const e = validateDraft(baseDraft({ iana_timezone: "IST" }));
    expect(e.iana_timezone).toBeTruthy();
  });
});

describe("toRequest", () => {
  it("maps an EXACT draft with numeric coercion", () => {
    const req = toRequest(baseDraft());
    expect(req).toMatchObject({
      preferred_name: "Asha",
      birth_date: "1990-05-14",
      birth_time_precision: "EXACT",
      birth_time_local: "08:30",
      uncertainty_minutes: null,
      birthplace_label: "Pune, India",
      iana_timezone: "Asia/Kolkata",
      latitude: 18.52,
      longitude: 73.85,
    });
    expect(typeof req.latitude).toBe("number");
    expect(typeof req.longitude).toBe("number");
  });

  it("clears the time and keeps uncertainty null when UNKNOWN", () => {
    const req = toRequest(baseDraft({ birth_time_precision: "UNKNOWN", birth_time_local: "08:30" }));
    expect(req.birth_time_local).toBeNull();
    expect(req.uncertainty_minutes).toBeNull();
  });

  it("passes uncertainty as a number when APPROXIMATE", () => {
    const req = toRequest(baseDraft({ birth_time_precision: "APPROXIMATE", uncertainty_minutes: "45" }));
    expect(req.uncertainty_minutes).toBe(45);
    expect(req.birth_time_local).toBe("08:30");
  });

  it("trims whitespace on text fields", () => {
    const req = toRequest(baseDraft({ preferred_name: "  Asha  ", birthplace_label: "  Pune  ", iana_timezone: "  Asia/Kolkata  " }));
    expect(req.preferred_name).toBe("Asha");
    expect(req.birthplace_label).toBe("Pune");
    expect(req.iana_timezone).toBe("Asia/Kolkata");
  });

  it("preserves midnight local time verbatim (no off-by-a-day tz shift)", () => {
    const e = validateDraft(baseDraft({ birth_time_local: "00:00" }));
    expect(e.birth_time_local).toBeUndefined();
    const req = toRequest(baseDraft({ birth_time_local: "00:00" }));
    expect(req.birth_time_local).toBe("00:00");
    expect(req.birth_date).toBe("1990-05-14");
  });

  it("passes a DST-transition local date/time through unchanged (client never resolves it)", () => {
    // 02:30 on a US spring-forward night is a non-existent local instant. The
    // client must NOT try to resolve or shift it — it forwards the literal
    // strings + IANA zone and lets the backend be authoritative.
    const draft = baseDraft({
      birth_date: "2021-03-14",
      birth_time_local: "02:30",
      iana_timezone: "America/New_York",
    });
    const req = toRequest(draft);
    expect(req.birth_date).toBe("2021-03-14");
    expect(req.birth_time_local).toBe("02:30");
    expect(req.iana_timezone).toBe("America/New_York");
  });

  it("uses the entered birth zone, never the device zone", () => {
    // Regardless of where the device is, the birthplace zone is what gets sent.
    const req = toRequest(baseDraft({ iana_timezone: "Pacific/Auckland" }));
    expect(req.iana_timezone).toBe("Pacific/Auckland");
  });
});
