// Screen 6 — Observe, front-door seam 7 (FD-11.4 TWO_LABELLED_SOURCES).
//
// The two sources are distinct, each labelled with its record type, its executor and
// its maturity; nothing is read until a specific control is used; the worker's typed
// answer is shown as the worker read it, verification included; a refusal that
// withholds entries, a typed not-found and a gap never look alike or like an empty
// ledger; and the console source keeps its own typed gap while FD-8.1 holds.
import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "@/app/App";
import { installV2FetchMock, renderStudio, unavailable } from "./studioTestUtils";

afterEach(() => vi.unstubAllGlobals());

const SOURCE = {
  source: "worker_audit_ledger",
  record_type: "control-plane audit-ledger rows",
  executor: "the worker reads its own tenant",
  maturity: "REFERENCE_GRADE",
};

const READ = {
  available: true,
  found: true,
  source: SOURCE,
  result: {
    result: "READ",
    read: true,
    tenant_id: "tenant-a",
    correlation_id: "c-1",
    entries: [
      {
        seq: 1,
        entry_ref: "tenant-a/1",
        kind: "governed_review.linkage.v2",
        recorded_at: "2026-09-06T09:00:00+00:00",
        recorded_by: "governed-runtime-worker",
        correlation_id: "c-1",
        payload: { instance_id: "shadow-1" },
        prev_digest: "0".repeat(64),
        record_digest: "abcdef0123456789".repeat(4),
      },
    ],
    entry_count: 1,
    chain_verified: true,
    reason: "",
    record_type: "control_plane_root audit-ledger rows, raw and uninterpreted",
    maturity: "REFERENCE_GRADE_SHADOW_ONLY",
  },
};

function getsTo(fetchMock: ReturnType<typeof installV2FetchMock>, path: string) {
  return fetchMock.mock.calls.filter(([u]) => String(u).includes(path));
}

async function readLedger(id: string) {
  await userEvent.type(await screen.findByLabelText(/^correlation id$/i, { selector: "#ledger-correlation-id" }), id);
  await userEvent.click(screen.getByRole("button", { name: /read ledger/i }));
}

describe("6 · Observe — two labelled sources (FD-11.4)", () => {
  it("shows both sources, each labelled with record type, executor and maturity, and reads neither by itself", async () => {
    const fetchMock = installV2FetchMock();
    renderStudio(<App />, "/studio/observe");
    const worker = await screen.findByRole("heading", { name: /source a · worker audit ledger/i });
    const console_ = screen.getByRole("heading", { name: /source b · console audit chain/i });
    const workerPanel = worker.parentElement as HTMLElement;
    expect(within(workerPanel).getByText(/receipts and references/i)).toBeInTheDocument();
    expect(within(workerPanel).getByText(/reads its own tenant's ledger/i)).toBeInTheDocument();
    expect(within(workerPanel).getByText(/REFERENCE_GRADE; durable, per-tenant, hash-chained/)).toBeInTheDocument();
    const consolePanel = console_.parentElement as HTMLElement;
    expect(within(consolePanel).getByText(/stage chain/i)).toBeInTheDocument();
    expect(within(consolePanel).getByText(/absent by ruling FD-8.1/i)).toBeInTheDocument();
    expect(within(consolePanel).getByText(/lost on restart/i)).toBeInTheDocument();
    // the console source keeps its typed gap; the ledger is not read until asked
    expect(await within(consolePanel).findByRole("note", { name: /capability unavailable/i })).toHaveTextContent(/console_api/);
    expect(getsTo(fetchMock, "/api/v2/observe/ledger/")).toHaveLength(0);
    expect(screen.getByRole("button", { name: /read ledger/i })).toBeDisabled();
  });

  it("reads the worker's ledger by correlation id and renders the answer as the worker read it", async () => {
    const fetchMock = installV2FetchMock({ results: { "/api/v2/observe/ledger/c-1": READ } });
    renderStudio(<App />, "/studio/observe");
    await readLedger("c-1");
    const status = await screen.findByRole("status", { name: /ledger outcome/i });
    expect(status).toHaveTextContent(/READ/);
    expect(status).toHaveTextContent(/chain verified by the worker: true/i);
    const result = screen.getByTestId("ledger-result");
    expect(within(result).getByRole("list", { name: /ledger entries/i })).toHaveTextContent(/tenant-a\/1/);
    expect(result).toHaveTextContent(/governed_review\.linkage\.v2/);
    expect(result).toHaveTextContent(/governed-runtime-worker/);
    expect(result).toHaveTextContent(/raw and uninterpreted/);
    expect(getsTo(fetchMock, "/api/v2/observe/ledger/c-1")).toHaveLength(1);
    expect(getsTo(fetchMock, "/api/v2/observe/audit/")).toHaveLength(0);
  });

  it("a refusal that withholds entries is shown as a refusal, never as an empty ledger", async () => {
    installV2FetchMock({
      results: {
        "/api/v2/observe/ledger/c-1": {
          ...READ,
          result: { ...READ.result, result: "REFUSED_INTEGRITY", read: false, entries: [], entry_count: 0,
                    chain_verified: false, reason: "the tenant's chain does not verify; entries withheld" },
        },
      },
    });
    renderStudio(<App />, "/studio/observe");
    await readLedger("c-1");
    const status = await screen.findByRole("status", { name: /ledger outcome/i });
    expect(status).toHaveTextContent(/REFUSED_INTEGRITY/);
    expect(status).toHaveTextContent(/chain verified by the worker: false/i);
    expect(status).toHaveTextContent(/withheld the entries/i);
    expect(screen.queryByRole("list", { name: /ledger entries/i })).toBeNull();
  });

  it("a typed not-found is distinct from an empty ledger and from a read", async () => {
    installV2FetchMock({
      results: { "/api/v2/observe/ledger/c-none": { available: true, found: false, source: SOURCE, result: null } },
    });
    renderStudio(<App />, "/studio/observe");
    await readLedger("c-none");
    const status = await screen.findByRole("status", { name: /ledger outcome/i });
    expect(status).toHaveTextContent(/typed not-found from a reachable worker/i);
    expect(screen.queryByRole("list", { name: /ledger entries/i })).toBeNull();
  });

  it("an unconfigured review service is a gap on the worker source and the console source keeps its own", async () => {
    installV2FetchMock({
      results: { "/api/v2/observe/ledger/c-1": unavailable("review_service", "no governed review service base URL is configured") },
    });
    renderStudio(<App />, "/studio/observe");
    await readLedger("c-1");
    const result = await screen.findByTestId("ledger-result");
    const note = await within(result).findByRole("note", { name: /capability unavailable/i });
    expect(note).toHaveTextContent(/review_service/);
    const notes = await screen.findAllByRole("note", { name: /capability unavailable/i });
    expect(notes.map((n) => n.textContent)).toEqual(
      expect.arrayContaining([expect.stringMatching(/console_api/), expect.stringMatching(/review_service/)]),
    );
  });

  it("a malformed correlation id is refused on screen and nothing is read", async () => {
    const fetchMock = installV2FetchMock({ results: { "/api/v2/observe/ledger/c-1": READ } });
    renderStudio(<App />, "/studio/observe");
    await userEvent.type(await screen.findByLabelText(/^correlation id$/i, { selector: "#ledger-correlation-id" }), "has space");
    expect(screen.getByRole("alert")).toHaveTextContent(/typed token/i);
    expect(screen.getByRole("button", { name: /read ledger/i })).toBeDisabled();
    expect(getsTo(fetchMock, "/api/v2/observe/ledger/")).toHaveLength(0);
  });
});
