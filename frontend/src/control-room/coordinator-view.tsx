import {
  buildCoordinatorRows,
  dependencyTableAlternative,
  type DependencyProposal,
} from "./coordinator"

export interface CoordinatorViewProps {
  readonly proposals: readonly DependencyProposal[]
  readonly actorId: string
  readonly onApprove: (proposalId: string) => void
  readonly onReject: (proposalId: string) => void
}

export function CoordinatorView({
  proposals,
  actorId,
  onApprove,
  onReject,
}: CoordinatorViewProps) {
  const rows = buildCoordinatorRows(proposals, actorId)
  const alternatives = dependencyTableAlternative(proposals)
  return (
    <section aria-labelledby="coordinator-heading">
      <h1 id="coordinator-heading">Coordinator proposals</h1>
      <p>
        Dependency changes remain proposals until an independent actor approves an
        exact source revision.
      </p>
      <table>
        <caption>Keyboard-accessible dependency repair alternative</caption>
        <thead>
          <tr>
            <th scope="col">Relationship</th>
            <th scope="col">Unlock impact</th>
            <th scope="col">State</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={row.proposal.proposalId}>
              <td>{alternatives[index]}</td>
              <td>{row.proposal.unlockCount}</td>
              <td>{row.disabledReason ?? "Ready for independent approval"}</td>
              <td>
                <button
                  disabled={!row.approvalAllowed}
                  onClick={() => onApprove(row.proposal.proposalId)}
                  type="button"
                >
                  Approve
                </button>
                <button
                  disabled={row.proposal.status !== "pending"}
                  onClick={() => onReject(row.proposal.proposalId)}
                  type="button"
                >
                  Reject
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
