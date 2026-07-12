/** Deterministic JSON serialization matching Python DecisionRecord.canonical_json(). */

function sortDeep(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(sortDeep)
  }
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).sort(([a], [b]) =>
      a < b ? -1 : a > b ? 1 : 0,
    )
    const sorted: Record<string, unknown> = {}
    for (const [key, nested] of entries) {
      sorted[key] = sortDeep(nested)
    }
    return sorted
  }
  return value
}

export function canonicalJson(value: unknown): string {
  return JSON.stringify(sortDeep(value))
}
