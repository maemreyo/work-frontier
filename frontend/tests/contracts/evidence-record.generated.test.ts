import { createHash } from "node:crypto"
import { readFileSync, readdirSync } from "node:fs"
import { join } from "node:path"
import { describe, expect, it } from "vitest"

import { EvidenceRecordSchema } from "../../src/contracts/evidence-record.generated"
import {
  canonicalizeEvidenceRecord,
  isEvidenceRecordValid,
  validateEvidenceRecordSemantic,
} from "../../src/contracts/evidence-record-semantic"

const FIXTURES_DIR = join(__dirname, "../../..", "contracts", "fixtures", "evidence")
const fixtureFiles = readdirSync(FIXTURES_DIR)
  .filter((f) => f.endsWith(".json"))
  .sort()

const REQUIRED_VALID_FIXTURES: ReadonlySet<string> = new Set([
  "valid-minimal.json",
  "valid-full.json",
  "valid-maximal.json",
])

// Every invalid fixture must be rejected by at least one validation layer
// (Zod structural or semantic validator).
const REQUIRED_INVALID_FIXTURES: ReadonlySet<string> = new Set([
  // Schema-level (Zod rejects via pattern/regex/structural rules)
  "invalid-absolute-working-directory.json",
  "invalid-absolute-artifact-path.json",
  "invalid-backslash-working-directory.json",
  "invalid-backslash-artifact-path.json",
  "invalid-missing-environment-os.json",
  // Semantic-level (Zod accepts, validateEvidenceRecordSemantic rejects)
  "invalid-traversal-working-directory.json",
  "invalid-traversal-artifact-path.json",
  "invalid-pass-with-failing-result.json",
  "invalid-fail-zero-without-failing-result.json",
  "invalid-duration-mismatch.json",
  "invalid-not-applicable-short-reason.json",
])

const REQUIRED_FIXTURE_INVENTORY: ReadonlySet<string> = new Set([
  ...REQUIRED_VALID_FIXTURES,
  ...REQUIRED_INVALID_FIXTURES,
])

function pythonCanonicalJson(value: unknown, path: readonly string[] = []): string {
  if (value === null) return "null"
  if (typeof value === "string") return JSON.stringify(value)
  if (typeof value === "boolean") return value ? "true" : "false"
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new Error(`non-finite number at ${path.join(".")}`)
    }
    // Pydantic's typed float serializes integral duration values as 15.0,
    // while JSON.parse/JSON.stringify would otherwise collapse them to 15.
    if (path.at(-1) === "duration_seconds" && Number.isInteger(value)) {
      return `${value}.0`
    }
    return JSON.stringify(value)
  }
  if (Array.isArray(value)) {
    return `[${value
      .map((item, index) => pythonCanonicalJson(item, [...path, String(index)]))
      .join(",")}]`
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).sort(
      ([left], [right]) => left.localeCompare(right),
    )
    return `{${entries
      .map(
        ([key, item]) =>
          `${JSON.stringify(key)}:${pythonCanonicalJson(item, [...path, key])}`,
      )
      .join(",")}}`
  }
  throw new Error(`unsupported canonical value at ${path.join(".")}`)
}

// A minimal valid record to use in unit tests.
const validRecord = {
  schema_version: "1.0.0" as const,
  harness_id: "WF-HAR-PREFLIGHT-01",
  status: "pass" as const,
  run_id: "run-test-001",
  subject_sha: "a1b2c3d4e5f6789012345678901234567890abcd",
  subject_tree_sha: "0123456789abcdef0123456789abcdef01234567",
  invocation: {
    command: "pytest tests/unit",
    exit_code: 0,
    working_directory: ".",
    start_time: "2026-07-12T03:20:00Z",
    end_time: "2026-07-12T03:20:15Z",
    duration_seconds: 15.0,
  },
  tool: {
    name: "pytest",
    version: "8.2.0",
    commit_sha: "a1b2c3d4e5f6789012345678901234567890abcd",
  },
  applicability: "standard" as const,
  release_stage: "pre_ga" as const,
  applicability_reason: "Standard foundation closure fixture",
  environment: { os: "linux-x86_64", python: "3.13.5" },
  stdout_artifact: {
    path: "stdout.txt",
    hashes: { sha256: "ab".repeat(32), md5: null, sha512: null },
  },
  stderr_artifact: {
    path: "stderr.txt",
    hashes: { sha256: "ab".repeat(32), md5: null, sha512: null },
  },
  property_bag: null,
}

