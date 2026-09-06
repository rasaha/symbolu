// Screen 4 — Simulate, front-door seam 6 (FD-10.5 TWO_LABELLED_PATHS).
//
// The two paths are distinct, each labelled with its executor, its hook and its
// maturity; nothing runs until a specific control is used; the worker relay sends a
// correlation id or nothing, never a workflow; and the worker's typed answer is shown
// as the worker said it, including a replay and a refusal.
import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { App } from "@/app/App";
import { installV2FetchMock, renderStudio, unavailable } from "./studioTestUtils";

afterEach(() => vi.unstubAllGlobals());

const STARTED = {
  available: true,
  path: { path: "worker_shadow_run", maturity: "REFERENCE_GRADE_SHADOW_ONLY" },
  result: {
    result: "STARTED",
    started: true,
    mode: "shadow",
    instance_id: "shadow-0123456789abcdef01234567",
    workflow_id: "wf-shadow",
    correlation_id: "c-1",
    definition_digest: "shadow-v1",
    advanced: true,
    awaiting_external: true,
    stop_reason: "ESCALATE",
    reason: "",
    workload_maturity: "FIXTURE_ONLY",
    maturity: "REFERENCE_GRADE_SHADOW_ONLY",
    identity_proof: "PRESENTED_UNPROVEN",
  },
};

function postsTo(fetchMock: ReturnType<typeof installV2FetchMock>, path: string) {
  return fetchMock.mock.calls.filter(([u]) => String(u).includes(path)) as unknown as [unknown, RequestInit][];
}

