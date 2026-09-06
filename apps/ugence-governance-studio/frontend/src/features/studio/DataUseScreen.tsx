// Screen 5 — Data-use declarations (front-door seam 8, FD-12). Typed intake over
// data-use-admission.
//
// The form sends typed fields and nothing else: no tenant (the deployment's), no
// declaration id (derived by the package), no recording composition (the deployment's
// name and version). The data reference is an opaque handle — there is no field on this
// screen, or in the contract behind it, that could carry the data itself. The
// classification, purpose and residency labels are recorded exactly as typed and
// interpreted nowhere. Declare is the only write: there is no admit, authorize, verify,
// score, enforce, edit, revoke or delete control, because no such route exists. No
// egress restriction is expressible here, and the screen says so rather than offering a
// control that would not restrict anything.
import { useState } from "react";

import { GapNotice } from "./GapNotice";
import { ActionButton, Json, Panel, ScreenFrame } from "./ScreenFrame";
import { useDataUseDeclarations, useDeclareDataUse } from "./hooks";
import { LoadingState, QueryError } from "@/design-system/states";
import { isUnavailable } from "@/api/types-v2";
import type { DataUseDeclareBody } from "@/api/types-v2";

type BindingKey = keyof DataUseDeclareBody["binding"];

const BINDING_FIELDS: { key: BindingKey; label: string; required: boolean }[] = [
  { key: "binding_id", label: "Binding id", required: true },
  { key: "subject_id", label: "Subject id", required: true },
  { key: "context_id", label: "Context id", required: true },
  { key: "context_digest", label: "Context digest (sha-256 hex)", required: true },
  { key: "system_id", label: "System id", required: true },
  { key: "system_version", label: "System version", required: true },
  { key: "configuration_id", label: "Configuration id", required: true },
  { key: "configuration_digest", label: "Configuration digest (sha-256 hex)", required: true },
  { key: "deployment_environment_ref", label: "Deployment environment ref", required: false },
];

const EMPTY_BINDING: Record<BindingKey, string> = {
  binding_id: "",
  subject_id: "",
  context_id: "",
  context_digest: "",
  system_id: "",
  system_version: "",
  configuration_id: "",
  configuration_digest: "",
  deployment_environment_ref: "",
};

const input =
  "w-full rounded border border-surface-border bg-surface-0 px-2 py-1 font-mono text-[11px] text-ink-0";

function Field({
  id,
  label,
  hint,
  value,
  onChange,
  required,
}: {
  id: string;
  label: string;
  hint?: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-[11px] text-ink-2">
        {label}
        {required ? " *" : ""}
      </label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={input}
        spellCheck={false}
      />
      {hint ? <p className="mt-1 text-[10px] text-ink-3">{hint}</p> : null}
    </div>
  );
}

function RefusalNotice({ code, reason }: { code: string; reason: string }) {
  return (
    <p
      role="alert"
      className="rounded border border-rose-300 bg-rose-50 px-3 py-2 text-[12px] text-rose-800"
    >
      Refused (<span className="font-mono">{code}</span>): {reason}
    </p>
  );
}

/** FD-12.5: the egress package does not exist, so this screen invents no restriction. */
function EgressNotice({ note }: { note: string }) {
  return (
    <div
      role="note"
      aria-label="egress restrictions"
      className="rounded border border-surface-border bg-surface-2 px-3 py-2 text-[12px] text-ink-1"
    >
      <span className="font-semibold">Egress restrictions:</span> {note}
    </div>
  );
}

