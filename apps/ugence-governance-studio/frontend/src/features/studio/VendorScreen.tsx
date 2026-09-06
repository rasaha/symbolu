// Screen 5b — Vendor dependencies (front-door seam 9, FD-13). Typed intake over
// vendor-dependency.
//
// The form sends typed fields and nothing else: no tenant (the deployment's), no
// declaration id (derived by the package), no recording composition. The vendor
// reference is an opaque locator — there is no field on this screen, or in the
// contract behind it, that could carry an address, endpoint or credential.
//
// FD-13.4 is the line this screen exists to hold visibly. "Risk posture" is exactly
// the kind of label a reader assumes somebody assessed. Nobody did: it is recorded as
// typed, ordered and ranked nowhere, and there is no approval, onboarding, tier,
// certification, score, verify or enforce control anywhere — because no route and no
// package computes any of them. The policy reference is recorded and never resolved.
import { useState } from "react";

import { GapNotice } from "./GapNotice";
import { ActionButton, Json, Panel, ScreenFrame } from "./ScreenFrame";
import { useDeclareVendorDependency, useVendorDeclarations } from "./hooks";
import { LoadingState, QueryError } from "@/design-system/states";
import { isUnavailable } from "@/api/types-v2";
import type { VendorDeclareBody } from "@/api/types-v2";

type BindingKey = keyof VendorDeclareBody["binding"];

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

/** FD-13.4: the posture is a record, not an assessment. Said on every answer. */
function PostureNotice({ note }: { note: string }) {
  return (
    <div
      role="note"
      aria-label="risk posture"
      className="rounded border border-surface-border bg-surface-2 px-3 py-2 text-[12px] text-ink-1"
    >
      <span className="font-semibold">Risk posture:</span> {note}
    </div>
  );
}

export function VendorScreen() {
  const [binding, setBinding] = useState<Record<BindingKey, string>>(EMPTY_BINDING);
  const [vendorRef, setVendorRef] = useState("");
  const [posture, setPosture] = useState("");
  const [policyRef, setPolicyRef] = useState("");
  const [issuedAt, setIssuedAt] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [supersedes, setSupersedes] = useState("");
  const [declaredBy, setDeclaredBy] = useState("");
  const [notes, setNotes] = useState("");

  const declare = useDeclareVendorDependency();
  const declarations = useVendorDeclarations();

  const submit = () => {
    const body: VendorDeclareBody = {
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
      vendor_ref: vendorRef,
      risk_posture_label: posture,
      policy_ref: policyRef,
      validity: { issued_at: issuedAt, expires_at: expiresAt || null },
      supersedes,
      declared_by: declaredBy,
      // No control offers one: a correlation id would tie this record to a run, and
      // this screen declares a dependency, it does not start or observe anything.
      correlation_id: "",
      notes,
    };
    declare.mutate(body, { onSuccess: () => declarations.refetch() });
  };

  const declared = declare.data;

  return (
    <ScreenFrame
      title="Vendor dependencies"
      subtitle="Record what a declarer asserts about one AI system's dependency on a vendor: an opaque reference to the vendor, what they called its risk posture, the policy they cite, and for how long."
      neverDoes="A declaration confers nothing. This screen never resolves, verifies, scores, grades, ranks, approves, onboards or contacts; the risk posture is recorded, never assessed, and a changed declaration is a new one that supersedes the old."
    >
      <Panel title="Declare a vendor dependency">
        <p className="mb-2 text-[11px] text-ink-3">
          Typed fields only. The tenant is this deployment&rsquo;s, the declaration id is
          derived by the package, and the declarer is recorded as{" "}
          <span className="font-mono">PRESENTED_UNPROVEN</span>: an opaque handle, not an
          authenticated identity. The vendor reference is a locator and never a way to
          reach the vendor. Nothing here is a supplier record, a questionnaire or a
          due-diligence workflow.
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
            id="vendor-ref"
            label="Vendor reference"
            hint="An opaque locator in your own spelling. Never an address, endpoint or credential."
            required
            value={vendorRef}
            onChange={setVendorRef}
          />
          <Field
            id="risk-posture-label"
            label="Risk posture label"
            hint="Recorded exactly as typed and interpreted nowhere: nothing orders, ranks or scores it, and it implies no approval, onboarding status, tier or certification."
            required
            value={posture}
            onChange={setPosture}
          />
          <Field
            id="policy-ref"
            label="Policy reference"
            hint="Recorded and never resolved: a reference that names nothing looks the same here as one that names a real policy."
            required
            value={policyRef}
            onChange={setPolicyRef}
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
                <p className="text-[12px] text-ink-1" data-testid="vendor-declared-notice">
                  Declared{" "}
                  <span className="font-mono">
                    {String((declared as { declaration_id?: string }).declaration_id ?? "")}
                  </span>
                  {" · "}declarer{" "}
                  {String((declared as { declared_by_status?: string }).declared_by_status ?? "")}
                  {" · "}confers {String((declared as { confers?: string }).confers ?? "")}
                </p>
                <PostureNotice
                  note={String((declared as { risk_posture?: string }).risk_posture ?? "")}
                />
                <Json value={(declared as { record?: unknown }).record} label="Declaration record" />
              </>
            )}
          </div>
        ) : null}
      </Panel>

      <Panel title="Vendor declarations in force">
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
              <PostureNotice
                note={String((declarations.data as { risk_posture?: string }).risk_posture ?? "")}
              />
              {(() => {
                const records = ((declarations.data as { result?: unknown[] }).result ??
                  []) as unknown[];
                if (records.length === 0) {
                  return (
                    <p className="text-[12px] text-ink-2">
                      No vendor declaration is in force for this tenant at that instant.
                    </p>
                  );
                }
                // Rendered in the answer's own order. That order is the package's stable
                // key order and says nothing about which posture is worse (FD-13.4).
                return <Json value={records} label={`${records.length} declaration(s)`} />;
              })()}
            </div>
          )
        ) : null}
      </Panel>
    </ScreenFrame>
  );
}
