import { describe, expect, it } from "vitest"

import {
  buildCoordinatorRows,
  dependencyTableAlternative,
  type DependencyProposal,
} from "../../src/control-room/coordinator"

const proposals: readonly DependencyProposal[] = [
  {
    proposalId: "p2",
    sourceItemId: "b",
    targetItemId: "a",
    action: "remove_blocker",
    status: "pending",
    createdBy: "other",
    sourceRevision: "2",
    currentSourceRevision: "2",
    unlockCount: 4,
  },
  {
    proposalId: "p1",
    sourceItemId: "a",
    targetItemId: "b",
    action: "add_blocker",
    status: "pending",
    createdBy: "actor",
    sourceRevision: "1",
    currentSourceRevision: "1",
    unlockCount: 1,
  },
]

describe("coordinator workflow", () => {
  it("orders by unlock impact and enforces separation of duties", () => {
    const rows = buildCoordinatorRows(proposals, "actor")
    expect(rows.map((row) => row.proposal.proposalId)).toEqual(["p2", "p1"])
    expect(rows[0]?.approvalAllowed).toBe(true)
    expect(rows[1]?.disabledReason).toBe("Separation of duties")
  })

  it("provides a keyboard table alternative", () => {
    expect(dependencyTableAlternative(proposals)[0]).toContain("remove_blocker")
  })
})
