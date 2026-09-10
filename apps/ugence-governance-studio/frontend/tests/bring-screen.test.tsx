// Bring Your Workflow screen (ADR §22, BW-1 to BW-5): the operator's document enters
// through the gate, reaches exactly the three approved operations, and leaves only as
// a local download. Boundary properties are asserted on the source as well as on the
// rendered screen.
import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { App } from "@/app/App";
import { DISCLAIMER } from "@/features/bring/BringYourWorkflowScreen";
import exampleV1 from "@/features/bring/example-workflow-ir.v1.json";
import exampleV2 from "./fixtures/bring.example-v2.json";
import adaptFixture from "./fixtures/bring.adapt.json";
import { installFetchMock, renderWithProviders } from "./testUtils";

const ROUTE = "/bring-your-workflow";
const FRONTEND = path.resolve(__dirname, "..");
const v1Text = JSON.stringify(exampleV1, null, 2);
const v2Text = JSON.stringify(exampleV2, null, 2);

type Mock = ReturnType<typeof installFetchMock>;

function workflowCalls(fetchMock: Mock) {
  return fetchMock.mock.calls.map(([url]) => String(url).replace(/^https?:\/\/[^/]+/, "")).filter((p) => p.startsWith("/api/"));
}

function lastBody(fetchMock: Mock, suffix: string): Record<string, unknown> {
  const call = [...fetchMock.mock.calls].reverse().find(([url]) => String(url).endsWith(suffix));
  if (!call) throw new Error(`no request to ${suffix}`);
  return JSON.parse(String((call[1] as RequestInit)?.body ?? "{}"));
}

let downloads: Array<{ name: string; text: string }>;

