// Screen 6 — Observe.
//
// Renders the console's audit chain exactly as returned. It does not re-derive,
// re-order or re-hash it: the console's audit store is the record, and a studio-side
// reconstruction would be a second, unverified account of the same events.
//
// "Unreachable" and "empty" are shown differently, on purpose. On an audit screen
// those two must never look alike.
import { useState } from "react";

import { GapNotice } from "./GapNotice";
import { ActionButton, Json, Panel, ScreenFrame } from "./ScreenFrame";
import { useAuditChain, useAuditCorrelationIds } from "./hooks";
import { LoadingState, QueryError } from "@/design-system/states";
import { isUnavailable } from "@/api/types-v2";

export function ObserveScreen() {
  const [correlationId, setCorrelationId] = useState<string>("");
  const [selected, setSelected] = useState<string | null>(null);
  const ids = useAuditCorrelationIds();
  const chain = useAuditChain(selected);

  return (
    <ScreenFrame
      title="Observe"
      subtitle="Reconstruct a decision chain by correlation id, as the console recorded it."
      neverDoes="This screen re-derives nothing. What is shown is what the console returned."
    >
      <Panel title="Correlation ids">
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
                        className="rounded border border-surface-border bg-surface-2 px-2 py-1 font-mono text-[11px] text-ink-0 hover:bg-surface-3"
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
      </Panel>

      <Panel title="Look up a chain">
        <label htmlFor="correlation-id" className="mb-1 block text-[11px] text-ink-2">
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
      </Panel>

      {selected ? (
        <Panel title={`Chain for ${selected}`}>
          {chain.isLoading ? <LoadingState label="Reconstructing…" /> : null}
          {chain.error ? <QueryError error={chain.error} /> : null}
          {chain.data ? (
            isUnavailable(chain.data) ? (
              <GapNotice gap={chain.data} />
            ) : (
              <Json value={(chain.data as { result?: unknown }).result} label="Decision chain" />
            )
          ) : null}
        </Panel>
      ) : null}
    </ScreenFrame>
  );
}
