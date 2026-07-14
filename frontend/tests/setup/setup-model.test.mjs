import test from "node:test"
import assert from "node:assert/strict"

import {
  capabilityLabel,
  groupPlanActions,
  removeSecretValue,
  setupStateMessage,
} from "../../src/setup/setup-model.js"

test("capability labels remain independent and readable", () => {
  assert.equal(capabilityLabel("local_runtime"), "Local runtime")
  assert.equal(capabilityLabel("github_integration"), "GitHub integration")
  assert.equal(capabilityLabel("release_certification"), "Release certification")
  assert.equal(capabilityLabel("production_cutover"), "Production cutover")
})

test("plan actions are grouped by concrete effect", () => {
  const groups = groupPlanActions([
    { action_id: "config.write", kind: "write_config", title: "Write config" },
    { action_id: "services.local.start", kind: "docker_compose_up", title: "Start services" },
    { action_id: "checks.fast", kind: "run_fast_checks", title: "Run checks" },
  ])
  assert.deepEqual(groups.create.map((item) => item.action_id), ["config.write"])
  assert.deepEqual(groups.start.map((item) => item.action_id), ["services.local.start"])
  assert.deepEqual(groups.run.map((item) => item.action_id), ["checks.fast"])
})

test("secret fields are cleared after secure storage", () => {
  const form = { namespace: "release", name: "signing-key", value: "private-value" }
  assert.deepEqual(removeSecretValue(form), {
    namespace: "release",
    name: "signing-key",
    value: "",
  })
  assert.equal(JSON.stringify(removeSecretValue(form)).includes("private-value"), false)
})

test("state message explains blocked status", () => {
  assert.equal(
    setupStateMessage("blocked"),
    "Blocked — resolve the required safety or dependency issue before continuing.",
  )
})
