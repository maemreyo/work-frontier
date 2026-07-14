import { SetupApi } from "./setup-api.js"
import {
  capabilityLabel,
  escapeHtml,
  groupPlanActions,
  removeSecretValue,
  setupStateMessage,
} from "./setup-model.js"

const EMPTY_ENVELOPE = Object.freeze({
  detection: null,
  plan: null,
  capabilities: [],
  results: [],
})

export function renderSetupCenter(state) {
  const envelope = state.envelope ?? EMPTY_ENVELOPE
  const capabilities = envelope.capabilities ?? []
  const checks = envelope.detection?.checks ?? []
  const actions = envelope.plan?.actions ?? []
  const groups = groupPlanActions(actions)
  const disabled = state.busy ? " disabled" : ""
  const isProduction = state.profile === "production"

  return `
    <section class="wf-setup" aria-labelledby="wf-setup-heading">
      <header class="wf-setup__header">
        <div>
          <p class="wf-eyebrow">Persistent Setup Center</p>
          <h1 id="wf-setup-heading">Configure Work Frontier</h1>
          <p>Detect the current environment, review every effect, then apply a resumable plan.</p>
        </div>
        <button type="button" data-action="refresh"${disabled}>Refresh status</button>
      </header>

      <output class="wf-setup__status" aria-live="polite">${escapeHtml(state.message ?? "Ready")}</output>

      <section aria-labelledby="wf-profile-heading" class="wf-setup__panel">
        <h2 id="wf-profile-heading">1. Choose profile</h2>
        <label>
          Setup profile
          <select data-field="profile"${disabled}>
            <option value="development"${state.profile === "development" ? " selected" : ""}>Development</option>
            <option value="production"${isProduction ? " selected" : ""}>Production / self-hosted</option>
          </select>
        </label>
        <p>${isProduction
          ? "Production requires external services, GitHub App machine identity, and explicit release/cutover preparation."
          : "Development keeps release signing and production cutover optional."}</p>
      </section>

      <section aria-labelledby="wf-capability-heading" class="wf-setup__panel">
        <h2 id="wf-capability-heading">Capability readiness</h2>
        <div class="wf-setup__capabilities">
          ${capabilities.length > 0
            ? capabilities.map(renderCapability).join("")
            : renderCapabilityPlaceholders(state.profile)}
        </div>
      </section>

      <section aria-labelledby="wf-detect-heading" class="wf-setup__panel">
        <h2 id="wf-detect-heading">2. Detect environment</h2>
        <button type="button" data-action="detect"${disabled}>Run read-only detection</button>
        ${checks.length > 0 ? `<div class="wf-setup__checks">${checks.map(renderCheck).join("")}</div>` : ""}
      </section>

      <section aria-labelledby="wf-github-heading" class="wf-setup__panel">
        <h2 id="wf-github-heading">3. Configure GitHub</h2>
        <label>
          ${isProduction ? "Managed repository" : "Sandbox repository"}
          <input data-field="github_repository" value="${escapeHtml(state.desired?.github_repository ?? "")}" placeholder="owner/repository" autocomplete="off"${disabled}>
        </label>
        <p>${isProduction
          ? "Machine identity uses a GitHub App. Human OAuth/OIDC remains a separate approval identity."
          : "The preferred credential is your existing GitHub CLI login; Work Frontier stores only a gh-cli:// reference."}</p>
        ${isProduction ? renderProductionConfiguration(state.desired ?? {}, disabled) : ""}
      </section>

      <section aria-labelledby="wf-secret-heading" class="wf-setup__panel">
        <h2 id="wf-secret-heading">4. Store a secret reference</h2>
        <form data-form="secret">
          <label>Namespace <input name="namespace" value="release" required${disabled}></label>
          <label>Name <input name="name" value="signing-key" required${disabled}></label>
          <label>Secret value <input name="value" type="password" autocomplete="new-password" required${disabled}></label>
          <button type="submit"${disabled}>Store securely</button>
        </form>
        <p>Plaintext is sent once to the loopback backend, stored by the selected provider, cleared from the form, and never written to normal configuration.</p>
        ${isProduction ? `<button type="button" data-action="generate-signing-key"${disabled}>Generate Ed25519 signing key</button>` : ""}
        ${state.signingKey ? `<dl class="wf-setup__key"><dt>Key ID</dt><dd>${escapeHtml(state.signingKey.key_id)}</dd><dt>Public fingerprint</dt><dd>${escapeHtml(state.signingKey.fingerprint)}</dd><dt>Secret reference</dt><dd>${escapeHtml(state.signingKey.reference)}</dd></dl>` : ""}
      </section>

      <section aria-labelledby="wf-review-heading" class="wf-setup__panel">
        <h2 id="wf-review-heading">5. Review plan</h2>
        <button type="button" data-action="plan"${disabled || !envelope.detection ? " disabled" : ""}>Create reviewed plan</button>
        ${envelope.plan ? renderPlan(envelope.plan, groups) : "<p>No plan yet. Detection must be current before planning.</p>"}
      </section>

      <section aria-labelledby="wf-apply-heading" class="wf-setup__panel">
        <h2 id="wf-apply-heading">6. Apply and verify</h2>
        <button type="button" data-action="apply"${disabled || !envelope.plan ? " disabled" : ""}>Apply reviewed plan</button>
        ${envelope.session_id ? `<button type="button" data-action="resume"${disabled}>Resume interrupted setup</button>` : ""}
        ${(envelope.results ?? []).length > 0
          ? `<ol class="wf-setup__results">${envelope.results.map(renderResult).join("")}</ol>`
          : "<p>Execution is journaled. Closing the browser does not erase progress.</p>"}
      </section>
    </section>`
}


