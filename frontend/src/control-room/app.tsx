import { useState } from "react"

import { SetupCenter } from "../setup/setup-center"
import { buildBuilderWorkspace, type BuilderDecision } from "./builder"
import { BuilderView } from "./builder-view"
import type { FrontierItem } from "./client.generated"
import { CoordinatorView } from "./coordinator-view"
import type { DependencyProposal } from "./coordinator"
import { CopilotPanel } from "./copilot-panel"
import { ExecutiveView } from "./executive-view"
import type {
  ExecutiveMetric,
  OperatorStatus,
} from "./executive-operator"
import { OperatorView } from "./operator-view"
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
  {
    item_id: "item-conflicted",
    decision_id: "decision-conflicted",
    decision_type: "conflicted",
    title: "Resolve conflicting source values",
    ready: false,
    ranking_position: null,
    authority: "conflicted",
    freshness: "current",
    why: ["distinct_source_values > 1"],
    blocked_by: [],
  },
  {
    item_id: "item-unavailable",
    decision_id: "decision-unavailable",
    decision_type: "unavailable",
    title: "Restore unavailable source authority",
    ready: false,
    ranking_position: null,
    authority: "unavailable",
    freshness: "unavailable",
    why: ["no_source_observations"],
    blocked_by: [],
  },
]

const proposals: readonly DependencyProposal[] = [
  {
    proposalId: "proposal-independent",
    sourceItemId: "item-stale",
    targetItemId: "item-api",
    action: "remove_blocker",
    status: "pending",
    createdBy: "builder-2",
    sourceRevision: "rev-4",
    currentSourceRevision: "rev-4",
    unlockCount: 3,
  },
  {
    proposalId: "proposal-self",
    sourceItemId: "item-api",
    targetItemId: "item-foundation",
    action: "add_blocker",
    status: "pending",
    createdBy: "builder-1",
    sourceRevision: "rev-4",
    currentSourceRevision: "rev-4",
    unlockCount: 1,
  },
]

const metrics: readonly ExecutiveMetric[] = [
  {
    label: "Terminal outcomes",
    value: 12,
    unit: "completed",
    authority: "authoritative",
    sourceRevision: "rev-4",
  },
  {
    label: "At-risk outcomes",
    value: 2,
    unit: "items",
    authority: "authoritative",
    sourceRevision: "rev-4",
  },
]

const operatorStatus: OperatorStatus = {
  connectionState: "degraded",
  queueDepth: 4,
  deadLetters: 1,
  reconciliationState: "attention_required",
  auditEntries: [
    {
      event: "connection_degraded",
      token: "must-not-render",
      actor: "operator-1",
    },
  ],
}

export function ControlRoomApp() {
  const [activeView, setActiveView] = useState<ControlRoomView>("builder")
  const [status, setStatus] = useState("Runtime ready; Setup Center remains available")
  const [claimedItem, setClaimedItem] = useState<string | null>(null)
  const [proposalState, setProposalState] = useState(proposals)
  const [items, setItems] = useState(seededItems)
  const workspace = buildBuilderWorkspace(items)

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
        role: activeView === "operator" || activeView === "setup" ? "operator" : "builder",
        sessionToken: "session-good",
        tenantId: "tenant-1",
        workspaceId: "workspace-1",
      }}
    >
      <output>
        {status}
      </output>
      {activeView === "builder" ? (
        <>
          <BuilderView
            workspace={workspace}
            onClaim={claim}
            onOpen={(decision) => setStatus(`Opened ${decision.item.decision_id}`)}
          />
          <CopilotPanel
            citations={[]}
            enabled={false}
            explanation={null}
            onExplain={() => setStatus("Copilot explanation requested")}
          />
        </>
      ) : null}
      {activeView === "coordinator" ? (
        <CoordinatorView
          actorId="builder-1"
          proposals={proposalState}
          onApprove={(proposalId) => {
            const proposal = proposalState.find(
              (candidate) => candidate.proposalId === proposalId,
            )
            if (proposal === undefined) return
            setProposalState((current) =>
              current.map((candidate) =>
                candidate.proposalId === proposalId
                  ? { ...candidate, status: "approved" }
                  : candidate,
              ),
            )
            if (proposal.action === "remove_blocker") {
              setItems((current) =>
                current.map((item) =>
                  item.item_id === proposal.sourceItemId
                    ? {
                        ...item,
                        ready: true,
                        ranking_position: 3,
                        authority: "authoritative",
                        freshness: "current",
                        blocked_by: [],
                        why: [
                          ...item.why,
                          `approved_proposal=${proposalId}`,
                        ],
                      }
                    : item,
                ),
              )
            }
            setStatus(`Approved ${proposalId}; frontier recomputed`)
          }}
          onReject={(proposalId) => {
            setProposalState((current) =>
              current.map((candidate) =>
                candidate.proposalId === proposalId
                  ? { ...candidate, status: "rejected" }
                  : candidate,
              ),
            )
            setStatus(`Rejected ${proposalId}`)
          }}
        />
      ) : null}
      {activeView === "executive" ? <ExecutiveView metrics={metrics} /> : null}
      {activeView === "operator" ? (
        <OperatorView
          userRole="operator"
          status={operatorStatus}
          onReconcile={() => setStatus("Guarded reconciliation requested")}
          onRetryDeadLetter={() => setStatus("Dead letter retry requested")}
        />
      ) : null}
      {activeView === "setup" ? <SetupCenter /> : null}
    </ControlRoomShell>
  )
}
