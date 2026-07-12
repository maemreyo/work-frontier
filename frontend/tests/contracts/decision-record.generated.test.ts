import { readdirSync, readFileSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

import { DecisionRecordSchema } from "../../src/contracts/decision-record.generated"

const hash = "a".repeat(64)

const validRecord = {
  decision_id: "decision-01",
  workspace_id: "workspace-01",
  program_id: null,
  item_id: "item-01",
  computed_at: "2026-07-12T00:00:00Z",
  causation_id: "event-01",
  correlation_id: "trace-01",
  normalized_snapshot_id: "snapshot-01",
  normalized_snapshot_hash: hash,
  source_revision_set: { "github:issue:1": "revision-01" },
  graph_revision: "graph-01",
  policy_bundle_id: "policy-01",
  policy_bundle_hash: hash,
  ranking_pipeline_hash: hash,
  engine_version: "engine-01",
  normalization_profile_version: "profile-01",
  ready: true,
  ranking_position: 1,
  schema_version: "1.0.0",
}

const FIXTURES_DIR = join(__dirname, "../../..", "contracts", "fixtures", "decision-record")
const fixtureFiles = readdirSync(FIXTURES_DIR)
  .filter((f) => f.endsWith(".json"))
  .sort()

describe("DecisionRecordSchema", () => {
  it("round-trips a complete canonical envelope when parsed", () => {
    // Given a complete DecisionRecord transport payload
    // When the generated Zod contract parses it
    const result = DecisionRecordSchema.parse(validRecord)

    // Then the canonical fields survive unchanged
    expect(result).toEqual(validRecord)
  })

  it("rejects a missing workspace when the envelope is parsed", () => {
    // Given an otherwise complete DecisionRecord payload without workspace scope
    const { workspace_id: _, ...withoutWorkspace } = validRecord

    // When the generated Zod contract validates it
    const result = DecisionRecordSchema.safeParse(withoutWorkspace)

    // Then the required reproducibility field is rejected
    expect(result.success).toBe(false)
  })

  it.each(fixtureFiles)("cross-language consistency: %s", (fixtureFile) => {
    // Given a shared fixture with expected validity encoded in filename
    const fixturePath = join(FIXTURES_DIR, fixtureFile)
    const jsonStr = readFileSync(fixturePath, "utf-8")
    const data = JSON.parse(jsonStr)
    const expectedValid = fixtureFile.startsWith("valid-")

    // When the Zod contract validates it
    const result = DecisionRecordSchema.safeParse(data)

    // Then the verdict matches Python/Pydantic
    if (expectedValid) {
      expect(result.success).toBe(true)
    } else {
      expect(result.success).toBe(false)
    }
  })
})