describe("EvidenceRecordSchema", () => {
  // -----------------------------------------------------------------------
  // Schema-level structural checks
  // -----------------------------------------------------------------------

  it("round-trips a minimal canonical envelope when parsed", () => {
    const result = EvidenceRecordSchema.parse(validRecord)
    expect(result).toEqual(validRecord)
  })

  it("rejects a missing required field when the envelope is parsed", () => {
    const { status: _, ...withoutStatus } = validRecord
    const result = EvidenceRecordSchema.safeParse(withoutStatus)
    expect(result.success).toBe(false)
  })

  it("rejects an invalid harness_id pattern", () => {
    const result = EvidenceRecordSchema.safeParse({
      ...validRecord,
      harness_id: "INVALID-HARNESS-01",
    })
    expect(result.success).toBe(false)
  })

  it("rejects an extra unknown field (.strict())", () => {
    const result = EvidenceRecordSchema.safeParse({
      ...validRecord,
      unknown_field: "should_fail",
    })
    expect(result.success).toBe(false)
  })

  it("rejects an absolute working_directory (schema pattern ^[^/])", () => {
    const result = EvidenceRecordSchema.safeParse({
      ...validRecord,
      invocation: { ...validRecord.invocation, working_directory: "/absolute/path" },
    })
    expect(result.success).toBe(false)
  })

  it("rejects an absolute artifact path (schema pattern ^[^/])", () => {
    const result = EvidenceRecordSchema.safeParse({
      ...validRecord,
      artifacts: [
        { path: "/etc/passwd", hashes: { sha256: "ab".repeat(32) } },
      ],
    })
    expect(result.success).toBe(false)
  })

  it("rejects environment missing 'os' key (catchall requires os)", () => {
    const result = EvidenceRecordSchema.safeParse({
      ...validRecord,
      environment: { python: "3.13.5" },
    })
    expect(result.success).toBe(false)
  })

  // -----------------------------------------------------------------------
  // Semantic validation — rules beyond JSON Schema expressibility
  // -----------------------------------------------------------------------

  it("rejects path traversal in working_directory", () => {
    const result = EvidenceRecordSchema.safeParse({
      ...validRecord,
      invocation: {
        ...validRecord.invocation,
        working_directory: "build/../outside",
      },
    })
    // Zod accepts (regex ^[^/] passes), semantic validator must reject
    expect(result.success).toBe(true)
    if (result.success) {
      const semanticErrors = validateEvidenceRecordSemantic(result.data)
      expect(semanticErrors.length).toBeGreaterThan(0)
      expect(semanticErrors[0]?.path).toBe("invocation.working_directory")
    }
  })

  it("rejects path traversal in artifact path", () => {
    const result = EvidenceRecordSchema.safeParse({
      ...validRecord,
      artifacts: [
        {
          path: "../outside/file.txt",
          hashes: { sha256: "ab".repeat(32) },
        },
      ],
    })
    expect(result.success).toBe(true)
    if (result.success) {
      const semanticErrors = validateEvidenceRecordSemantic(result.data)
      expect(semanticErrors.length).toBeGreaterThan(0)
      expect(semanticErrors[0]?.path).toMatch(/^artifacts\[0\]\.path$/)
    }
  })

  it("rejects duration_seconds mismatch with timestamps", () => {
    const result = EvidenceRecordSchema.safeParse({
      ...validRecord,
      invocation: {
        ...validRecord.invocation,
        duration_seconds: 999.9,
      },
    })
    // Zod only checks duration_seconds >= 0, so it accepts
    expect(result.success).toBe(true)
    if (result.success) {
      const semanticErrors = validateEvidenceRecordSemantic(result.data)
      expect(semanticErrors.length).toBeGreaterThan(0)
      expect(semanticErrors[0]?.path).toBe("invocation.duration_seconds")
    }
  })

  it("rejects pass status with a failing result", () => {
    const result = EvidenceRecordSchema.safeParse({
      ...validRecord,
      results: [
        { kind: "unit_test", passed: false, detail: "test_foo failed" },
      ],
    })
    expect(result.success).toBe(true)
    if (result.success) {
      const semanticErrors = validateEvidenceRecordSemantic(result.data)
      expect(semanticErrors.length).toBeGreaterThan(0)
      expect(semanticErrors[0]?.path).toBe("status")
    }
  })

  it("rejects fail status with exit_code=0 and no failing results", () => {
    const result = EvidenceRecordSchema.safeParse({
      ...validRecord,
      status: "fail" as const,
      invocation: { ...validRecord.invocation, exit_code: 0 },
      results: [
        { kind: "unit_test", passed: true, detail: "test_bar passed" },
      ],
    })
    expect(result.success).toBe(true)
    if (result.success) {
      const semanticErrors = validateEvidenceRecordSemantic(result.data)
      expect(semanticErrors.length).toBeGreaterThan(0)
      expect(semanticErrors[0]?.path).toBe("status")
    }
  })

  it("rejects not_applicable status with short applicability_reason", () => {
    const result = EvidenceRecordSchema.safeParse({
      ...validRecord,
      status: "not_applicable" as const,
      applicability_reason: "Too short",
    })
    // Zod only checks min(1), so it accepts
    expect(result.success).toBe(true)
    if (result.success) {
      const semanticErrors = validateEvidenceRecordSemantic(result.data)
      expect(semanticErrors.length).toBeGreaterThan(0)
      expect(semanticErrors[0]?.path).toBe("applicability_reason")
    }
  })

  // -----------------------------------------------------------------------
  // Valid fixture cross-language consistency
  // -----------------------------------------------------------------------

  it.each(
    fixtureFiles.filter((f) => f.startsWith("valid-")),
  )("valid fixture cross-language: %s", (fixtureFile) => {
    const fixturePath = join(FIXTURES_DIR, fixtureFile)
    const jsonStr = readFileSync(fixturePath, "utf-8")
    const data = JSON.parse(jsonStr) as unknown
    const result = EvidenceRecordSchema.safeParse(data)

    // Cross-language consistency: Python Pydantic and JS Zod must
    // reach the same verdict.  For valid fixtures, both must accept.
    expect(result.success).toBe(true)

    // Semantic validation must also pass for valid fixtures.
    // The parsed canonical bytes must also match Python's golden digest.
    if (result.success) {
      const semanticErrors = validateEvidenceRecordSemantic(result.data)
      expect(semanticErrors).toEqual([])

      const canonical = pythonCanonicalJson(canonicalizeEvidenceRecord(result.data))
      const digest = createHash("sha256").update(canonical).digest("hex")
      const goldenPath = fixturePath.replace(/\.json$/, ".canonical.sha256")
      const expected = readFileSync(goldenPath, "utf-8").trim()
      expect(digest).toBe(expected)
    }
  })

  // -----------------------------------------------------------------------
  // Invalid fixture — full pipeline (Zod + semantic) must reject all
  // -----------------------------------------------------------------------

  it.each(
    [...REQUIRED_INVALID_FIXTURES].sort(),
  )("full validation rejects invalid fixture: %s", (fixtureFile) => {
    const fixturePath = join(FIXTURES_DIR, fixtureFile)
    const jsonStr = readFileSync(fixturePath, "utf-8")
    const data = JSON.parse(jsonStr) as unknown

    // The full validation pipeline must reject every invalid fixture
    expect(isEvidenceRecordValid(data)).toBe(false)
  })

  // -----------------------------------------------------------------------
  // Fixture inventory gates
  // -----------------------------------------------------------------------

  it("fixture inventory matches the shared corpus", () => {
    const onDisk = new Set(
      readdirSync(FIXTURES_DIR).filter((f) => f.endsWith(".json")),
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
})
