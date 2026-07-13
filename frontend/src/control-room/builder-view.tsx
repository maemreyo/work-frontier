import type { BuilderDecision, BuilderWorkspace } from "./builder"

export interface BuilderViewProps {
  readonly workspace: BuilderWorkspace
  readonly onClaim: (decision: BuilderDecision) => void
  readonly onOpen: (decision: BuilderDecision) => void
}

export function BuilderView({ workspace, onClaim, onOpen }: BuilderViewProps) {
  return (
    <section aria-labelledby="builder-heading">
      <h1 id="builder-heading">Builder workspace</h1>
      <section aria-labelledby="recommended-heading">
        <h2 id="recommended-heading">Recommended Next</h2>
        {workspace.recommended === null ? (
          <output>No authoritative ready recommendation is available.</output>
        ) : (
          <DecisionCard decision={workspace.recommended} onClaim={onClaim} onOpen={onOpen} />
        )}
      </section>
      <section aria-labelledby="ready-heading">
        <h2 id="ready-heading">All authoritative ready work</h2>
        <ul>{workspace.ready.map((decision) => <li key={decision.item.item_id}><DecisionCard decision={decision} onClaim={onClaim} onOpen={onOpen} /></li>)}</ul>
      </section>
      <section aria-labelledby="blocked-heading">
        <h2 id="blocked-heading">Blocked or non-authoritative</h2>
        <ul>{workspace.blocked.map((decision) => <li key={decision.item.item_id}><DecisionCard decision={decision} onClaim={onClaim} onOpen={onOpen} /></li>)}</ul>
      </section>
    </section>
  )
}

function DecisionCard({ decision, onClaim, onOpen }: { readonly decision: BuilderDecision; readonly onClaim: (decision: BuilderDecision) => void; readonly onOpen: (decision: BuilderDecision) => void }) {
  return (
    <article aria-label={decision.accessibleLabel} className="wf-decision-card">
      <h3>{decision.item.title}</h3>
      <p><strong>Decision type:</strong> {decision.item.decision_type}</p>
      <p><strong>Authority:</strong> {decision.item.authority}; <strong>freshness:</strong> {decision.item.freshness}</p>
      <ol aria-label="Deterministic ranking rationale">{decision.item.why.map((reason) => <li key={reason}>{reason}</li>)}</ol>
      {decision.disabledReason === null ? null : <output>{decision.disabledReason}</output>}
      <button disabled={!decision.claimable} onClick={() => onClaim(decision)} type="button">Claim</button>
      <button onClick={() => onOpen(decision)} type="button">Open decision detail</button>
    </article>
  )
}
