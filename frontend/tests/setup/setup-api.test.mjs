import test from "node:test"
import assert from "node:assert/strict"

import { SetupApi } from "../../src/setup/setup-api.js"

test("bootstrap token is exchanged once and removed from the URL", async () => {
  const calls = []
  const history = { replaced: null, replaceState(_state, _title, url) { this.replaced = url } }
  const api = new SetupApi({
    fetchImpl: async (url, options) => {
      calls.push({ url, options })
      return new Response(null, { status: 204, headers: { "X-Setup-CSRF": "csrf-1" } })
    },
    location: { hash: "#bootstrap-token", pathname: "/setup.html", search: "" },
    history,
  })

  await api.exchangeBootstrapToken()

  assert.equal(calls.length, 1)
  assert.equal(JSON.parse(calls[0].options.body).token, "bootstrap-token")
  assert.equal(history.replaced, "/setup.html")
  assert.equal(api.csrfToken, "csrf-1")
})

test("secret storage sends value only in request and returns reference", async () => {
  let capturedBody = ""
  const api = new SetupApi({
    fetchImpl: async (_url, options) => {
      capturedBody = options.body
      return new Response(JSON.stringify({ reference: "keyring://work-frontier/release/signing-key" }), {
        status: 201,
        headers: { "content-type": "application/json" },
      })
    },
    location: { hash: "", pathname: "/setup.html", search: "" },
    history: { replaceState() {} },
  })
  api.csrfToken = "csrf"

  const result = await api.storeSecret({ namespace: "release", name: "signing-key", value: "private-value" })

  assert.equal(result.reference, "keyring://work-frontier/release/signing-key")
  assert.match(capturedBody, /private-value/)
  assert.equal(JSON.stringify(result).includes("private-value"), false)
})

test("persistent requests include injected authenticated session headers", async () => {
  let captured
  const api = new SetupApi({
    fetchImpl: async (_url, options) => {
      captured = options.headers
      return new Response(JSON.stringify({ capabilities: [], detection: null, plan: null, results: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    },
    location: { hash: "", pathname: "/", search: "" },
    history: { replaceState() {} },
    defaultHeaders: { Authorization: "Bearer session-good", "X-Actor-Role": "operator" },
  })
  await api.status()
  assert.equal(captured.Authorization, "Bearer session-good")
  assert.equal(captured["X-Actor-Role"], "operator")
})

test("resume posts to the durable session endpoint", async () => {
  let capturedUrl = ""
  let capturedMethod = ""
  const api = new SetupApi({
    fetchImpl: async (url, options) => {
      capturedUrl = url
      capturedMethod = options.method
      return new Response(JSON.stringify({ session_id: "session-1", capabilities: [], results: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    },
    location: { hash: "", pathname: "/setup.html", search: "" },
    history: { replaceState() {} },
  })
  api.csrfToken = "csrf"

  const result = await api.resume("session-1")

  assert.equal(capturedUrl, "/api/setup/resume/session-1")
  assert.equal(capturedMethod, "POST")
  assert.equal(result.session_id, "session-1")
})

test("signing key generation returns public material only", async () => {
  let requestBody = ""
  const api = new SetupApi({
    fetchImpl: async (_url, options) => {
      requestBody = options.body
      return new Response(JSON.stringify({
        reference: "keyring://work-frontier/release/standard-signing-key",
        key_id: "work-frontier-standard-2026-01",
        public_key_b64: "public-key",
        fingerprint: "a".repeat(64),
      }), {
        status: 201,
        headers: { "content-type": "application/json" },
      })
    },
    location: { hash: "", pathname: "/setup.html", search: "" },
    history: { replaceState() {} },
  })
  api.csrfToken = "csrf"

  const result = await api.generateSigningKey({
    namespace: "release",
    name: "standard-signing-key",
    key_id: "work-frontier-standard-2026-01",
  })

  assert.equal(result.public_key_b64, "public-key")
  assert.equal(JSON.stringify(result).includes("private"), false)
  assert.equal(requestBody.includes("private"), false)
})
