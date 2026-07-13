import AxeBuilder from "@axe-core/playwright"
import { expect, test } from "@playwright/test"

test("Control Room meets automated WCAG 2.2 AA checks", async ({ page }, testInfo) => {
  await page.goto("/")
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag22aa"])
    .analyze()
  expect(results.violations).toEqual([])
  await testInfo.attach("wcag-22-aa", {
    body: await page.screenshot({ fullPage: true }),
    contentType: "image/png",
  })
})
