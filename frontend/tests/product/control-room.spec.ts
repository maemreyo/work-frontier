import AxeBuilder from "@axe-core/playwright"
import { expect, test } from "@playwright/test"

const viewports = [
  { width: 320, height: 800 },
  { width: 768, height: 900 },
  { width: 1280, height: 900 },
  { width: 1920, height: 1080 },
] as const

for (const viewport of viewports) {
  test(`Builder lands with recommended decisions at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport)
    await page.goto("/")
    await expect(page.getByRole("heading", { name: "Recommended Next" })).toBeVisible()
    await expect(page.getByRole("heading", { name: "Stabilize the release foundation" }).first()).toBeVisible()
    const results = await new AxeBuilder({ page }).analyze()
    expect(results.violations).toEqual([])
    const screenshot = await page.screenshot({ fullPage: true })
    expect(screenshot.byteLength).toBeGreaterThan(1000)
  })
}

test("Builder keyboard flow exposes decision type and claim conflict", async ({ page }) => {
  await page.goto("/")
  await expect(page.getByText("Decision type:").first()).toBeVisible()
  const claimButtons = page.getByRole("button", { name: "Claim" })
  await claimButtons.nth(0).focus()
  await page.keyboard.press("Enter")
  await expect(page.getByRole("status").first()).toContainText("Claimed")
  await claimButtons.nth(1).click()
  await expect(page.getByRole("status").first()).toContainText("Claim conflict")
  await page.getByRole("button", { name: "Open decision detail" }).first().click()
  await expect(page.getByRole("status").first()).toContainText("Opened decision-foundation")
})
