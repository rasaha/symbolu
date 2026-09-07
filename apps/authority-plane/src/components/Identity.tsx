/**
 * What every answer says about identity, shown on every screen, before the answer.
 *
 * A read is not authenticated; the worker says so on each answer, and this component
 * says it again where the operator looks. `decision_identity_proof` is what the
 * deployment can prove about a decision, not about this read, and
 * `issuer_validation` stays IN_PROCESS_ISSUER_ONLY until AI-C is validated against a
 * real issuer. A grant listed here is what an administrator loaded.
 */
import type { ReadEnvelope, Refusal } from "@/api/client";

export function IdentityBanner({ answer }: { answer: ReadEnvelope }) {
  const proven = answer.decision_identity_proof === "IDP_AUTHENTICATED";
  return (
    <div
      role="note"
      aria-label="identity and provenance"
      className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-[12px] text-amber-950"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded border border-amber-400 px-1.5 py-0.5 font-mono text-[11px]">
          read_authenticated: false
        </span>
        <span className="rounded border border-amber-400 px-1.5 py-0.5 font-mono text-[11px]">
          decision proof: {answer.decision_identity_proof}
        </span>
        <span className="rounded border border-amber-400 px-1.5 py-0.5 font-mono text-[11px]">
          issuer validation: {answer.issuer_validation}
        </span>
        <span className="rounded border border-amber-400 px-1.5 py-0.5 font-mono text-[11px]">{answer.maturity}</span>
      </div>
      <p className="mt-1 leading-relaxed">
        This read was not authenticated. {proven
          ? "An identity port is composed, so a decision on this worker can carry an issuer-authenticated approver;"
          : "No identity port is composed, so every decision on this worker is a presented, unproven approver;"}{" "}
        the adapter has been validated against an in-process issuer only. What is listed below is {answer.provenance}.
      </p>
      <p className="mt-1 font-mono text-[11px]">
        tenant {answer.tenant_id} · as of {answer.as_of}
      </p>
    </div>
  );
}

export function RefusalNotice({ status, refusal }: { status: number; refusal: Refusal }) {
  return (
    <div role="status" aria-label="typed refusal" className="rounded border border-neutral-400 bg-neutral-50 px-3 py-2 text-[12px]">
      <span className="font-mono">{refusal.result}</span> · HTTP {status} · {refusal.reason}
    </div>
  );
}

export function Unreachable({ reason }: { reason: string }) {
  return (
    <div role="alert" className="rounded border border-red-300 bg-red-50 px-3 py-2 text-[12px] text-red-900">
      <span className="font-semibold">The authority plane's worker is not reachable.</span> {reason}
    </div>
  );
}

export function Json({ value, label }: { value: unknown; label: string }) {
  return (
    <details className="mt-2">
      <summary className="cursor-pointer text-[11px] text-neutral-700">{label}</summary>
      <pre className="mt-1 max-h-72 overflow-auto rounded bg-neutral-100 p-2 font-mono text-[11px] leading-relaxed">
        {JSON.stringify(value, null, 2)}
      </pre>
    </details>
  );
}