function renderProductionConfiguration(desired, disabled) {
  const value = (name) => escapeHtml(desired[name] ?? "")
  const checked = (name) => desired[name] === true ? " checked" : ""
  return `<div class="wf-setup__production">
    <fieldset><legend>GitHub App machine identity</legend>
      <label>App ID <input data-desired="github_app_id" data-kind="number" type="number" min="1" value="${value("github_app_id")}"${disabled}></label>
      <label>Installation ID <input data-desired="github_installation_id" data-kind="number" type="number" min="1" value="${value("github_installation_id")}"${disabled}></label>
      <label>Private-key reference <input data-desired="github_app_credential_reference" value="${value("github_app_credential_reference")}" placeholder="keyring:// or env://"${disabled}></label>
      <label>Webhook reference <input data-desired="github_webhook_reference" value="${value("github_webhook_reference")}" placeholder="keyring:// or env://"${disabled}></label>
    </fieldset>
    <fieldset><legend>External data services</legend>
      <label>PostgreSQL endpoint <input data-desired="database_endpoint" value="${value("database_endpoint")}" placeholder="postgresql://host:5432/database"${disabled}></label>
      <label>Database credential reference <input data-desired="database_credential_reference" value="${value("database_credential_reference")}" placeholder="env://WF_DATABASE_PASSWORD"${disabled}></label>
      <label>Object-storage endpoint <input data-desired="object_storage_endpoint" value="${value("object_storage_endpoint")}" placeholder="https://objects.example"${disabled}></label>
      <label>Object-storage credential reference <input data-desired="object_storage_credential_reference" value="${value("object_storage_credential_reference")}" placeholder="env://WF_OBJECT_STORAGE_SECRET"${disabled}></label>
    </fieldset>
    <fieldset><legend>Optional release certification</legend>
      <label><input data-desired="prepare_release" data-kind="boolean" type="checkbox"${checked("prepare_release")}${disabled}> Prepare release certification</label>
      <label>Signing-key reference <input data-desired="release_signing_key_reference" value="${value("release_signing_key_reference")}" placeholder="keyring:// or env://"${disabled}></label>
      <label>Key ID <input data-desired="release_key_id" value="${value("release_key_id")}"${disabled}></label>
      <label>Isolated sandbox <input data-desired="release_sandbox_repository" value="${value("release_sandbox_repository")}" placeholder="owner/repository"${disabled}></label>
      <label>Soak duration seconds <input data-desired="soak_duration_seconds" data-kind="number" type="number" min="259200" value="${value("soak_duration_seconds") || "259200"}"${disabled}></label>
    </fieldset>
    <fieldset><legend>Optional controlled cutover</legend>
      <label><input data-desired="prepare_cutover" data-kind="boolean" type="checkbox"${checked("prepare_cutover")}${disabled}> Prepare production cutover</label>
      <label>Approval ID <input data-desired="cutover_approval_id" value="${value("cutover_approval_id")}"${disabled}></label>
      <label>Exact source revision <input data-desired="cutover_source_revision" value="${value("cutover_source_revision")}"${disabled}></label>
      <label>Reference repository <input data-desired="cutover_repository" value="${value("cutover_repository")}" placeholder="owner/repository"${disabled}></label>
    </fieldset>
  </div>`
}

