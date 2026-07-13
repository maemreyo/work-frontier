import {
  canViewOperations,
  redactAuditEntry,
  type OperatorStatus,
} from "./executive-operator"

export interface OperatorViewProps {
  readonly userRole: string
  readonly status: OperatorStatus
  readonly onRetryDeadLetter: () => void
  readonly onReconcile: () => void
}

export function OperatorView({
  userRole,
  status,
  onRetryDeadLetter,
  onReconcile,
}: OperatorViewProps) {
  if (!canViewOperations(userRole)) {
    return (
      <section aria-labelledby="operator-heading">
        <h1 id="operator-heading">Operator view</h1>
        <output>
          Operational data is available only to an Operator or Admin role.
        </output>
      </section>
    )
  }
  return (
    <section aria-labelledby="operator-heading">
      <h1 id="operator-heading">Operator view</h1>
      <dl>
        <dt>Connection</dt>
        <dd>{status.connectionState}</dd>
        <dt>Queue depth</dt>
        <dd>{status.queueDepth}</dd>
        <dt>Dead letters</dt>
        <dd>{status.deadLetters}</dd>
        <dt>Reconciliation</dt>
        <dd>{status.reconciliationState}</dd>
      </dl>
      <button
        disabled={status.deadLetters === 0}
        onClick={onRetryDeadLetter}
        type="button"
      >
        Retry dead letter
      </button>
      <button onClick={onReconcile} type="button">
        Run guarded reconciliation
      </button>
      <h2>Redacted audit</h2>
      <pre>{JSON.stringify(status.auditEntries.map(redactAuditEntry), null, 2)}</pre>
    </section>
  )
}
