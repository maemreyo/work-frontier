import { describe, expect, it } from "vitest"
import { buildBuilderWorkspace, claimDivergenceRequired } from "../../src/control-room/builder"
import type { FrontierItem } from "../../src/control-room/client.generated"

const ready = (id: string, rank: number): FrontierItem => ({
  item_id: id,
  decision_id: `decision-${id}`,
  decision_type: "ready",
  title: id,
  ready: true,
  ranking_position: rank,
  authority: "authoritative",
  freshness: "current",
  why: ["program_priority", "stable_id"],
  blocked_by: [],
})

describe("Builder view model", () => {
  it("renders API rank one as Recommended Next", () => {
    const workspace = buildBuilderWorkspace([ready("second", 2), ready("first", 1)])
    expect(workspace.recommended?.item.item_id).toBe("first")
    expect(workspace.ready.map((decision) => decision.item.item_id)).toEqual(["first", "second"])
  })

  it("disables stale or conflicted claims with an exact reason", () => {
    const stale: FrontierItem = { ...ready("stale", 1), authority: "conflicted" }
    const workspace = buildBuilderWorkspace([stale])
    expect(workspace.recommended).toBeNull()
    expect(workspace.blocked[0]?.disabledReason).toBe("Authority is conflicted")
  })

  it("requires a divergence reason for another authoritative-ready item", () => {
    const workspace = buildBuilderWorkspace([ready("first", 1), ready("second", 2)])
    expect(claimDivergenceRequired(workspace.ready[1]!, workspace.recommended)).toBe(true)
  })
})
