import { test, expect } from "@playwright/test";

// Core demo flow (§29) against the real backend: catalog → workflow → role →
// registry → eligibility → eliminated agent → reasons/evidence → maturity labels.
test("Procurement end-to-end eligibility flow", async ({ page }) => {
  await page.goto("/scenarios");
  await expect(page.getByRole("heading", { name: /scenario catalog/i })).toBeVisible();
  // maturity labels are prominent in the chrome
  await expect(page.getByText(/no business-action authorization/i).first()).toBeVisible();

  await page.getByTestId("open-procurement").click();
  await expect(page.getByTestId("verification-state")).toBeVisible();

  await page.getByRole("link", { name: "Workflow", exact: true }).click();
  await expect(page.getByRole("region", { name: /accessible list/i })).toBeVisible();

  await page.getByRole("link", { name: "Eligibility", exact: true }).click();
  await expect(page.getByRole("table")).toBeVisible();

  // open an explanation and confirm reasons + fingerprints render
  await page.getByRole("button", { name: /^Explain$/ }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText(/failed conditions/i)).toBeVisible();
  await expect(dialog.getByText(/result fingerprint/i)).toBeVisible();
  await dialog.getByRole("button", { name: /close explanation/i }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);

  // registry with synthetic evidence labels
  await page.getByRole("link", { name: "Registry", exact: true }).click();
  await expect(page.getByRole("heading", { name: /agent registry/i })).toBeVisible();
  await expect(page.getByText(/DECLARED evidence/i).first()).toBeVisible();
});

test("Cybersecurity no-feasible-team renders honestly", async ({ page }) => {
  await page.goto("/scenarios/cybersecurity_no_feasible_team/eligibility");
  await expect(page.getByRole("table")).toBeVisible();
  // at least one ineligible agent is shown for the infeasible scenario
  await expect(page.getByText(/Ineligible/).first()).toBeVisible();
});
