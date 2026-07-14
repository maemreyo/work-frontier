export class SetupApi {
  constructor({
    fetchImpl = globalThis.fetch.bind(globalThis),
    location = globalThis.location,
    history = globalThis.history,
    basePath = "/api/setup",
    defaultHeaders = {},
  } = {}) {
    this.fetchImpl = fetchImpl
    this.location = location
    this.history = history
    this.basePath = basePath
    this.defaultHeaders = { ...defaultHeaders }
    this.csrfToken = null
  }

  async exchangeBootstrapToken() {
    const token = this.location.hash?.replace(/^#/, "") ?? ""
    if (!token) return false
    const response = await this.fetchImpl(`${this.basePath}/session/exchange`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ token }),
    })
    if (!response.ok) throw await this.#error(response)
    this.csrfToken = response.headers.get("X-Setup-CSRF")
    this.history.replaceState(null, "", `${this.location.pathname}${this.location.search ?? ""}`)
    return true
  }

  status(profile = "development") {
    return this.#request(`/status?profile=${encodeURIComponent(profile)}`)
  }

  detect(profile) {
    return this.#request("/detect", { profile })
  }

  plan({ profile, desired, expectedSnapshotId }) {
    return this.#request("/plan", {
      profile,
      desired,
      expected_snapshot_id: expectedSnapshotId,
    })
  }

  apply(planId) {
    return this.#request("/apply", { plan_id: planId })
  }

  resume(sessionId) {
    return this.#request(`/resume/${encodeURIComponent(sessionId)}`, {})
  }

  generateSigningKey(request) {
    return this.#request("/signing-key", request)
  }

  async storeSecret(secret) {
    return this.#request("/secrets", secret)
  }

  async close() {
    return this.#request("/session/close", {})
  }

  async #request(path, body) {
    const options = {
      credentials: "same-origin",
      headers: { ...this.defaultHeaders, accept: "application/json" },
    }
    if (body !== undefined) {
      options.method = "POST"
      options.headers["content-type"] = "application/json"
      if (this.csrfToken) options.headers["X-Setup-CSRF"] = this.csrfToken
      options.body = JSON.stringify(body)
    }
    const response = await this.fetchImpl(`${this.basePath}${path}`, options)
    if (!response.ok) throw await this.#error(response)
    if (response.status === 204) return null
    return response.json()
  }

  async #error(response) {
    let detail = `Setup request failed (${response.status})`
    try {
      const payload = await response.json()
      detail = payload?.detail ?? payload?.error?.message ?? detail
    } catch {
      // Keep the status-only error; response bodies may be empty.
    }
    return new Error(detail)
  }
}
