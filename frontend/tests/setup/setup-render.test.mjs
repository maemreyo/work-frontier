import test from "node:test"
import assert from "node:assert/strict"

import { renderSetupCenter } from "../../src/setup/setup-center-element.js"

test("renders four independent capability cards", () => {
  const html = renderSetupCenter({
    profile: "development",
    step: "status",
    busy: false,
    message: "Ready",
    desired: { github_repository: "" },
    envelope: {
      capabilities: [
        { capability: "local_runtime", state: "ready", reason: "Runtime verified", impact: "Can run", next_actions: [], supporting_check_ids: [] },
        { capability: "github_integration", state: "needs_input", reason: "Choose repository", impact: "No sync", next_actions: ["Choose repository"], supporting_check_ids: [] },
        { capability: "release_certification", state: "not_required", reason: "Optional", impact: "No release", next_actions: [], supporting_check_ids: [] },
        { capability: "production_cutover", state: "not_required", reason: "Optional", impact: "No cutover", next_actions: [], supporting_check_ids: [] },
      ],
      detection: null,
      plan: null,
      results: [],
    },
  })
  for (const label of ["Local runtime", "GitHub integration", "Release certification", "Production cutover"]) {
    assert.match(html, new RegExp(label))
  }
  assert.match(html, /aria-live="polite"/)
})

test("rendered state never contains a submitted secret", () => {
  const html = renderSetupCenter({
    profile: "production",
    step: "secrets",
    busy: false,
    message: "Stored keyring://work-frontier/release/signing-key",
    desired: { github_repository: "acme/sandbox" },
    envelope: { capabilities: [], detection: null, plan: null, results: [] },
  })
  assert.equal(html.includes("private-value"), false)
  assert.match(html, /type="password"/)
})

test("offers resume when a durable session exists", () => {
  const html = renderSetupCenter({
    profile: "development",
    step: "execution",
    busy: false,
    message: "Setup interrupted",
    desired: { github_repository: "acme/sandbox" },
    envelope: {
      session_id: "session-1",
      capabilities: [],
      detection: null,
      plan: null,
      results: [{ action_id: "database.migrate", state: "failed", message: "Interrupted" }],
    },
  })
  assert.match(html, /data-action="resume"/)
  assert.match(html, /Resume interrupted setup/)
})

test("production profile offers release signing key generation", () => {
  const html = renderSetupCenter({
    profile: "production",
    step: "secrets",
    busy: false,
    message: "Ready",
    desired: { github_repository: "acme/managed" },
    envelope: { capabilities: [], detection: null, plan: null, results: [] },
  })
  assert.match(html, /data-action="generate-signing-key"/)
  assert.match(html, /Generate Ed25519 signing key/)
})

test("production profile exposes GitHub App external services release and cutover fields", () => {
  const html = renderSetupCenter({
    profile: "production",
    step: "profile",
    busy: false,
    message: "Ready",
    desired: { github_repository: "" },
    envelope: { capabilities: [], detection: null, plan: null, results: [] },
  })
  for (const field of [
    "github_app_id",
    "github_installation_id",
    "github_app_credential_reference",
    "database_endpoint",
    "object_storage_endpoint",
    "prepare_release",
    "release_sandbox_repository",
    "prepare_cutover",
    "cutover_approval_id",
    "cutover_source_revision",
  ]) {
    assert.match(html, new RegExp(`data-desired="${field}"`))
  }
})
