// Screen 6 — Observe.
//
// Two labelled sources, never merged (front-door ruling FD-11.4 TWO_LABELLED_SOURCES).
//
// Source A is the governed runtime worker's own audit ledger (seam 7): durable,
// per-tenant, hash-chained, append-only by database trigger; what it holds are
// receipts and references (kind, payload, digests), raw and uninterpreted, read by
// the worker for its own tenant. Source B is the console's audit chain: stage
// narratives held by one console instance in memory, and while FD-8.1 holds the
// console is absent, so this source reports its typed gap. Each source names its
// record type, its executor and its maturity beside its own control.
//
// This screen re-derives, re-orders and re-hashes nothing. What is shown is what the
// worker or the console returned, including the worker's own chain verification, and
// a worker refusal that withholds entries is shown as exactly that.
//
// "Unreachable", "empty", "not found" and "refused" are shown differently, on purpose.
// On an audit screen none of those may look alike.
import { useState } from "react";

import { GapNotice } from "./GapNotice";
import { ActionButton, Json, Panel, ScreenFrame } from "./ScreenFrame";
import { useAuditChain, useAuditCorrelationIds, useLedgerChain } from "./hooks";
import { LoadingState, QueryError } from "@/design-system/states";
import { isUnavailable } from "@/api/types-v2";

/** FD-11.4: what each source is, stated where its control is. */
const SOURCES = {
  worker: {
    label: "Source A · Worker audit ledger",
    recordType: "control-plane audit-ledger rows: receipts and references (kind, payload, digests), raw and uninterpreted; not stage narratives",
    executor: "the governed runtime worker reads its own tenant's ledger (seam 7); the studio names no tenant and re-derives nothing",
    maturity: "REFERENCE_GRADE; durable, per-tenant, hash-chained; tamper-evident, not tamper-proof",
  },
  console: {
    label: "Source B · Console audit chain",
    recordType: "the console's stage chain: assertion, action, signals and disposition per correlation id",
    executor: "one console instance's in-memory audit store; absent by ruling FD-8.1 until the console is packaged (FD-8.3)",
    maturity: "prototype; lost on restart; never durable, complete, distributed or restart-safe (FD-8.5)",
  },
} as const;

/** FD-4: a correlation id is a typed token, or nothing at all. */
const CORRELATION_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$/;

function SourceLabel({ source }: { source: (typeof SOURCES)[keyof typeof SOURCES] }) {
  return (
    <dl className="mb-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[11px] text-ink-2">
      <dt className="font-medium text-ink-3">Record type</dt>
      <dd>{source.recordType}</dd>
      <dt className="font-medium text-ink-3">Executor</dt>
      <dd>{source.executor}</dd>
      <dt className="font-medium text-ink-3">Maturity</dt>
      <dd className="font-mono">{source.maturity}</dd>
    </dl>
  );
}

function str(value: unknown, key: string): string {
  return String((value as Record<string, unknown>)[key] ?? "");
}

