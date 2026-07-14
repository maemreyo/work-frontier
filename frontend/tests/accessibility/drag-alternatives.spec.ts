import { expect, test } from "@playwright/test"

test("dependency interaction has a non-drag table alternative", async ({ page }) => {
  await page.goto("/")
  await page.getByRole("button", { name: "Coordinator" }).click()
  await expect(
    page.getByRole("table", {
      name: "Keyboard-accessible dependency repair alternative",
    }),
  ).toBeVisible()
})
