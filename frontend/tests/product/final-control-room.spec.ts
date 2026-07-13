import AxeBuilder from "@axe-core/playwright"
import { expect, test } from "@playwright/test"

async function onboard(page: import("@playwright/test").Page) {
  await page.goto("/")
  await page.getByRole("button", { name: "Connect installation" }).click()
  await page.getByRole("button", { name: "Validate profile" }).click()
  await page.getByRole("button", {
    name: "Reconcile authoritative state",
  }).click()
}

test("coordinator approval and stale/self approval rules are visible", async ({
  page,
}, testInfo) => {
  await onboard(page)
  await page.getByRole("button", { name: "Coordinator" }).click()
  await expect(page.getByRole("heading", { name: "Coordinator proposals" })).toBeVisible()
  const independentApproval = page.getByRole("button", { name: "Approve" }).first()
  await expect(independentApproval).toBeEnabled()
  await expect(page.getByRole("button", { name: "Approve" }).last()).toBeDisabled()
  await independentApproval.click()
  await expect(page.getByText("frontier recomputed")).toBeVisible()
  await page.getByRole("button", { name: "Builder" }).click()
  await expect(page.getByRole("heading", { name: "Publish stale projection" })).toBeVisible()
  await testInfo.attach("coordinator-approved-builder", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  })
})

test("executive and operator views expose role-safe information", async ({ page }, testInfo) => {
  await onboard(page)
  await page.getByRole("button", { name: "Executive" }).click()
  await expect(page.getByText("authoritative; rev-4").first()).toBeVisible()
  await page.getByRole("button", { name: "Operator" }).click()
  await expect(page.getByText("[REDACTED]")).toBeVisible()
  await expect(page.getByText("must-not-render")).toHaveCount(0)
  await testInfo.attach("operator-redacted", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  })
})

for (const width of [320, 768, 1280, 1920]) {
  test(`has no serious axe violations at ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 })
    await onboard(page)
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
      .analyze()
    expect(results.violations).toEqual([])
    await testInfo.attach(`builder-${width}px-five-decision-types`, {
      body: await page.screenshot({ fullPage: true }),
      contentType: "image/png",
    })
  })
}
