// Screen 1 — Constitution.
//
// Validates a constitution document, and PREFLIGHTS issuance. It never issues and
// never activates: those are authority acts, permanently outside the studio's
// allowlist (SD-2). The preflight button is present and works — it reports that no
// trust root is configured, which is the honest answer and the one an operator needs.
import { useState } from "react";

import { GapNotice } from "./GapNotice";
import { ActionButton, Json, Panel, ScreenFrame } from "./ScreenFrame";
import { usePreflightConstitution, useValidateConstitution } from "./hooks";
import { isUnavailable, type GapAware } from "@/api/types-v2";

const SAMPLE = JSON.stringify(
  { constitution_id: "con_demo", clauses: [], version: "1" },
  null,
  2,
);

function ValidationResult({ gap }: { gap: GapAware }) {
  if (isUnavailable(gap)) return <GapNotice gap={gap} />;
  const state = String((gap as { validation_state?: string }).validation_state ?? "");
  const diagnostics = ((gap as { diagnostics?: unknown[] }).diagnostics ?? []) as {
    code: string;
    message: string;
  }[];
  return (
    <div className="space-y-2">
      <div
        className={
          state === "VALID"
            ? "rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-[12px] text-emerald-950"
            : "rounded border border-rose-300 bg-rose-50 px-3 py-2 text-[12px] text-rose-950"
        }
        role="status"
      >
        <span className="font-semibold">{state || "UNKNOWN"}</span>
        {diagnostics.length > 0 ? (
          <ul className="mt-1 list-disc pl-4">
            {diagnostics.map((d, i) => (
              <li key={i}>
                <span className="font-mono text-[11px]">{d.code}</span> — {d.message}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
      <Json value={gap} label="Full result" />
    </div>
  );
}

export function ConstitutionScreen() {
  const [text, setText] = useState(SAMPLE);
  const [parseError, setParseError] = useState<string | null>(null);
  const validate = useValidateConstitution();
  const preflight = usePreflightConstitution();

  const parsed = (): Record<string, unknown> | null => {
    try {
      const value = JSON.parse(text) as Record<string, unknown>;
      setParseError(null);
      return value;
    } catch (err) {
      setParseError(String((err as Error).message));
      return null;
    }
  };

  return (
    <ScreenFrame
      title="Constitution"
      subtitle="Author a constitution, check its structure, and dry-run every pre-signing check."
      neverDoes="This screen never issues and never activates a constitution — those are authority acts."
    >
      <Panel title="Constitution document">
        <label htmlFor="constitution-json" className="mb-1 block text-[11px] text-ink-2">
          JSON document
        </label>
        <textarea
          id="constitution-json"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={10}
          spellCheck={false}
          className="w-full rounded border border-surface-border bg-surface-0 p-2 font-mono text-[11px] text-ink-0"
        />
        {parseError ? (
          <p role="alert" className="mt-1 text-[11px] text-rose-700">
            Not valid JSON: {parseError}
          </p>
        ) : null}
        <div className="mt-2 flex gap-2">
          <ActionButton
            onClick={() => {
              const value = parsed();
              if (value) validate.mutate({ constitution: value });
            }}
            disabled={validate.isPending}
          >
            Validate
          </ActionButton>
          <ActionButton
            onClick={() => {
              const value = parsed();
              if (value) preflight.mutate({ constitution: value, record_id: "studio-preflight" });
            }}
            disabled={preflight.isPending}
          >
            Preflight issuance
          </ActionButton>
        </div>
      </Panel>

      {validate.data ? (
        <Panel title="Validation">
          <ValidationResult gap={validate.data} />
        </Panel>
      ) : null}

      {preflight.data ? (
        <Panel title="Preflight">
          {isUnavailable(preflight.data) ? (
            <GapNotice gap={preflight.data} />
          ) : (
            <Json value={preflight.data} label="Preflight report" />
          )}
        </Panel>
      ) : null}
    </ScreenFrame>
  );
}