function renderCapability(report) {
  return `<article class="wf-setup__capability" data-state="${escapeHtml(report.state)}">
    <h3>${escapeHtml(capabilityLabel(report.capability))}</h3>
    <strong>${escapeHtml(report.state)}</strong>
    <p>${escapeHtml(report.reason)}</p>
    <p>${escapeHtml(setupStateMessage(report.state))}</p>
    ${report.next_actions?.length ? `<ul>${report.next_actions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
  </article>`
}

function renderCapabilityPlaceholders(profile) {
  const states = {
    local_runtime: "needs_input",
    github_integration: "needs_input",
    release_certification: profile === "development" ? "not_required" : "needs_input",
    production_cutover: profile === "development" ? "not_required" : "needs_input",
  }
  return Object.entries(states).map(([capability, state]) => renderCapability({
    capability,
    state,
    reason: state === "not_required" ? "Optional for Development" : "Run detection to calculate readiness",
    next_actions: [],
  })).join("")
}

function renderCheck(check) {
  return `<article class="wf-setup__check" data-state="${escapeHtml(check.state)}">
    <h3>${escapeHtml(check.summary)}</h3>
    <p><strong>${escapeHtml(check.state)}</strong> — ${escapeHtml(check.impact)}</p>
    ${check.remediation?.length ? `<ul>${check.remediation.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
  </article>`
}

function renderPlan(plan, groups) {
  const section = (title, actions) => actions.length > 0
    ? `<section><h3>${title}</h3><ul>${actions.map((action) => `<li><strong>${escapeHtml(action.title)}</strong> — ${escapeHtml(action.reason)} (${escapeHtml(action.risk)}, ${action.reversible ? "reversible" : "manual recovery"})</li>`).join("")}</ul></section>`
    : ""
  return `<div class="wf-setup__plan">
    <p><strong>Plan:</strong> ${escapeHtml(plan.plan_id)}</p>
    ${section("Will create or update", groups.create)}
    ${section("Will start", groups.start)}
    ${section("Will run", groups.run)}
    ${section("Remote checks or mutations", groups.remote)}
    <section><h3>Will not do</h3><ul><li>Approve production cutover automatically</li><li>Shorten the real soak duration</li><li>Write plaintext secrets to config</li></ul></section>
  </div>`
}

function renderResult(result) {
  return `<li data-state="${escapeHtml(result.state)}"><strong>${escapeHtml(result.action_id)}</strong>: ${escapeHtml(result.state)} — ${escapeHtml(result.message)}</li>`
}

const ElementBase = globalThis.HTMLElement ?? class {}

export class WorkFrontierSetupCenter extends ElementBase {
  constructor() {
    super()
    this.api = new SetupApi()
    this.state = {
      profile: "development",
      step: "status",
      busy: false,
      message: "Opening Setup Center…",
      desired: {
        github_repository: "",
        prepare_release: false,
        soak_duration_seconds: 259200,
        prepare_cutover: false,
      },
      signingKey: null,
      envelope: EMPTY_ENVELOPE,
    }
  }

  async connectedCallback() {
    const mode = this.getAttribute?.("mode") ?? "bootstrap"
    this.api = new SetupApi({ basePath: this.getAttribute?.("base-path") ?? "/api/setup" })
    this.render()
    if (mode === "manual") return
    try {
      if (mode === "bootstrap") await this.api.exchangeBootstrapToken()
      await this.refreshStatus()
    } catch (error) {
      this.fail(error)
    }
  }

  async configure({ basePath, headers }) {
    this.api = new SetupApi({ basePath, defaultHeaders: headers })
    await this.refreshStatus()
  }

  render() {
    this.innerHTML = renderSetupCenter(this.state)
    this.querySelector('[data-field="profile"]')?.addEventListener("change", (event) => {
      this.state.profile = event.target.value
      this.state.envelope = EMPTY_ENVELOPE
      this.state.message = `Selected ${event.target.selectedOptions[0]?.textContent ?? event.target.value}`
      this.render()
    })
    this.querySelector('[data-field="github_repository"]')?.addEventListener("input", (event) => {
      this.state.desired.github_repository = event.target.value.trim()
    })
    for (const input of this.querySelectorAll("[data-desired]")) {
      input.addEventListener("input", (event) => {
        const name = event.target.getAttribute("data-desired")
        if (!name) return
        const kind = event.target.getAttribute("data-kind")
        if (kind === "boolean") {
          this.state.desired[name] = event.target.checked
        } else if (kind === "number") {
          this.state.desired[name] = Number(event.target.value)
        } else {
          this.state.desired[name] = event.target.value.trim()
        }
      })
    }
    this.querySelector('[data-action="refresh"]')?.addEventListener("click", () => this.refreshStatus())
    this.querySelector('[data-action="detect"]')?.addEventListener("click", () => this.detect())
    this.querySelector('[data-action="plan"]')?.addEventListener("click", () => this.plan())
    this.querySelector('[data-action="apply"]')?.addEventListener("click", () => this.apply())
    this.querySelector('[data-action="resume"]')?.addEventListener("click", () => this.resume())
    this.querySelector('[data-action="generate-signing-key"]')?.addEventListener("click", () => this.generateSigningKey())
    this.querySelector('[data-form="secret"]')?.addEventListener("submit", (event) => this.storeSecret(event))
  }

  async refreshStatus() {
    return this.run("Refreshing setup status…", async () => {
      this.state.envelope = await this.api.status(this.state.profile)
      this.state.message = "Setup status refreshed"
    })
  }

  async detect() {
    return this.run("Detecting environment without changes…", async () => {
      const detection = await this.api.detect(this.state.profile)
      this.state.envelope = { ...this.state.envelope, detection, plan: null, results: [] }
      this.state.message = "Detection complete. Review checks before planning."
    })
  }

  async plan() {
    if (!this.state.envelope.detection) return
    return this.run("Building a secret-free reviewed plan…", async () => {
      const plan = await this.api.plan({
        profile: this.state.profile,
        desired: this.state.desired,
        expectedSnapshotId: this.state.envelope.detection.snapshot_id,
      })
      this.state.envelope = { ...this.state.envelope, plan, results: [] }
      this.state.message = "Plan ready. Review every effect before applying."
    })
  }

  async apply() {
    if (!this.state.envelope.plan) return
    const highRisk = this.state.envelope.plan.actions.some((action) => action.risk === "high")
    if (highRisk && globalThis.confirm && !globalThis.confirm("This plan contains high-risk actions. Apply the reviewed plan?")) return
    return this.run("Applying and verifying the reviewed plan…", async () => {
      this.state.envelope = await this.api.apply(this.state.envelope.plan.plan_id)
      this.state.message = "Plan execution finished. Capability readiness was recomputed."
    })
  }

  async resume() {
    const sessionId = this.state.envelope.session_id
    if (!sessionId) return
    return this.run("Resuming the durable setup session…", async () => {
      this.state.envelope = await this.api.resume(sessionId)
      this.state.message = "Setup session resumed and capability readiness was recomputed."
    })
  }

  async generateSigningKey() {
    return this.run("Generating a release signing key directly in the secret provider…", async () => {
      const key = await this.api.generateSigningKey({
        namespace: "release",
        name: "standard-signing-key",
        key_id: "work-frontier-standard-2026-01",
      })
      this.state.signingKey = key
      this.state.desired.release_signing_key_reference = key.reference
      this.state.desired.release_key_id = key.key_id
      this.state.message = `Generated signing key ${key.key_id}; only public material is displayed.`
    })
  }

  async storeSecret(event) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const secret = {
      namespace: String(form.get("namespace") ?? ""),
      name: String(form.get("name") ?? ""),
      value: String(form.get("value") ?? ""),
    }
    return this.run("Storing secret with the configured provider…", async () => {
      const result = await this.api.storeSecret(secret)
      const cleared = removeSecretValue(secret)
      event.currentTarget.reset()
      this.state.message = `Stored ${result.reference}. The plaintext value was cleared.`
      Object.assign(secret, cleared)
    })
  }

  async run(message, operation) {
    this.state.busy = true
    this.state.message = message
    this.render()
    try {
      await operation()
    } catch (error) {
      this.fail(error)
      return
    } finally {
      this.state.busy = false
    }
    this.render()
  }

  fail(error) {
    this.state.busy = false
    this.state.message = error instanceof Error ? error.message : "Setup action failed"
    this.render()
  }
}

if (globalThis.customElements && !globalThis.customElements.get("work-frontier-setup-center")) {
  globalThis.customElements.define("work-frontier-setup-center", WorkFrontierSetupCenter)
}
