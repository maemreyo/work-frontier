import { expect, test } from "@playwright/test"

test("focus indicator has visible outline", async ({ page }) => {
  await page.goto("/")
  await page.getByRole("button", { name: "Connect installation" }).focus()
  const outline = await page
    .getByRole("button", { name: "Connect installation" })
    .evaluate((element: HTMLElement) => getComputedStyle(element).outlineWidth)
  expect(Number.parseFloat(outline)).toBeGreaterThanOrEqual(3)
})
