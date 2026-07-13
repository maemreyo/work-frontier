import { useReducer, useState } from "react"

import { buildBuilderWorkspace, type BuilderDecision } from "./builder"
import { BuilderView } from "./builder-view"
import type { FrontierItem } from "./client.generated"
import { initialOnboardingState, isAuthoritative, reduceOnboarding } from "./onboarding"
import { ControlRoomShell, type ControlRoomView } from "./shell"

const seededItems: readonly FrontierItem[] = [
  {
    item_id: "item-foundation",
    decision_id: "decision-foundation",
    decision_type: "ready",
    title: "Stabilize the release foundation",
    ready: true,
    ranking_position: 1,
    authority: "authoritative",
    freshness: "current",
    why: ["program_priority=100", "work_class=foundation", "stable_id=item-foundation"],
    blocked_by: [],
  },
  {
    item_id: "item-api",
    decision_id: "decision-api",
    decision_type: "ready",
    title: "Complete the API contract",
    ready: true,
    ranking_position: 2,
    authority: "authoritative",
    freshness: "current",
    why: ["program_priority=90", "stable_id=item-api"],
    blocked_by: [],
  },
  {
    item_id: "item-stale",
    decision_id: "decision-stale",
    decision_type: "blocked",
    title: "Publish stale projection",
    ready: false,
    ranking_position: null,
    authority: "stale",
    freshness: "stale",
    why: ["source_revision_stale"],
    blocked_by: ["item-api"],
  },
]

export function ControlRoomApp() {
  const [onboarding, dispatch] = useReducer(reduceOnboarding, initialOnboardingState)
  const [activeView, setActiveView] = useState<ControlRoomView>("builder")
  const [status, setStatus] = useState("Ready for onboarding")
  const [claimedItem, setClaimedItem] = useState<string | null>(null)
  const workspace = buildBuilderWorkspace(seededItems)

  if (!isAuthoritative(onboarding)) {
    return (
      <main className="wf-onboarding" id="wf-main">
        <h1>Connect Work Frontier</h1>
        <p role="status">{onboarding.conflict ?? status}</p>
        {onboarding.step === "install" ? (
          <button
            type="button"
            onClick={() => {
              dispatch({ type: "installation_connected" })
              setStatus("GitHub installation connected")
            }}
          >
            Connect installation
          </button>
        ) : null}
        {onboarding.step === "profile" ? (
          <button
            type="button"
            onClick={() => {
              dispatch({ type: "profile_validated" })
              setStatus("Normalization profile validated")
            }}
          >
            Validate profile
          </button>
        ) : null}
        {onboarding.step === "reconcile" ? (
          <button
            type="button"
            onClick={() => {
              dispatch({ type: "reconciliation_succeeded" })
              setStatus("Reconciliation complete")
            }}
          >
            Reconcile authoritative state
          </button>
        ) : null}
      </main>
    )
  }

  function claim(decision: BuilderDecision): void {
    if (claimedItem === null) {
      setClaimedItem(decision.item.item_id)
      setStatus(`Claimed ${decision.item.title}`)
      return
    }
    setStatus(`Claim conflict: ${claimedItem} is already owned; refresh required`)
  }

  return (
    <ControlRoomShell
      activeView={activeView}
      onNavigate={setActiveView}
      session={{
        actorId: "builder-1",
        role: "builder",
        tenantId: "tenant-1",
        workspaceId: "workspace-1",
      }}
    >
      <p aria-live="polite" role="status">{status}</p>
      {activeView === "builder" ? (
        <BuilderView
          workspace={workspace}
          onClaim={claim}
          onOpen={(decision) => setStatus(`Opened ${decision.item.decision_id}`)}
        />
      ) : (
        <section aria-labelledby="view-heading">
          <h1 id="view-heading">{activeView}</h1>
          <p>This role-adapted view has no readiness editing controls.</p>
        </section>
      )}
    </ControlRoomShell>
  )
}
