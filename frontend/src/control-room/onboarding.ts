/** Deterministic onboarding state machine; authority is never declared early. */

export type OnboardingStep = "install" | "profile" | "reconcile" | "authoritative"

export interface OnboardingState {
  readonly step: OnboardingStep
  readonly installationConnected: boolean
  readonly profileValidated: boolean
  readonly reconciliationComplete: boolean
  readonly conflict: string | null
}

export type OnboardingEvent =
  | { readonly type: "installation_connected" }
  | { readonly type: "profile_validated" }
  | { readonly type: "reconciliation_succeeded" }
  | { readonly type: "reconciliation_conflicted"; readonly reason: string }
  | { readonly type: "retry_reconciliation" }

export const initialOnboardingState: OnboardingState = {
  step: "install",
  installationConnected: false,
  profileValidated: false,
  reconciliationComplete: false,
  conflict: null,
}

export function reduceOnboarding(
  state: OnboardingState,
  event: OnboardingEvent,
): OnboardingState {
  switch (event.type) {
    case "installation_connected":
      return { ...state, installationConnected: true, step: "profile", conflict: null }
    case "profile_validated":
      if (!state.installationConnected) return state
      return { ...state, profileValidated: true, step: "reconcile", conflict: null }
    case "reconciliation_succeeded":
      if (!state.installationConnected || !state.profileValidated) return state
      return { ...state, reconciliationComplete: true, step: "authoritative", conflict: null }
    case "reconciliation_conflicted":
      return { ...state, reconciliationComplete: false, step: "reconcile", conflict: event.reason }
    case "retry_reconciliation":
      return { ...state, reconciliationComplete: false, step: "reconcile", conflict: null }
  }
}

export function isAuthoritative(state: OnboardingState): boolean {
  return state.step === "authoritative" && state.reconciliationComplete
}
