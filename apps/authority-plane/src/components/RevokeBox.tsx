/**
 * Revoke one grant with a reason (AW-1), behind the presented token (AW-3). Revocation
 * is forward-only: the directory appends a REVOKED event under the proven subject and
 * never edits the grant in place.
 */
import { useState } from "react";
import { revokeGrant, type WriteOutcome } from "@/api/client";
import { WriteResult } from "@/components/Proof";

export function RevokeBox({ grantId, proof, onRecorded, onCancel }: {
  grantId: string;
  proof: string;
  onRecorded: () => void;
  onCancel: () => void;
}) {
  const [reason, setReason] = useState("");
  const [outcome, setOutcome] = useState<WriteOutcome | null>(null);
  const [busy, setBusy] = useState(false);
  const canSend = proof !== "" && reason.trim() !== "" && !busy;

  async function send() {
    if (!canSend) return;
    setBusy(true);
    try {
      const result = await revokeGrant(grantId, reason.trim(), proof);
      setOutcome(result);
      if (result.kind === "recorded") onRecorded();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div role="region" aria-label={`revoke ${grantId}`} className="space-y-2 rounded border border-neutral-300 px-3 py-2 text-[12px]">
      <p>
        Revoke grant <span className="font-mono">{grantId}</span>. From the worker&rsquo;s clock at the write, the grant is
        absent from every answer; its history keeps the REVOKED event under your proven subject.
      </p>
      {proof === "" ? (
        <p role="note" aria-label="no token for revoke" className="text-neutral-700">
          Present an issuer token above to revoke. Nothing is sent without one.
        </p>
      ) : null}
      <div className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor={`revoke-reason-${grantId}`} className="sr-only">reason</label>
        <input
          id={`revoke-reason-${grantId}`}
          className="field flex-1"
          placeholder="reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button type="button" className="btn-action" onClick={send} disabled={!canSend}>
          Revoke grant
        </button>
        <button type="button" className="btn-action" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
      {outcome ? <WriteResult outcome={outcome} /> : null}
    </div>
  );
}
