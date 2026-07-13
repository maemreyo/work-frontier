import { describe, expect, it } from "vitest"
import { initialOnboardingState, isAuthoritative, reduceOnboarding } from "../../src/control-room/onboarding"

describe("Control Room onboarding", () => {
  it("does not declare authority before reconciliation succeeds", () => {
    const installed = reduceOnboarding(initialOnboardingState, { type: "installation_connected" })
    const profiled = reduceOnboarding(installed, { type: "profile_validated" })
    expect(isAuthoritative(profiled)).toBe(false)
    expect(isAuthoritative(reduceOnboarding(profiled, { type: "reconciliation_succeeded" }))).toBe(true)
  })

  it("keeps conflicted onboarding in draft reconciliation with recovery", () => {
    const conflicted = reduceOnboarding(initialOnboardingState, {
      type: "reconciliation_conflicted",
      reason: "permission conflict",
    })
    expect(conflicted.step).toBe("reconcile")
    expect(conflicted.conflict).toBe("permission conflict")
    expect(reduceOnboarding(conflicted, { type: "retry_reconciliation" }).conflict).toBeNull()
  })
})