export function DataUseScreen() {
  const [binding, setBinding] = useState<Record<BindingKey, string>>(EMPTY_BINDING);
  const [dataRef, setDataRef] = useState("");
  const [classification, setClassification] = useState("");
  const [purpose, setPurpose] = useState("");
  const [residency, setResidency] = useState("");
  const [issuedAt, setIssuedAt] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [supersedes, setSupersedes] = useState("");
  const [declaredBy, setDeclaredBy] = useState("");
  const [notes, setNotes] = useState("");

  const declare = useDeclareDataUse();
  const declarations = useDataUseDeclarations();

  const submit = () => {
    const body: DataUseDeclareBody = {
      binding: {
        binding_id: binding.binding_id,
        subject_id: binding.subject_id,
        context_id: binding.context_id,
        context_digest: binding.context_digest,
        system_id: binding.system_id,
        system_version: binding.system_version,
        configuration_id: binding.configuration_id,
        configuration_digest: binding.configuration_digest,
        deployment_environment_ref: binding.deployment_environment_ref,
      },
      data_ref: dataRef,
      classification_label: classification,
      purpose_label: purpose,
      validity: { issued_at: issuedAt, expires_at: expiresAt || null },
      residency_label: residency,
      supersedes,
      declared_by: declaredBy,
      // No control offers one: a correlation id would tie this record to a run, and
      // this screen declares data use, it does not start or observe anything.
      correlation_id: "",
      notes,
    };
    declare.mutate(body, { onSuccess: () => declarations.refetch() });
  };

  const declared = declare.data;

  return (
    <ScreenFrame
      title="Data use"
      subtitle="Record what a declarer asserts about the data one AI system uses: an opaque reference to it, what they called it, what they said it is for, and for how long."
      neverDoes="A declaration confers nothing. This screen never inspects, classifies, redacts, minimizes, admits, authorizes, verifies, scores or enforces; it restricts no egress, and a changed declaration is a new one that supersedes the old."
    >
      <Panel title="Declare a data use">
        <p className="mb-2 text-[11px] text-ink-3">
          Typed fields only. The tenant is this deployment&rsquo;s, the declaration id is
          derived by the package, and the declarer is recorded as{" "}
          <span className="font-mono">PRESENTED_UNPROVEN</span>: an opaque handle, not an
          authenticated identity. The data reference is a locator and never the data. The
          classification, purpose and residency labels are recorded exactly as typed and
          interpreted nowhere.
        </p>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          {BINDING_FIELDS.map((f) => (
            <Field
              key={f.key}
              id={`binding-${f.key}`}
              label={f.label}
              required={f.required}
              value={binding[f.key]}
              onChange={(v) => setBinding((b) => ({ ...b, [f.key]: v }))}
            />
          ))}
          <Field
            id="data-ref"
            label="Data reference"
            hint="An opaque locator — a dataset id, a record handle. Never the data itself."
            required
            value={dataRef}
            onChange={setDataRef}
          />
          <Field
            id="classification-label"
            label="Classification label"
            hint="Recorded uninterpreted: what the declarer called it, never what that means."
            required
            value={classification}
            onChange={setClassification}
          />
          <Field
            id="purpose-label"
            label="Purpose label"
            hint="Recorded uninterpreted."
            required
            value={purpose}
            onChange={setPurpose}
          />
          <Field
            id="residency-label"
            label="Residency label"
            hint="Recorded as metadata and evaluated nowhere in this deployment."
            value={residency}
            onChange={setResidency}
          />
          <Field
            id="issued-at"
            label="Issued at (ISO-8601, with timezone)"
            required
            value={issuedAt}
            onChange={setIssuedAt}
          />
          <Field
            id="expires-at"
            label="Expires at (ISO-8601, with timezone)"
            value={expiresAt}
            onChange={setExpiresAt}
          />
          <Field
            id="declared-by"
            label="Declared by"
            hint="An opaque handle, recorded as presented and unproven."
            value={declaredBy}
            onChange={setDeclaredBy}
          />
          <Field
            id="supersedes"
            label="Supersedes (declaration id)"
            value={supersedes}
            onChange={setSupersedes}
          />
          <Field id="notes" label="Notes" value={notes} onChange={setNotes} />
        </div>
        <div className="mt-2">
          <ActionButton onClick={submit} disabled={declare.isPending}>
            Declare
          </ActionButton>
        </div>
        {declare.error ? <QueryError error={declare.error} /> : null}
        {declared ? (
          <div className="mt-2 space-y-2">
            {isUnavailable(declared) ? (
              <GapNotice gap={declared} />
            ) : (declared as { refused?: boolean }).refused ? (
              <RefusalNotice
                code={String((declared as { code?: string }).code ?? "refused")}
                reason={String((declared as { reason?: string }).reason ?? "")}
              />
            ) : (
              <>
                <p className="text-[12px] text-ink-1" data-testid="declared-notice">
                  Declared{" "}
                  <span className="font-mono">
                    {String((declared as { declaration_id?: string }).declaration_id ?? "")}
                  </span>
                  {" · "}declarer{" "}
                  {String((declared as { declared_by_status?: string }).declared_by_status ?? "")}
                  {" · "}confers {String((declared as { confers?: string }).confers ?? "")}
                </p>
                <EgressNotice
                  note={String(
                    (declared as { egress_restrictions?: string }).egress_restrictions ?? "",
                  )}
                />
                <Json value={(declared as { record?: unknown }).record} label="Declaration record" />
              </>
            )}
          </div>
        ) : null}
      </Panel>

      <Panel title="Declarations in force">
        {declarations.isLoading ? <LoadingState label="Reading the declarations…" /> : null}
        {declarations.error ? <QueryError error={declarations.error} /> : null}
        {declarations.data ? (
          isUnavailable(declarations.data) ? (
            <GapNotice gap={declarations.data} />
          ) : (
            <div className="space-y-2">
              <p className="text-[11px] text-ink-3">
                Tenant{" "}
                <span className="font-mono">
                  {String((declarations.data as { tenant_id?: string }).tenant_id ?? "")}
                </span>
                {" · "}store{" "}
                <span className="font-mono">
                  {String((declarations.data as { store_kind?: string }).store_kind ?? "unknown")}
                </span>
                {" · "}as of{" "}
                <span className="font-mono">
                  {String((declarations.data as { as_of?: string }).as_of ?? "")}
                </span>
                {" · "}declarers are{" "}
                {String(
                  (declarations.data as { declared_by_status?: string }).declared_by_status ?? "",
                )}
                {" · "}a declaration confers{" "}
                {String((declarations.data as { confers?: string }).confers ?? "")}
              </p>
              <EgressNotice
                note={String(
                  (declarations.data as { egress_restrictions?: string }).egress_restrictions ?? "",
                )}
              />
              {(() => {
                const records = ((declarations.data as { result?: unknown[] }).result ??
                  []) as unknown[];
                if (records.length === 0) {
                  return (
                    <p className="text-[12px] text-ink-2">
                      No declaration is in force for this tenant at that instant.
                    </p>
                  );
                }
                return <Json value={records} label={`${records.length} declaration(s)`} />;
              })()}
            </div>
          )
        ) : null}
      </Panel>
    </ScreenFrame>
  );
}