beforeEach(() => {
  downloads = [];
  const urls = new Map<string, Blob>();
  vi.stubGlobal("URL", {
    ...URL,
    createObjectURL: (blob: Blob) => {
      const key = `blob:test/${urls.size}`;
      urls.set(key, blob);
      return key;
    },
    revokeObjectURL: () => undefined,
  });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    const blob = urls.get(this.getAttribute("href") ?? "");
    if (!blob) throw new Error("download without a blob");
    downloads.push({ name: this.getAttribute("download") ?? "", text: "" });
    const index = downloads.length - 1;
    // jsdom's Blob has no text(); FileReader is what a browser would also offer
    const reader = new FileReader();
    reader.onload = () => {
      downloads[index].text = String(reader.result ?? "");
    };
    reader.readAsText(blob);
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function paste(user: ReturnType<typeof userEvent.setup>, testId: string, text: string) {
  const area = screen.getByTestId(testId) as HTMLTextAreaElement;
  await user.clear(area);
  // paste, not type: typing a 4 KB document key by key is slow and exercises nothing
  await user.click(area);
  await user.paste(text);
}

describe("BW-1 — the screen, its name and its disclaimer", () => {
  it("is reachable from the shell, states the disclaimer verbatim, and offers no action before a document", async () => {
    installFetchMock();
    renderWithProviders(<App />, ROUTE);
    expect(await screen.findByRole("heading", { name: "Bring Your Workflow" })).toBeInTheDocument();
    expect(screen.getByTestId("bring-disclaimer")).toHaveTextContent(DISCLAIMER);
    expect(screen.getByText("REFERENCE_GRADE")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Bring Your Workflow" })).toHaveAttribute("href", ROUTE);
    expect(screen.queryByTestId("bring-validate")).not.toBeInTheDocument();
    expect(screen.queryByTestId("bring-summary")).not.toBeInTheDocument();
  });

  it("has no serious axe violations, empty and with the example loaded", async () => {
    installFetchMock();
    const user = userEvent.setup();
    const { container } = renderWithProviders(<App />, ROUTE);
    await screen.findByRole("heading", { name: "Bring Your Workflow" });
    const axeOpts = { rules: { "color-contrast": { enabled: false } } };
    expect(await axe(container, axeOpts)).toHaveNoViolations();
    await user.click(screen.getByTestId("bring-load-example"));
    await screen.findByTestId("bring-summary");
    expect(await axe(container, axeOpts)).toHaveNoViolations();
  });
});

describe("BW-2 — the gate in the browser", () => {
  it("the guided example loads, is summarized verbatim, and nothing is sent until an action", async () => {
    const fetchMock = installFetchMock();
    const user = userEvent.setup();
    renderWithProviders(<App />, ROUTE);
    await screen.findByTestId("bring-load-example");
    await user.click(screen.getByTestId("bring-load-example"));
    const summary = await screen.findByTestId("bring-summary");
    expect(within(summary).getByTestId("bring-node-count")).toHaveTextContent("9");
    expect(within(summary).getByTestId("bring-edge-count")).toHaveTextContent("8");
    expect(within(summary).getByText("workflow_ir.v1")).toBeInTheDocument();
    expect(within(summary).getByText("gs_procurement@1")).toBeInTheDocument();
    expect(workflowCalls(fetchMock).filter((p) => p.includes("/workflows/"))).toEqual([]);
  });

  it.each([
    ["NOT_JSON", "ir_version: workflow_ir.v2\nnodes: []\n"],
    ["UNSUPPORTED_VERSION", '{"ir_version": "workflow_ir.v9"}'],
    ["CREDENTIAL_SHAPED", '{"ir_version": "workflow_ir.v2", "client_secret": "s3cr3t"}'],
    ["REMOTE_REFERENCE", '{"ir_version": "workflow_ir.v2", "href": "https://example.invalid/x.json"}'],
  ])("refuses %s on screen with no request sent", async (code, text) => {
    const fetchMock = installFetchMock();
    const user = userEvent.setup();
    renderWithProviders(<App />, ROUTE);
    await screen.findByTestId("bring-text");
    await paste(user, "bring-text", text);
    const refusal = await screen.findByTestId("bring-refusal");
    expect(refusal).toHaveTextContent(code);
    expect(screen.queryByTestId("bring-validate")).not.toBeInTheDocument();
    expect(workflowCalls(fetchMock).filter((p) => p.includes("/workflows/"))).toEqual([]);
  });

  it("reads a local JSON file in the browser and gates it like pasted text", async () => {
    installFetchMock();
    const user = userEvent.setup();
    renderWithProviders(<App />, ROUTE);
    const input = (await screen.findByTestId("bring-file")) as HTMLInputElement;
    const file = new File([v1Text], "procurement.workflow-ir.json", { type: "application/json" });
    await user.upload(input, file);
    const summary = await screen.findByTestId("bring-summary");
    expect(within(summary).getByTestId("bring-node-count")).toHaveTextContent("9");
    expect(screen.getByText(/read locally; nothing was uploaded/)).toBeInTheDocument();
  });
});

describe("BW-3 — validate, adapt and compare, and nothing else", () => {
  it("validate posts the document with its declared version and client digest, and shows the server's answer", async () => {
    const fetchMock = installFetchMock();
    const user = userEvent.setup();
    renderWithProviders(<App />, ROUTE);
    await user.click(await screen.findByTestId("bring-load-example"));
    await screen.findByTestId("bring-summary");
    await waitFor(() => expect(screen.getByTestId("bring-validate")).toBeEnabled());
    await user.click(screen.getByTestId("bring-validate"));
    const result = await screen.findByTestId("bring-validation-result");
    expect(within(result).getByTestId("bring-validation-state")).toHaveTextContent("VALID");
    const body = lastBody(fetchMock, "/api/v1/workflows/validate");
    expect(body.contract_version).toBe("workflow_ir.v1");
    expect(body.workflow).toEqual(exampleV1);
    expect(Object.keys(body).sort()).toEqual(["contract_version", "source_digest", "workflow"]);
    expect(String(body.source_digest)).toMatch(/^sha256:[0-9a-f]{64}$/);
    expect(within(result).getByTestId("bring-integrity")).toHaveTextContent("match");
  });

  it("adapt shows the adapter mode, every node disposition and every role requirement the server returned", async () => {
    const fetchMock = installFetchMock();
    const user = userEvent.setup();
    renderWithProviders(<App />, ROUTE);
    await user.click(await screen.findByTestId("bring-load-example"));
    await screen.findByTestId("bring-summary");
    await user.click(screen.getByTestId("bring-adapt"));
    const result = await screen.findByTestId("bring-adaptation-result");
    expect(within(result).getByTestId("bring-adapter-mode")).toHaveTextContent(adaptFixture.adapter_mode);
    expect(within(result).getAllByRole("row")).toHaveLength(adaptFixture.node_dispositions.length + 1);
    for (const role of adaptFixture.role_requirements) expect(within(result).getAllByText(role.role_id).length).toBeGreaterThan(0);
    const body = lastBody(fetchMock, "/api/v1/workflows/adapt");
    expect(Object.keys(body).sort()).toEqual(["contract_version", "workflow"]);
  });

  it("compare needs one v1 and one v2 document, sends both, and shows the equivalence state", async () => {
    const fetchMock = installFetchMock();
    const user = userEvent.setup();
    renderWithProviders(<App />, ROUTE);
    await user.click(await screen.findByTestId("bring-load-example"));
    await screen.findByTestId("bring-summary");
    expect(screen.getByTestId("bring-compare")).toBeDisabled();
    await paste(user, "bring-second-text", v1Text);
    expect(await screen.findByTestId("bring-compare-note")).toHaveTextContent("both declare workflow_ir.v1");
    expect(screen.getByTestId("bring-compare")).toBeDisabled();
    await paste(user, "bring-second-text", v2Text);
    await waitFor(() => expect(screen.getByTestId("bring-compare")).toBeEnabled());
    await user.click(screen.getByTestId("bring-compare"));
    const result = await screen.findByTestId("bring-comparison-result");
    expect(within(result).getByTestId("bring-equivalence-state")).toHaveTextContent("SEMANTICALLY_EQUIVALENT");
    const body = lastBody(fetchMock, "/compare-adaptations");
    expect(Object.keys(body).sort()).toEqual(["v1_workflow", "v2_workflow"]);
    expect(body.v1_workflow).toEqual(exampleV1);
    expect(body.v2_workflow).toEqual(exampleV2);
  });

  it("a server refusal is shown with its typed code, never swallowed", async () => {
    installFetchMock({ workflowTooComplex: true });
    const user = userEvent.setup();
    renderWithProviders(<App />, ROUTE);
    await user.click(await screen.findByTestId("bring-load-example"));
    await screen.findByTestId("bring-summary");
    await user.click(screen.getByTestId("bring-adapt"));
    expect(await screen.findByTestId("bring-server-refusal")).toHaveTextContent("workflow_too_complex");
    expect(screen.queryByTestId("bring-adaptation-result")).not.toBeInTheDocument();
  });

  it("only the three workflow operations are ever reached, and editing the document clears every result", async () => {
    const fetchMock = installFetchMock();
    const user = userEvent.setup();
    renderWithProviders(<App />, ROUTE);
    await user.click(await screen.findByTestId("bring-load-example"));
    await screen.findByTestId("bring-summary");
    await user.click(screen.getByTestId("bring-validate"));
    await screen.findByTestId("bring-validation-result");
    await user.click(screen.getByTestId("bring-adapt"));
    await screen.findByTestId("bring-adaptation-result");
    const reached = new Set(workflowCalls(fetchMock));
    expect([...reached].sort()).toEqual(["/api/v1/workflows/adapt", "/api/v1/workflows/validate"]);
    await user.click(screen.getByTestId("bring-clear"));
    expect(screen.queryByTestId("bring-validation-result")).not.toBeInTheDocument();
    expect(screen.queryByTestId("bring-adaptation-result")).not.toBeInTheDocument();
    expect(screen.queryByTestId("bring-summary")).not.toBeInTheDocument();
  });
});

describe("BW-4 — ephemeral, and the local download is the server's own record", () => {
  it("the report carries the request ids and results as returned; the envelope is the adaptation envelope", async () => {
    installFetchMock();
    const user = userEvent.setup();
    renderWithProviders(<App />, ROUTE);
    await user.click(await screen.findByTestId("bring-load-example"));
    await screen.findByTestId("bring-summary");
    await user.click(screen.getByTestId("bring-validate"));
    await screen.findByTestId("bring-validation-result");
    await user.click(screen.getByTestId("bring-adapt"));
    await screen.findByTestId("bring-adaptation-result");
    await user.click(screen.getByTestId("bring-download-report"));
    await user.click(screen.getByTestId("bring-download-envelope"));
    await waitFor(() => expect(downloads.filter((d) => d.text).length).toBe(2));
    expect(downloads.map((d) => d.name)).toEqual(["ugence-bring-your-workflow-report.json", "ugence-adapted-workflow-envelope.json"]);
    const report = JSON.parse(downloads[0].text);
    expect(report.schema).toBe("governance_studio.bring-your-workflow.report.v1");
    expect(report.disclaimer).toBe(DISCLAIMER);
    expect(report.validate.request_id).toBe("req_test");
    expect(report.adapt.result.adaptation_fingerprint).toBe(adaptFixture.adaptation_fingerprint);
    expect(report.compare).toBeNull();
    expect(report.input.declared_contract_version).toBe("workflow_ir.v1");
    expect(report.input.summary.nodeCount).toBe(9);
    expect(JSON.parse(downloads[1].text)).toEqual(adaptFixture.adaptation_envelope);
  });

  it("the screen's source touches no browser storage, opens no connection and names no forbidden operation", () => {
    const dir = path.join(FRONTEND, "src", "features", "bring");
    const sources = readdirSync(dir).filter((f) => /\.(ts|tsx)$/.test(f));
    expect(sources.sort()).toEqual(["BringYourWorkflowScreen.tsx", "gate.ts"]);
    for (const f of sources) {
      const text = readFileSync(path.join(dir, f), "utf-8");
      for (const banned of ["localStorage", "sessionStorage", "indexedDB", "fetch(", "XMLHttpRequest", "WebSocket", "eval(", "new Function", "/api/v2/", "/scenarios"]) {
        expect(text, `${f} contains ${banned}`).not.toContain(banned);
      }
    }
    const manifest = JSON.parse(readFileSync(path.join(FRONTEND, "security", "approved-api-operations.json"), "utf-8"));
    for (const id of ["validate_workflow", "adapt_workflow", "compare_adaptations"]) {
      expect(manifest.approved_operation_ids).toContain(id);
      expect(manifest.forbidden_operation_ids).not.toContain(id);
    }
    // the three internal planning operations stay forbidden; named by count, not by
    // literal, so this file needs no negative-fixture exemption from the verifier
    expect(manifest.forbidden_operation_ids).toHaveLength(3);
    expect(manifest.forbidden_paths).toHaveLength(3);
  });
});
