import { expect, test } from "@playwright/test"

test("all primary workflows are reachable by keyboard", async ({ page }) => {
  await page.goto("/")
  await page.keyboard.press("Tab")
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused()
  await page.keyboard.press("Tab")
  await expect(page.getByRole("button", { name: "Builder" })).toBeFocused()
})
