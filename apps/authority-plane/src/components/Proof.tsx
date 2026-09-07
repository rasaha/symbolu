/**
 * The issuer token an administrator presents for this session (AW-3).
 *
 * The plane has no login of its own: the enterprise identity provider is the login,
 * and what it issued is presented here, held in memory only, sent on writes only on
 * the worker's proof header, never on a read, and never stored. Clearing it, or
 * closing the tab, is the end of it. Until the adapter is validated against a real
 * issuer, every answer says the subject was proven by an in-process issuer only.
 */
import { useState } from "react";
import type { WriteOutcome } from "@/api/client";
import { Unreachable } from "@/components/Identity";

export function ProofPanel({ proof, onChange }: { proof: string; onChange: (proof: string) => void }) {
  const [draft, setDraft] = useState("");
  const presented = proof !== "";
  return (
    <section aria-labelledby="proof-title" className="rounded border border-neutral-300 bg-neutral-50 px-3 py-2 text-[12px]">
      <h2 id="proof-title" className="font-semibold">Issuer token for this session</h2>
      <p className="mt-1 text-neutral-700">
        Present the token your identity provider issued you. It is held in memory only, sent on writes only, never on a
        read, and never stored. A write is recorded only when the worker&rsquo;s identity adapter proves it as a human of
        this tenant.
      </p>
      <div className="mt-2 flex flex-col gap-2 sm:flex-row">
        <label htmlFor="issuer-token" className="sr-only">issuer token</label>
        <input
          id="issuer-token"
          type="password"
          autoComplete="off"
          className="field flex-1"
          placeholder="issuer token"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && draft.trim()) {
              onChange(draft.trim());
              setDraft("");
            }
          }}
        />
        <button
          type="button"
          className="btn-action"
          disabled={!draft.trim()}
          onClick={() => {
            onChange(draft.trim());
            setDraft("");
          }}
        >
          Present token
        </button>
        <button type="button" className="btn-action" disabled={!presented} onClick={() => onChange("")}>
          Clear
        </button>
      </div>
      <p role="status" aria-label="token presented" className="mt-2 font-mono text-[11px]">
        {presented
          ? "a token is presented for this session · sent on writes only · never on a read · never stored"
          : "no token presented · every write control is disabled · reads need none"}
      </p>
    </section>
  );
}

/** What a write came back as: recorded under a proven subject, refused with a reason, or unreachable. */
export function WriteResult({ outcome }: { outcome: WriteOutcome }) {
  if (outcome.kind === "unreachable") return <Unreachable reason={outcome.reason} />;
  if (outcome.kind === "refusal") {
    return (
      <div role="status" aria-label="write refused" className="rounded border border-neutral-400 bg-neutral-50 px-3 py-2 text-[12px]">
        <span className="font-mono">{outcome.refusal.result}</span>
        {outcome.status ? <> · HTTP {outcome.status}</> : null} · {outcome.refusal.reason}
        {outcome.refusal.ruling ? <> · ruling {outcome.refusal.ruling}</> : null}
        <div className="mt-1 text-neutral-700">Nothing was recorded.</div>
      </div>
    );
  }
  const a = outcome.answer;
  return (
    <div role="status" aria-label="write recorded" className="rounded border border-green-700 bg-green-50 px-3 py-2 text-[12px] text-green-950">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded border border-green-700 px-1.5 py-0.5 font-mono text-[11px]">{a.event}</span>
        <span className="rounded border border-green-700 px-1.5 py-0.5 font-mono text-[11px]">identity proof: {a.identity_proof}</span>
        <span className="rounded border border-green-700 px-1.5 py-0.5 font-mono text-[11px]">issuer validation: {a.issuer_validation}</span>
        <span className="rounded border border-green-700 px-1.5 py-0.5 font-mono text-[11px]">{a.maturity}</span>
      </div>
      <p className="mt-1">
        Recorded by <span className="font-mono">{a.subject}</span> at <span className="font-mono">{a.as_of}</span> on grant{" "}
        <span className="font-mono">{a.grant.grant_id}</span>.
      </p>
      <p className="mt-1 font-mono text-[11px]">authentication reference {a.authentication_reference}</p>
      <p className="mt-1 text-[11px]">
        The subject was proven by the worker&rsquo;s identity adapter, which has been validated against an in-process
        issuer only; nothing here claims a real issuer proved it.
      </p>
    </div>
  );
}
