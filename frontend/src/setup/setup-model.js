const CAPABILITY_LABELS = {
  local_runtime: "Local runtime",
  github_integration: "GitHub integration",
  release_certification: "Release certification",
  production_cutover: "Production cutover",
}

export function capabilityLabel(capability) {
  return CAPABILITY_LABELS[capability] ?? capability.replaceAll("_", " ")
}

export function setupStateMessage(state) {
  switch (state) {
    case "ready":
      return "Ready — all required checks are verified."
    case "repairable":
      return "Repairable — Work Frontier can propose a reviewed repair plan."
    case "needs_input":
      return "Needs input — provide the missing configuration to continue."
    case "blocked":
      return "Blocked — resolve the required safety or dependency issue before continuing."
    case "not_required":
      return "Not required for the selected profile."
    default:
      return "Status is not available yet."
  }
}

export function groupPlanActions(actions) {
  const groups = { create: [], start: [], run: [], remote: [] }
  for (const action of actions) {
    if (action.kind === "write_config" || action.kind.includes("secret")) {
      groups.create.push(action)
    } else if (action.kind.includes("docker") || action.kind.includes("start")) {
      groups.start.push(action)
    } else if (action.kind.includes("github") || action.kind.includes("remote")) {
      groups.remote.push(action)
    } else {
      groups.run.push(action)
    }
  }
  return groups
}

export function removeSecretValue(form) {
  return { ...form, value: "" }
}

export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;")
}
