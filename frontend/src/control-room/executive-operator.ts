export interface ExecutiveMetric {
  readonly label: string
  readonly value: number
  readonly unit: string
  readonly authority: string
  readonly sourceRevision: string
}

export interface OperatorStatus {
  readonly connectionState: "healthy" | "degraded" | "unavailable"
  readonly queueDepth: number
  readonly deadLetters: number
  readonly reconciliationState: string
  readonly auditEntries: readonly Record<string, unknown>[]
}

const secretKeys = /authorization|token|password|secret|credential/i

export function redactAuditEntry(
  value: Record<string, unknown>,
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(value).map(([key, item]) => [
      key,
      secretKeys.test(key) ? "[REDACTED]" : item,
    ]),
  )
}

export function canViewOperations(role: string): boolean {
  return role === "operator" || role === "admin"
}

export function exportExecutiveMetrics(
  metrics: readonly ExecutiveMetric[],
): string {
  const rows = [
    "label,value,unit,authority,source_revision",
    ...metrics.map((metric) =>
      [
        metric.label,
        metric.value,
        metric.unit,
        metric.authority,
        metric.sourceRevision,
      ].join(","),
    ),
  ]
  return rows.join("\n")
}
