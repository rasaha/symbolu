import React, { useMemo, useState } from "react";
import { useRouter } from "expo-router";

import { userMessageFor } from "@/api/errors";
import type { BirthProfileResponse, BirthTimePrecision } from "@/api/types";
import { useBirthProfile, useSaveBirthProfile } from "@/query/hooks";
import {
  type DraftBirthProfile,
  type FieldErrors,
  hasErrors,
  toRequest,
  validateDraft,
} from "@/validation/birthProfile";
import { Body, Button, ErrorText, Heading, Loading, Screen, TextField } from "@/ui/components";

const PRECISIONS: BirthTimePrecision[] = ["EXACT", "APPROXIMATE", "UNKNOWN"];

const EMPTY_DRAFT: DraftBirthProfile = {
  preferred_name: "",
  birth_date: "",
  birth_time_precision: "EXACT",
  birth_time_local: "",
  uncertainty_minutes: "",
  birthplace_label: "",
  iana_timezone: "",
  latitude: "",
  longitude: "",
};

function seedFrom(p: BirthProfileResponse | null | undefined): DraftBirthProfile {
  if (!p) return EMPTY_DRAFT;
  // The response intentionally omits raw local time / lat / lon (privacy-minimal);
  // those are re-entered on edit. Seed only the returned fields.
  return {
    ...EMPTY_DRAFT,
    preferred_name: p.preferred_name,
    birth_date: p.birth_date,
    birth_time_precision: p.birth_time_precision,
    uncertainty_minutes: p.uncertainty_minutes != null ? String(p.uncertainty_minutes) : "",
    birthplace_label: p.birthplace_label,
    iana_timezone: p.iana_timezone,
  };
}

/**
 * Birth-profile create/edit form. Validates with the shared validator only —
 * it never computes a Nakshatra, natal Moon, or any interpretation value.
 */
export default function Profile(): React.ReactElement {
  const router = useRouter();
  const query = useBirthProfile();
  const save = useSaveBirthProfile();

  const exists = !!query.data;
  const seeded = useMemo(() => seedFrom(query.data), [query.data]);
  const [draft, setDraft] = useState<DraftBirthProfile | null>(null);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [serverError, setServerError] = useState<string | null>(null);

  // Initialize the editable draft once the query settles.
  const current: DraftBirthProfile = draft ?? seeded;

  if (query.isLoading) {
    return (
      <Screen scroll={false}>
        <Loading label="Loading your birth profile…" />
      </Screen>
    );
  }

  const set = (patch: Partial<DraftBirthProfile>): void => {
    setDraft({ ...current, ...patch });
  };

  const onSave = async (): Promise<void> => {
    setServerError(null);
    const next = validateDraft(current);
    setErrors(next);
    if (hasErrors(next)) return;
    try {
      await save.mutateAsync({ body: toRequest(current), exists });
      router.back();
    } catch (e) {
      setServerError(userMessageFor(e));
    }
  };

  const precision = current.birth_time_precision;

  return (
    <Screen>
      <Heading>{exists ? "Edit birth profile" : "Create birth profile"}</Heading>
      <Body muted>
        This information stays in your own private account. It is not shared with a partner unless you explicitly
        authorize sharing later.
      </Body>

      <TextField
        label="Preferred name"
        testID="preferred_name"
        value={current.preferred_name}
        onChangeText={(v) => set({ preferred_name: v })}
        error={errors.preferred_name}
        autoCapitalize="words"
      />

      <TextField
        label="Birth date (YYYY-MM-DD)"
        testID="birth_date"
        value={current.birth_date}
        onChangeText={(v) => set({ birth_date: v })}
        error={errors.birth_date}
        autoCapitalize="none"
        keyboardType="numbers-and-punctuation"
      />

      <Body>Time-of-birth precision</Body>
      <Body muted>How precisely do you know the clock time of birth?</Body>
      {PRECISIONS.map((p) => (
        <Button
          key={p}
          title={p === current.birth_time_precision ? `● ${p}` : p}
          testID={`precision-${p}`}
          variant={p === current.birth_time_precision ? "primary" : "secondary"}
          onPress={() => set({ birth_time_precision: p })}
        />
      ))}

      {precision !== "UNKNOWN" ? (
        <TextField
          label="Time of birth (HH:MM, 24-hour, local clock time at the birthplace)"
          testID="birth_time_local"
          value={current.birth_time_local}
          onChangeText={(v) => set({ birth_time_local: v })}
          error={errors.birth_time_local}
          autoCapitalize="none"
          keyboardType="numbers-and-punctuation"
        />
      ) : (
        <Body muted>Time of birth is not used when precision is UNKNOWN.</Body>
      )}

      {precision === "APPROXIMATE" ? (
        <TextField
          label="Uncertainty (minutes, 1–720)"
          testID="uncertainty_minutes"
          value={current.uncertainty_minutes}
          onChangeText={(v) => set({ uncertainty_minutes: v })}
          error={errors.uncertainty_minutes}
          keyboardType="number-pad"
        />
      ) : null}

      <TextField
        label="Birthplace"
        testID="birthplace_label"
        value={current.birthplace_label}
        onChangeText={(v) => set({ birthplace_label: v })}
        error={errors.birthplace_label}
      />

      <TextField
        label="Birthplace time zone (IANA, e.g. Asia/Kolkata — NOT your device's time zone)"
        testID="iana_timezone"
        value={current.iana_timezone}
        onChangeText={(v) => set({ iana_timezone: v })}
        error={errors.iana_timezone}
        autoCapitalize="none"
      />
      <Body muted>
        Use the time zone of the birthplace, not the zone your phone is currently set to. This must be an IANA zone
        such as Asia/Kolkata.
      </Body>

      <TextField
        label="Latitude (-90 to 90)"
        testID="latitude"
        value={current.latitude}
        onChangeText={(v) => set({ latitude: v })}
        error={errors.latitude}
        keyboardType="numbers-and-punctuation"
      />

      <TextField
        label="Longitude (-180 to 180)"
        testID="longitude"
        value={current.longitude}
        onChangeText={(v) => set({ longitude: v })}
        error={errors.longitude}
        keyboardType="numbers-and-punctuation"
      />

      {serverError ? <ErrorText>{serverError}</ErrorText> : null}

      <Button title="Save" testID="save" onPress={onSave} loading={save.isPending} />
      <Button title="Cancel" variant="secondary" testID="cancel" onPress={() => router.back()} />
    </Screen>
  );
}
