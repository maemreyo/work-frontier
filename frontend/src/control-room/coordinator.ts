export interface DependencyProposal {
  readonly proposalId: string
  readonly sourceItemId: string
  readonly targetItemId: string
  readonly action: "add_blocker" | "remove_blocker"
  readonly status: "pending" | "approved" | "rejected" | "stale"
  readonly createdBy: string
  readonly sourceRevision: string
  readonly currentSourceRevision: string
  readonly unlockCount: number
}

export interface CoordinatorRow {
  readonly proposal: DependencyProposal
  readonly approvalAllowed: boolean
  readonly disabledReason: string | null
}

export function buildCoordinatorRows(
  proposals: readonly DependencyProposal[],
  actorId: string,
): readonly CoordinatorRow[] {
  return [...proposals]
    .sort(
      (left, right) =>
        right.unlockCount - left.unlockCount ||
        left.proposalId.localeCompare(right.proposalId),
    )
    .map((proposal) => {
      let disabledReason: string | null = null
      if (proposal.status !== "pending") disabledReason = `Proposal is ${proposal.status}`
      else if (proposal.createdBy === actorId) disabledReason = "Separation of duties"
      else if (proposal.sourceRevision !== proposal.currentSourceRevision) {
        disabledReason = "Source revision is stale; refresh required"
      }
      return {
        proposal,
        approvalAllowed: disabledReason === null,
        disabledReason,
      }
    })
}

export function dependencyTableAlternative(
  proposals: readonly DependencyProposal[],
): readonly string[] {
  return proposals.map(
    (proposal) =>
      `${proposal.sourceItemId} ${proposal.action} ${proposal.targetItemId}; unlocks ${proposal.unlockCount}`,
  )
}
