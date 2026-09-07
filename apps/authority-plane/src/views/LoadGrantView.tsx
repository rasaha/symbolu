/**
 * Load one time-bounded role grant (AW-1, AW-4): the typed fields of a role grant and
 * nothing else. The worker derives the grant id, so an identical replay is the same
 * grant, answered ALREADY_LOADED. The write is sent only with a presented token (AW-3)
 * and recorded only for a human subject of this tenant the identity adapter proved
 * (AW-5).
 */
import { useState } from "react";
import { grantRole, type LoadGrantRequest, type WriteOutcome } from "@/api/client";
import { WriteResult } from "@/components/Proof";

const KINDS = ["HUMAN", "COMMITTEE", "SERVICE", "DELEGATED_POLICY"] as const;

function iso(offsetDays: number): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + offsetDays);
  d.setUTCMilliseconds(0);
  return d.toISOString().replace(".000Z", "Z");
}

export function LoadGrantView({ proof, onEvents }: { proof: string; onEvents: (grantId: string) => void }) {
  const [principalId, setPrincipalId] = useState("");
  const [kind, setKind] = useState<(typeof KINDS)[number]>("HUMAN");
  const [displayRef, setDisplayRef] = useState("");
  const [quorum, setQuorum] = useState("0");
  const [role, setRole] = useState("");
  const [scope, setScope] = useState("");
  const [issuedAt, setIssuedAt] = useState(iso(0));
  const [expiresAt, setExpiresAt] = useState(iso(90));
  const [authorityReference, setAuthorityReference] = useState("");
  const [memberOf, setMemberOf] = useState("");
  const [outcome, setOutcome] = useState<WriteOutcome | null>(null);
  const [busy, setBusy] = useState(false);

  const quorumValue = Number.parseInt(quorum, 10);
  const complete = [principalId, role, scope, issuedAt, expiresAt].every((v) => v.trim() !== "")
    && Number.isInteger(quorumValue) && quorumValue >= 0;
  const canSend = proof !== "" && complete && !busy;

  async function send() {
    if (!canSend) return;
    const request: LoadGrantRequest = {
      principal: { principal_id: principalId.trim(), principal_kind: kind, display_ref: displayRef.trim(), quorum: quorumValue },
      role: role.trim(),
      scope: scope.trim(),
      issued_at: issuedAt.trim(),
      expires_at: expiresAt.trim(),
      authority_reference: authorityReference.trim(),
      member_of: memberOf.trim(),
    };
    setBusy(true);
    try {
      setOutcome(await grantRole(request, proof));
    } finally {
      setBusy(false);
    }
  }

  const field = (id: string, label: string, value: string, set: (v: string) => void, placeholder = label) => (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-[11px] text-neutral-700">{label}</label>
      <input id={id} className="field" placeholder={placeholder} value={value} onChange={(e) => set(e.target.value)} />
    </div>
  );

  return (
    <section className="space-y-3" aria-labelledby="load-title">
      <h2 id="load-title" className="text-base font-semibold">Load a role grant</h2>
      <p className="text-[12px] text-neutral-700">
        Record that one principal holds one role in one scope for one bounded window. The worker derives the grant id
        from these fields, so loading the same grant twice answers ALREADY_LOADED with the standing grant. A grant is a
        record: it is never edited, only revoked. Loading confers a role grant and nothing else; it authorizes, clears and
        executes nothing (AP-4).
      </p>
      {proof === "" ? (
        <p role="note" aria-label="no token for load" className="rounded border border-neutral-300 bg-neutral-50 px-3 py-2 text-[12px]">
          Present an issuer token above to load a grant. Nothing is sent without one, and the worker records nothing
          for a subject it did not prove.
        </p>
      ) : null}
      <form
        aria-label="load grant"
        className="grid grid-cols-1 gap-3 sm:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        {field("load-principal-id", "principal id", principalId, setPrincipalId, "issuer-qualified subject, percent-encoded")}
        <div className="flex flex-col gap-1">
          <label htmlFor="load-principal-kind" className="text-[11px] text-neutral-700">principal kind</label>
          <select id="load-principal-kind" className="field" value={kind} onChange={(e) => setKind(e.target.value as (typeof KINDS)[number])}>
            {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
          </select>
        </div>
        {field("load-display-ref", "display reference", displayRef, setDisplayRef, "directory://people/…")}
        {field("load-quorum", "quorum (committees only)", quorum, setQuorum, "0")}
        {field("load-role", "role", role, setRole)}
        {field("load-scope", "scope", scope, setScope, "approval/policy_pack")}
        {field("load-issued-at", "issued at (ISO 8601, with timezone)", issuedAt, setIssuedAt)}
        {field("load-expires-at", "expires at (ISO 8601, with timezone)", expiresAt, setExpiresAt)}
        {field("load-authority-reference", "authority reference", authorityReference, setAuthorityReference, "directory://roles/…")}
        {field("load-member-of", "member of (committee id)", memberOf, setMemberOf, "")}
        <div className="sm:col-span-2">
          <button type="submit" className="btn-action" aria-label="load this grant" disabled={!canSend}>
            Load grant
          </button>
        </div>
      </form>
      {outcome ? (
        <div className="space-y-2" data-testid="load-result">
          <WriteResult outcome={outcome} />
          {outcome.kind === "recorded" ? (
            <button type="button" className="btn-action px-2 py-0.5 text-[11px]" onClick={() => onEvents(outcome.answer.grant.grant_id)}>
              Events
            </button>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