export function ObserveScreen() {
  const [correlationId, setCorrelationId] = useState<string>("");
  const [selected, setSelected] = useState<string | null>(null);
  const [ledgerId, setLedgerId] = useState<string>("");
  const [ledgerSelected, setLedgerSelected] = useState<string | null>(null);
  const ids = useAuditCorrelationIds();
  const chain = useAuditChain(selected);
  const ledger = useLedgerChain(ledgerSelected);
  const ledgerValid = ledgerId === "" || CORRELATION_ID.test(ledgerId);

  return (
    <ScreenFrame
      title="Observe"
      subtitle="Two distinct sources: the governed runtime worker's own audit ledger, and the console's audit chain. Each is labelled with its record type, its executor and its maturity."
      neverDoes="This screen re-derives nothing. What is shown is what the worker or the console returned, verification included; no source is chosen for you."
    >
      <Panel title={SOURCES.worker.label}>
        <SourceLabel source={SOURCES.worker} />
        <label htmlFor="ledger-correlation-id" className="mb-1 block text-[11px] text-ink-2">
          Correlation id
        </label>
        <div className="flex gap-2">
          <input
            id="ledger-correlation-id"
            value={ledgerId}
            onChange={(e) => setLedgerId(e.target.value)}
            aria-invalid={!ledgerValid}
            className="flex-1 rounded border border-surface-border bg-surface-0 px-2 py-1 font-mono text-[11px] text-ink-0"
          />
          <ActionButton onClick={() => setLedgerSelected(ledgerId)} disabled={ledgerId === "" || !ledgerValid}>
            Read ledger
          </ActionButton>
        </div>
        {!ledgerValid ? (
          <p role="alert" className="mt-1 text-[11px] text-red-700">
            A correlation id is a typed token: letters, digits, &lsquo;.&rsquo;, &lsquo;_&rsquo;, &lsquo;:&rsquo; and
            &lsquo;-&rsquo;, at most 64 characters. Nothing is read until it is.
          </p>
        ) : null}
        {ledgerSelected ? (
          <div className="mt-3" data-testid="ledger-result">
            {ledger.isLoading ? <LoadingState label="Reading the worker's ledger…" /> : null}
            {ledger.error ? <QueryError error={ledger.error} /> : null}
            {ledger.data ? (
              isUnavailable(ledger.data) ? (
                <GapNotice gap={ledger.data} />
              ) : (
                <LedgerAnswer data={ledger.data as Record<string, unknown>} correlationId={ledgerSelected} />
              )
            ) : null}
          </div>
        ) : null}
      </Panel>

      <Panel title={SOURCES.console.label}>
        <SourceLabel source={SOURCES.console} />
        <h3 className="mb-1 text-[11px] font-semibold text-ink-2">Correlation ids</h3>
        {ids.isLoading ? <LoadingState label="Reading the audit store…" /> : null}
        {ids.error ? <QueryError error={ids.error} /> : null}
        {ids.data ? (
          isUnavailable(ids.data) ? (
            <GapNotice gap={ids.data} />
          ) : (
            (() => {
              const list = ((ids.data as { result?: unknown }).result ?? []) as string[];
              if (!Array.isArray(list) || list.length === 0) {
                return (
                  <p className="text-[12px] text-ink-2" role="status">
                    The console is reachable and reported no correlation ids. That is an
                    empty audit store, not a failure to read it.
                  </p>
                );
              }
              return (
                <ul className="flex flex-wrap gap-2">
                  {list.map((id) => (
                    <li key={id}>
                      <button
                        type="button"
                        onClick={() => setSelected(id)}
                        className="btn-action px-2 py-1 font-mono text-[11px]"
                      >
                        {id}
                      </button>
                    </li>
                  ))}
                </ul>
              );
            })()
          )
        ) : null}
        <label htmlFor="correlation-id" className="mb-1 mt-3 block text-[11px] text-ink-2">
          Correlation id
        </label>
        <div className="flex gap-2">
          <input
            id="correlation-id"
            value={correlationId}
            onChange={(e) => setCorrelationId(e.target.value)}
            className="flex-1 rounded border border-surface-border bg-surface-0 px-2 py-1 font-mono text-[11px] text-ink-0"
          />
          <ActionButton onClick={() => setSelected(correlationId)} disabled={correlationId === ""}>
            Reconstruct
          </ActionButton>
        </div>
        {selected ? (
          <div className="mt-3" data-testid="console-result">
            <h3 className="mb-1 text-[11px] font-semibold text-ink-2">Chain for {selected}</h3>
            {chain.isLoading ? <LoadingState label="Reconstructing…" /> : null}
            {chain.error ? <QueryError error={chain.error} /> : null}
            {chain.data ? (
              isUnavailable(chain.data) ? (
                <GapNotice gap={chain.data} />
              ) : (
                <Json value={(chain.data as { result?: unknown }).result} label="Decision chain" />
              )
            ) : null}
          </div>
        ) : null}
      </Panel>
    </ScreenFrame>
  );
}

/** The worker's typed answer, rendered as the worker read it. */
function LedgerAnswer({ data, correlationId }: { data: Record<string, unknown>; correlationId: string }) {
  if (data.found === false) {
    return (
      <p role="status" aria-label="ledger outcome" className="text-[12px] text-ink-2">
        The worker reports no entry of its tenant carrying <span className="font-mono">{correlationId}</span>.
        That is a typed not-found from a reachable worker, not an empty ledger and not a failure to read it.
      </p>
    );
  }
  const answer = (data.result ?? {}) as Record<string, unknown>;
  const read = answer.read === true;
  const verified = answer.chain_verified === true;
  const entries = Array.isArray(answer.entries) ? (answer.entries as Record<string, unknown>[]) : [];
  return (
    <div className="space-y-2">
      <div
        role="status"
        aria-label="ledger outcome"
        className={
          read
            ? "rounded border border-surface-border bg-surface-2 px-3 py-2 text-[12px] text-ink-1"
            : "rounded border border-amber-300 bg-amber-50 px-3 py-2 text-[12px] text-amber-950"
        }
      >
        <span className="font-semibold">{str(answer, "result") || "no outcome"}</span>
        {" · chain verified by the worker: "}
        <span className="font-mono">{verified ? "true" : "false"}</span>
        {!read && str(answer, "reason") ? <p className="mt-1">{str(answer, "reason")}</p> : null}
        {!read && str(answer, "result") === "REFUSED_INTEGRITY"
          ? " The worker withheld the entries; nothing is shown that the chain does not vouch for."
          : null}
      </div>
      <div className="text-[11px] text-ink-2">
        Tenant <span className="font-mono">{str(answer, "tenant_id")}</span> · entries{" "}
        <span className="font-mono">{String(answer.entry_count ?? entries.length)}</span> · record type{" "}
        <span className="font-mono">{str(answer, "record_type")}</span> · maturity{" "}
        <span className="font-mono">{str(answer, "maturity")}</span>
      </div>
      {read ? (
        <ol className="space-y-1" aria-label="ledger entries">
          {entries.map((entry) => (
            <li key={str(entry, "entry_ref")} className="rounded border border-surface-border bg-surface-1 px-2 py-1 text-[11px] text-ink-1">
              <span className="font-mono">{str(entry, "entry_ref")}</span> · {str(entry, "kind")} · recorded{" "}
              {str(entry, "recorded_at")} by {str(entry, "recorded_by")} · digest{" "}
              <span className="font-mono">{str(entry, "record_digest").slice(0, 16)}…</span>
            </li>
          ))}
        </ol>
      ) : null}
      <Json value={answer} label="Worker answer" />
    </div>
  );
}
