import { describe, expect, it } from "vitest"

import {
  canViewOperations,
  exportExecutiveMetrics,
  redactAuditEntry,
} from "../../src/control-room/executive-operator"

describe("role-adapted views", () => {
  it("redacts sensitive audit values", () => {
    expect(redactAuditEntry({ token: "secret", event: "safe" })).toEqual({
      token: "[REDACTED]",
      event: "safe",
    })
  })

  it("restricts operations and exports authority metadata", () => {
    expect(canViewOperations("viewer")).toBe(false)
    expect(canViewOperations("operator")).toBe(true)
    expect(
      exportExecutiveMetrics([
        {
          label: "Risk",
          value: 2,
          unit: "items",
          authority: "authoritative",
          sourceRevision: "rev-1",
        },
      ]),
    ).toContain("authoritative,rev-1")
  })
})
