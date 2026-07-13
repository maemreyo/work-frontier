import type { FrontierItem } from "./client.generated"

export interface BuilderDecision {
  readonly item: FrontierItem
  readonly claimable: boolean
  readonly disabledReason: string | null
  readonly isRecommended: boolean
  readonly accessibleLabel: string
}

export interface BuilderWorkspace {
  readonly recommended: BuilderDecision | null
  readonly ready: readonly BuilderDecision[]
  readonly blocked: readonly BuilderDecision[]
}

export function buildBuilderWorkspace(items: readonly FrontierItem[]): BuilderWorkspace {
  const ordered = [...items].sort(compareFrontierItems)
  const decisions = ordered.map((item) => toDecision(item, item.ranking_position === 1))
  return {
    recommended: decisions.find((decision) => decision.isRecommended && decision.claimable) ?? null,
    ready: decisions.filter((decision) => decision.claimable),
    blocked: decisions.filter((decision) => !decision.claimable),
  }
}

export function claimDivergenceRequired(
  decision: BuilderDecision,
  recommended: BuilderDecision | null,
): boolean {
  return decision.claimable && recommended !== null && decision.item.item_id !== recommended.item.item_id
}

function toDecision(item: FrontierItem, isRecommended: boolean): BuilderDecision {
  const disabledReason = claimDisabledReason(item)
  return {
    item,
    claimable: disabledReason === null,
    disabledReason,
    isRecommended,
    accessibleLabel: `${item.title}; ${item.decision_type}; ${disabledReason ?? "claimable"}`,
  }
}

function claimDisabledReason(item: FrontierItem): string | null {
  if (!item.ready) return item.blocked_by.length > 0 ? `Blocked by ${item.blocked_by.join(", ")}` : "Not ready"
  if (item.authority !== "authoritative") return `Authority is ${item.authority}`
  if (item.freshness !== "current") return `Source is ${item.freshness}`
  return null
}

function compareFrontierItems(left: FrontierItem, right: FrontierItem): number {
  const leftRank = left.ranking_position ?? Number.MAX_SAFE_INTEGER
  const rightRank = right.ranking_position ?? Number.MAX_SAFE_INTEGER
  return leftRank - rightRank || left.item_id.localeCompare(right.item_id)
}
