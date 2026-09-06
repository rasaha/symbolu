// Screen 1 — Registration (front-door seam 5, FD-9). Typed intake over ai-system-registry.
//
// The form sends typed fields and nothing else: no tenant (the deployment's), no
// registration id (derived by the package), no registered_by (the deployment's name and
// version). The owner reference is an opaque handle the backend records as presented
// and unproven, and the screen says so. Register is the only write; a registration
// records what an administrator asserted and confers nothing. There is no admit,
// approve, gate, revoke, edit or delete control, because no such route exists.
import { useState } from "react";

import { GapNotice, RegistryKindNotice } from "./GapNotice";
import { ActionButton, Json, Panel, ScreenFrame } from "./ScreenFrame";
import { useRegisterSystem, useRegistrations } from "./hooks";
import { LoadingState, QueryError } from "@/design-system/states";
import { isUnavailable } from "@/api/types-v2";
import type { RegistryRegisterBody } from "@/api/types-v2";

type BindingKey = keyof RegistryRegisterBody["binding"];

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
  canonical_subject_context_ref: "",
  system_manifest_ref: "",
  system_manifest_digest: "",
  deployment_environment_ref: "",
};

const input =
  "w-full rounded border border-surface-border bg-surface-0 px-2 py-1 font-mono text-[11px] text-ink-0";

function Field({
  id,
  label,
  value,
  onChange,
  required,
}: {
  id: string;
  label: string;
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
      <input id={id} value={value} onChange={(e) => onChange(e.target.value)} className={input} spellCheck={false} />
    </div>
  );
}

function RefusalNotice({ code, reason }: { code: string; reason: string }) {
  return (
    <p role="alert" className="rounded border border-rose-300 bg-rose-50 px-3 py-2 text-[12px] text-rose-800">
      Refused (<span className="font-mono">{code}</span>): {reason}
    </p>
  );
}

export function RegistrationScreen() {
  const [binding, setBinding] = useState<Record<BindingKey, string>>(EMPTY_BINDING);
  const [ownerRef, setOwnerRef] = useState("");
  const [label, setLabel] = useState("");
  const [issuedAt, setIssuedAt] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [supersedes, setSupersedes] = useState("");
  const [notes, setNotes] = useState("");

  const register = useRegisterSystem();
  const registrations = useRegistrations();

  const submit = () => {
    const body: RegistryRegisterBody = {
      binding: {
        binding_id: binding.binding_id,
        subject_id: binding.subject_id,
        context_id: binding.context_id,
        context_digest: binding.context_digest,
        system_id: binding.system_id,
        system_version: binding.system_version,
        configuration_id: binding.configuration_id,
        configuration_digest: binding.configuration_digest,
        // The generated contract types the optional refs as strings; empty text is
        // "not supplied" to the registry, exactly as the package reads it.
        canonical_subject_context_ref: binding.canonical_subject_context_ref,
        system_manifest_ref: binding.system_manifest_ref,
        system_manifest_digest: binding.system_manifest_digest,
        deployment_environment_ref: binding.deployment_environment_ref,
      },
      owner_ref: ownerRef,
      classification_label: label,
      validity: { issued_at: issuedAt, expires_at: expiresAt || null },
      supersedes,
      notes,
    };
    register.mutate(body, { onSuccess: () => registrations.refetch() });
  };

  const registered = register.data;

  return (
    <ScreenFrame
      title="Registration"
      subtitle="Record what an administrator asserts about one AI system: its exact binding, an owner reference, a classification label and a validity window."
      neverDoes="Registering confers nothing. This screen never admits, approves, gates, promotes, attests, edits, revokes or deletes; a changed system is a new registration that supersedes the old."
    >
      <Panel title="Register a system">
        <p className="mb-2 text-[11px] text-ink-3">
          Typed fields only. The tenant is this deployment&rsquo;s, the registration id is
          derived by the registry, and the owner reference is recorded as{" "}
          <span className="font-mono">PRESENTED_UNPROVEN</span>: an opaque handle, not an
          authenticated identity. The classification label is recorded uninterpreted.
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
          <Field id="owner-ref" label="Owner reference" required value={ownerRef} onChange={setOwnerRef} />
          <Field id="classification-label" label="Classification label" required value={label} onChange={setLabel} />
          <Field id="issued-at" label="Issued at (ISO-8601, with timezone)" required value={issuedAt} onChange={setIssuedAt} />
          <Field id="expires-at" label="Expires at (ISO-8601, with timezone)" value={expiresAt} onChange={setExpiresAt} />
          <Field id="supersedes" label="Supersedes (registration id)" value={supersedes} onChange={setSupersedes} />
          <Field id="notes" label="Notes" value={notes} onChange={setNotes} />
        </div>
        <div className="mt-2">
          <ActionButton onClick={submit} disabled={register.isPending}>
            Register
          </ActionButton>
        </div>
        {register.error ? <QueryError error={register.error} /> : null}
        {registered ? (
          <div className="mt-2 space-y-2">
            {isUnavailable(registered) ? (
              <GapNotice gap={registered} />
            ) : (registered as { refused?: boolean }).refused ? (
              <RefusalNotice
                code={String((registered as { code?: string }).code ?? "refused")}
                reason={String((registered as { reason?: string }).reason ?? "")}
              />
            ) : (
              <>
                <p className="text-[12px] text-ink-1" data-testid="registered-notice">
                  Registered{" "}
                  <span className="font-mono">{String((registered as { registration_id?: string }).registration_id ?? "")}</span>
                  {" · "}owner reference {String((registered as { owner_ref_status?: string }).owner_ref_status ?? "")}
                  {" · "}confers {String((registered as { confers?: string }).confers ?? "")}
                </p>
                <Json value={(registered as { record?: unknown }).record} label="Registration record" />
              </>
            )}
          </div>
        ) : null}
      </Panel>

      <Panel title="Registrations in force">
        {registrations.isLoading ? <LoadingState label="Reading the registry…" /> : null}
        {registrations.error ? <QueryError error={registrations.error} /> : null}
        {registrations.data ? (
          isUnavailable(registrations.data) ? (
            <GapNotice gap={registrations.data} />
          ) : (
            <div className="space-y-2">
              <RegistryKindNotice
                kind={String((registrations.data as { registry_kind?: string }).registry_kind ?? "unknown")}
              />
              <p className="text-[11px] text-ink-3">
                Tenant <span className="font-mono">{String((registrations.data as { tenant_id?: string }).tenant_id ?? "")}</span>
                {" · "}as of{" "}
                <span className="font-mono">{String((registrations.data as { as_of?: string }).as_of ?? "")}</span>
                {" · "}owner references are {String((registrations.data as { owner_ref_status?: string }).owner_ref_status ?? "")}
                {" · "}a registration confers {String((registrations.data as { confers?: string }).confers ?? "")}
              </p>
              {(() => {
                const records = ((registrations.data as { result?: unknown[] }).result ?? []) as unknown[];
                if (records.length === 0) {
                  return <p className="text-[12px] text-ink-2">No registration is in force for this tenant at that instant.</p>;
                }
                return <Json value={records} label={`${records.length} registration(s)`} />;
              })()}
            </div>
          )
        ) : null}
      </Panel>
    </ScreenFrame>
  );
}