describe("4 · Simulate — two labelled paths (FD-10.5)", () => {
  it("shows both paths, each labelled with executor, hook and maturity, and runs neither by itself", async () => {
    const fetchMock = installV2FetchMock();
    renderStudio(<App />, "/studio/simulate");
    const local = await screen.findByRole("heading", { name: /path a · in-process fixture run/i });
    const worker = screen.getByRole("heading", { name: /path b · worker shadow run/i });
    expect(local).toBeInTheDocument();
    expect(worker).toBeInTheDocument();

    const localPanel = local.parentElement as HTMLElement;
    expect(within(localPanel).getByText(/this studio's own agent runtime/i)).toBeInTheDocument();
    expect(within(localPanel).getByText(/every consequential task blocks/i)).toBeInTheDocument();
    expect(within(localPanel).getByText(/DEMONSTRATION_ONLY/)).toBeInTheDocument();

    const workerPanel = worker.parentElement as HTMLElement;
    expect(within(workerPanel).getByText(/the governed runtime worker, a separate unit/i)).toBeInTheDocument();
    expect(within(workerPanel).getByText(/parks on ESCALATE in the review queue/i)).toBeInTheDocument();
    expect(within(workerPanel).getByText(/REFERENCE_GRADE_SHADOW_ONLY; the worker's providers are FIXTURE_ONLY/)).toBeInTheDocument();

    // no path is defaulted: nothing has been sent to either run route
    expect(postsTo(fetchMock, "/api/v2/simulate/run")).toHaveLength(0);
    expect(postsTo(fetchMock, "/api/v2/review/runs")).toHaveLength(0);
    expect(screen.getByRole("button", { name: /^run simulation$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^start worker shadow run$/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /live/i })).toBeNull();
  });

  it("the worker relay sends a correlation id or nothing, never a workflow", async () => {
    const fetchMock = installV2FetchMock({ results: { "/api/v2/review/runs": STARTED } });
    renderStudio(<App />, "/studio/simulate");
    await userEvent.click(await screen.findByRole("button", { name: /start worker shadow run/i }));
    let [call] = postsTo(fetchMock, "/api/v2/review/runs");
    expect(JSON.parse(String(call[1].body))).toEqual({});

    await userEvent.type(screen.getByLabelText(/correlation id/i), "c-1");
    await userEvent.click(screen.getByRole("button", { name: /start worker shadow run/i }));
    [, call] = postsTo(fetchMock, "/api/v2/review/runs");
    const body = JSON.parse(String(call[1].body));
    expect(body).toEqual({ correlation_id: "c-1" });
    for (const key of ["workflow", "tasks", "provider_id", "mode", "execution_mode", "definition_digest"]) {
      expect(body).not.toHaveProperty(key);
    }
    expect(postsTo(fetchMock, "/api/v2/simulate/run")).toHaveLength(0);
  });

  it("a malformed correlation id is refused on screen and nothing is sent", async () => {
    const fetchMock = installV2FetchMock({ results: { "/api/v2/review/runs": STARTED } });
    renderStudio(<App />, "/studio/simulate");
    await userEvent.type(await screen.findByLabelText(/correlation id/i), "has space");
    expect(screen.getByRole("alert")).toHaveTextContent(/typed token/i);
    const button = screen.getByRole("button", { name: /start worker shadow run/i });
    expect(button).toBeDisabled();
    await userEvent.click(button);
    expect(postsTo(fetchMock, "/api/v2/review/runs")).toHaveLength(0);
  });

  it("renders the worker's typed answer as the worker said it", async () => {
    installV2FetchMock({ results: { "/api/v2/review/runs": STARTED } });
    renderStudio(<App />, "/studio/simulate");
    await userEvent.click(await screen.findByRole("button", { name: /start worker shadow run/i }));
    const status = await screen.findByRole("status", { name: /worker outcome/i });
    expect(status).toHaveTextContent(/STARTED/);
    expect(status).toHaveTextContent(/waits on the review queue for a recorded decision/i);
    const result = screen.getByTestId("worker-result");
    expect(result).toHaveTextContent(/shadow-0123456789abcdef01234567/);
    expect(result).toHaveTextContent(/wf-shadow/);
    expect(result).toHaveTextContent(/shadow-v1/);
    expect(result).toHaveTextContent(/FIXTURE_ONLY/);
    expect(result).toHaveTextContent(/PRESENTED_UNPROVEN/);
  });

  it("shows a replay and a refusal distinctly, never as a fresh run", async () => {
    installV2FetchMock({
      results: {
        "/api/v2/review/runs": {
          ...STARTED,
          result: { ...STARTED.result, result: "REPLAYED", advanced: false },
        },
      },
    });
    renderStudio(<App />, "/studio/simulate");
    await userEvent.click(await screen.findByRole("button", { name: /start worker shadow run/i }));
    expect(await screen.findByRole("status", { name: /worker outcome/i })).toHaveTextContent(/nothing was re-run/i);

    vi.unstubAllGlobals();
    installV2FetchMock({
      results: {
        "/api/v2/review/runs": {
          ...STARTED,
          result: { ...STARTED.result, result: "REFUSED_DEFINITION", started: false, reason: "digest mismatch" },
        },
      },
    });
    renderStudio(<App />, "/studio/simulate");
    const buttons = await screen.findAllByRole("button", { name: /start worker shadow run/i });
    await userEvent.click(buttons[buttons.length - 1]);
    const statuses = await screen.findAllByRole("status", { name: /worker outcome/i });
    const refused = statuses[statuses.length - 1];
    expect(refused).toHaveTextContent(/REFUSED_DEFINITION/);
    expect(refused).toHaveTextContent(/digest mismatch/);
  });

  it("an unconfigured review service is a gap on the worker path and leaves the local path intact", async () => {
    installV2FetchMock({
      results: {
        "/api/v2/review/runs": unavailable("review_service", "no governed review service base URL is configured"),
      },
    });
    renderStudio(<App />, "/studio/simulate");
    await userEvent.click(await screen.findByRole("button", { name: /start worker shadow run/i }));
    const worker = await screen.findByTestId("worker-result");
    const note = within(worker).getByRole("note", { name: /capability unavailable/i });
    expect(note).toHaveTextContent(/review_service/);
    expect(screen.queryByTestId("local-result")).toBeNull();
    expect(screen.getByRole("button", { name: /^run simulation$/i })).toBeEnabled();
  });
});
