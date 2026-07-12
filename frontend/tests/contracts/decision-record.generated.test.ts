import { createHash } from "node:crypto"
import { readdirSync, readFileSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

import { DecisionRecordSchema } from "../../src/contracts/decision-record.generated"
import { canonicalJson } from "../../src/lib/canonical-json"

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
    const result = DecisionRecordSchema.parse(validRecord)
    expect(result).toEqual(validRecord)
  })

  it("rejects a missing workspace when the envelope is parsed", () => {
    const { workspace_id: _, ...withoutWorkspace } = validRecord
    const result = DecisionRecordSchema.safeParse(withoutWorkspace)
    expect(result.success).toBe(false)
  })

  it.each(fixtureFiles)("cross-language consistency: %s", (fixtureFile) => {
    const fixturePath = join(FIXTURES_DIR, fixtureFile)
    const jsonStr = readFileSync(fixturePath, "utf-8")
    const data = JSON.parse(jsonStr) as unknown
    const expectedValid = fixtureFile.startsWith("valid-")
    const result = DecisionRecordSchema.safeParse(data)

    if (expectedValid) {
      expect(result.success).toBe(true)
      if (result.success) {
        const canonical = canonicalJson(result.data)
        const digest = createHash("sha256").update(canonical, "utf8").digest("hex")
        const goldenPath = fixturePath.replace(/\.json$/, ".canonical.sha256")
        const expected = readFileSync(goldenPath, "utf-8").trim()
        expect(digest).toBe(expected)
      }
    } else {
      expect(result.success).toBe(false)
    }
  })
})
