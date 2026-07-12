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

const REQUIRED_VALID_FIXTURES: ReadonlySet<string> = new Set([
  "valid-minimal.json",
  "valid-maximal.json",
])
const REQUIRED_INVALID_FIXTURES: ReadonlySet<string> = new Set([
  "invalid-missing-workspace-id.json",
  "invalid-empty-decision-id.json",
  "invalid-empty-source-revision-set.json",
  "invalid-unknown-field.json",
  "invalid-naive-datetime.json",
  "invalid-uppercase-hash.json",
  "invalid-non-hex-hash.json",
  "invalid-coerce-int.json",
  "invalid-coerce-bool.json",
])
const REQUIRED_FIXTURE_INVENTORY: ReadonlySet<string> = new Set([
  ...REQUIRED_VALID_FIXTURES,
  ...REQUIRED_INVALID_FIXTURES,
])

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

  it("fixture inventory matches the shared corpus", () => {
    const onDisk = new Set(
      readdirSync(FIXTURES_DIR).filter((f) => f.endsWith(".json"))
    )
    const missing = [...REQUIRED_FIXTURE_INVENTORY].filter((n) => !onDisk.has(n))
    const extras = [...onDisk].filter((n) => !REQUIRED_FIXTURE_INVENTORY.has(n))
    expect({ missing, extras }).toEqual({ missing: [], extras: [] })
  })

  it("valid fixtures have paired golden hashes", () => {
    for (const name of REQUIRED_VALID_FIXTURES) {
      const fixturePath = join(FIXTURES_DIR, name)
      const goldenPath = fixturePath.replace(/\.json$/, ".canonical.sha256")
      const expected = readFileSync(goldenPath, "utf-8").trim()
      expect(expected).toMatch(/^[0-9a-f]{64}$/)
    }
  })

  it("breaking mutation changes the canonical digest", () => {
    const canonical = canonicalJson(validRecord)
    const originalDigest = createHash("sha256").update(canonical, "utf8").digest("hex")
    const mutatedCanonical = canonical.replace(/"ranking_position":1/, '"ranking_position":null')
    const mutatedDigest = createHash("sha256").update(mutatedCanonical, "utf8").digest("hex")
    expect(mutatedDigest).not.toBe(originalDigest)
  })
})
