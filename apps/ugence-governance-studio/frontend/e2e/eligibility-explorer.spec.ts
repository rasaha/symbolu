import { test, expect, type Page } from "@playwright/test";

// Direct browser E2E for ALL FOUR scenarios (§C1), run against the REAL local P3B
// backend with the live frozen scenario data. No mocked eligibility, no test-only
// domain logic. Deterministic selectors (test ids + exact nav names + row filters).

const MATURITY = /no business-action authorization/i;

async function openScenario(page: Page, id: string) {
  await page.goto("/scenarios");
  await expect(page.getByRole("heading", { name: /scenario catalog/i })).toBeVisible();
  await expect(page.getByText(MATURITY).first()).toBeVisible();
  await page.getByTestId(`open-${id}`).click();
  await expect(page.getByTestId("verification-state")).toBeVisible();
}

test("Procurement — guided full flow", async ({ page }) => {
  await openScenario(page, "procurement");

  // inspect workflow + select an AI-agent role
  await page.getByRole("link", { name: "Workflow", exact: true }).click();
  const list = page.getByRole("region", { name: /accessible list/i });
  await expect(list).toBeVisible();
  await list.getByRole("button").filter({ hasText: "AI-agent role" }).first().click();
  await page.getByRole("link", { name: /view role requirements/i }).click();

  // inspect role requirements + fingerprint
  await expect(page.getByRole("heading", { level: 3, name: /identity/i })).toBeVisible();
  await expect(page.getByText(/functional requirements/i)).toBeVisible();
  await expect(page.getByText(/role fingerprint/i)).toBeVisible();

  // inspect registry
  await page.getByRole("link", { name: "Registry", exact: true }).click();
  await expect(page.getByRole("heading", { name: /agent registry/i })).toBeVisible();
  await expect(page.getByText(/DECLARED evidence/i).first()).toBeVisible();

  // eligibility matrix → select an INELIGIBLE agent → reasons/evidence/fingerprints
  await page.getByRole("link", { name: "Eligibility", exact: true }).click();
  await expect(page.getByRole("table")).toBeVisible();
  const ineligibleRow = page.getByRole("row").filter({ hasText: "Ineligible" }).first();
  await ineligibleRow.getByRole("button", { name: "Explain" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText(/failed conditions/i)).toBeVisible();
  await expect(dialog.getByText(/elimination reasons/i)).toBeVisible();
  await expect(dialog.getByText(/evidence & policy/i)).toBeVisible();
  await expect(dialog.getByText(/result fingerprint/i)).toBeVisible();
  await dialog.getByRole("button", { name: /close explanation/i }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // persistent maturity language
  await expect(page.getByText(MATURITY).first()).toBeVisible();
});

test("Customer Support — direct smoke flow", async ({ page }) => {
  await openScenario(page, "customer_support");
  await expect(page.getByRole("heading", { name: /customer support/i })).toBeVisible();

  // workflow loads; node accounting ties the header count to the accessible list
  await page.getByRole("link", { name: "Workflow", exact: true }).click();
  const header = page.getByText(/\d+ nodes · \d+ edges/);
  await expect(header).toBeVisible();
  const headerText = (await header.textContent()) ?? "";
  const nodeCount = Number(headerText.match(/(\d+) nodes/)?.[1] ?? "0");
  expect(nodeCount).toBeGreaterThan(0);
  const listButtons = page.getByRole("region", { name: /accessible list/i }).getByRole("button");
  await expect(listButtons).toHaveCount(nodeCount);

  // eligibility rows exist; open one explanation
  await page.getByRole("link", { name: "Eligibility", exact: true }).click();
  await expect(page.getByRole("table")).toBeVisible();
  const rows = page.getByRole("row");
  expect(await rows.count()).toBeGreaterThan(1);
  await page.getByRole("button", { name: "Explain" }).first().click();
  const dialog = page.getByRole("dialog");
  // evidence/policy references OR explicit empty state ("None")
  await expect(dialog.getByText(/evidence & policy/i)).toBeVisible();
  await dialog.getByRole("button", { name: /close explanation/i }).click();

  // synthetic + maturity labels
  await page.getByRole("link", { name: "Registry", exact: true }).click();
  await expect(page.getByText(/synthetic/i).first()).toBeVisible();
  await expect(page.getByText(MATURITY).first()).toBeVisible();
});

test("Cybersecurity — Feasible", async ({ page }) => {
  await openScenario(page, "cybersecurity_success");
  await expect(page.getByRole("heading", { name: /cybersecurity/i })).toBeVisible();
  // feasible/complete context: verification present on overview
  await expect(page.getByTestId("verification-state")).toBeVisible();

  // workflow node accounting
  await page.getByRole("link", { name: "Workflow", exact: true }).click();
  await expect(page.getByRole("region", { name: /accessible list/i }).getByRole("button").first()).toBeVisible();

  // complete role-agent accounting; eligible + ineligible explanations
  await page.getByRole("link", { name: "Eligibility", exact: true }).click();
  await expect(page.getByRole("table")).toBeVisible();

  const eligibleRow = page.getByRole("row").filter({ hasText: /\bEligible\b/ }).first();
  await eligibleRow.getByRole("button", { name: "Explain" }).click();
  let dialog = page.getByRole("dialog");
  await expect(dialog.getByText(/passed conditions/i)).toBeVisible();
  // states are not described as ranking or assignment
  await expect(dialog.getByText(/\b(rank|ranked|assigned|selected)\b/i)).toHaveCount(0);
  await dialog.getByRole("button", { name: /close explanation/i }).click();

  const ineligibleRow = page.getByRole("row").filter({ hasText: "Ineligible" }).first();
  await ineligibleRow.getByRole("button", { name: "Explain" }).click();
  dialog = page.getByRole("dialog");
  await expect(dialog.getByText(/failed conditions/i)).toBeVisible();
  await dialog.getByRole("button", { name: /close explanation/i }).click();

  await expect(page.getByText(MATURITY).first()).toBeVisible();
});

test("Cybersecurity — No Feasible Team renders honestly", async ({ page }) => {
  await openScenario(page, "cybersecurity_no_feasible_team");

  await page.getByRole("link", { name: "Eligibility", exact: true }).click();
  await expect(page.getByRole("table")).toBeVisible();
  // eligibility failures are visible; not an empty-success rendering
  await expect(page.getByText(/Ineligible/).first()).toBeVisible();
  // no preferred-agent or assignment language, and infeasibility is not an app error
  await expect(
    page.getByText(/recommended agent|preferred agent|best agent|assigned agent|agent selected/i),
  ).toHaveCount(0);
  await expect(page.getByText(/unexpected error|request failed|backend unavailable/i)).toHaveCount(0);

  await expect(page.getByText(MATURITY).first()).toBeVisible();
});
