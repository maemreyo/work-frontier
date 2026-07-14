import test from "node:test"
import assert from "node:assert/strict"
import { readFile } from "node:fs/promises"

test("Control Room keeps Setup Center available after onboarding", async () => {
  const app = await readFile(new URL("../../src/control-room/app.tsx", import.meta.url), "utf8")
  const shell = await readFile(new URL("../../src/control-room/shell.tsx", import.meta.url), "utf8")
  assert.match(app, /<SetupCenter/)
  assert.doesNotMatch(app, /reduceOnboarding|isAuthoritative/)
  assert.match(shell, /"setup"/)
  assert.match(shell, /label: "Setup"/)
})
