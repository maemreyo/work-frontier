/**
 * Non-generated semantic validation for EvidenceRecord.
 *
 * This module enforces business rules that the generated Zod schema
 * cannot express (JSON Schema if/then, PurePosixPath traversal
 * detection, arithmetic constraints, cross-field contradictions).
 *
 * Mirrors Pydantic field_validator and model_validator rules from
 * backend/src/work_frontier/contracts/evidence_record.py exactly.
 *
 * Usage (two-step pipeline):
 *   1. const schemaResult = EvidenceRecordSchema.safeParse(unknownInput)
 *   2. if (schemaResult.success) {
 *        const errors = validateEvidenceRecordSemantic(schemaResult.data)
 *      }
 *   3. Accept only when both layers pass.
 */

import { EvidenceRecordSchema } from "./evidence-record.generated"
import type { EvidenceRecord } from "./evidence-record.generated"

export interface SemanticValidationError {
  /** Dot-notation path to the offending field */
  path: string
  /** Human-readable explanation */
  message: string
}

/**
 * Check for path-traversal `..` segments (mirrors PurePosixPath check).
 */
function hasTraversal(path: string): boolean {
  return path.split("/").includes("..")
}

/**
 * Apply semantic validation rules to a structurally-valid EvidenceRecord.
 *
 * Returns an array of errors (empty array = valid).
 * Rules mirror Pydantic validators in evidence_record.py:
 *   - Invocation.working_directory: no `..` segments
 *   - Artifact.path: no `..` segments
 *   - Invocation.validate_duration: duration_seconds within 0.001s of delta
 *   - validate_status_contradictions: pass + failing result, fail-zero + no failing
 *   - validate_applicability_reason: not_applicable requires >=10 non-whitespace chars
 */
export function validateEvidenceRecordSemantic(
  record: EvidenceRecord,
): SemanticValidationError[] {
  const errors: SemanticValidationError[] = []

  // -----------------------------------------------------------------------
  // 1. Path traversal in working_directory
  // -----------------------------------------------------------------------
  if (hasTraversal(record.invocation.working_directory)) {
    errors.push({
      path: "invocation.working_directory",
      message: `working_directory must not contain '..' traversal: ${record.invocation.working_directory}`,
    })
  }

  // -----------------------------------------------------------------------
  // 2. Path traversal in artifact paths
  // -----------------------------------------------------------------------
  for (const [i, artifact] of (record.artifacts ?? []).entries()) {
    if (hasTraversal(artifact.path)) {
      errors.push({
        path: `artifacts[${i}].path`,
        message: `artifact path must not contain '..' traversal: ${artifact.path}`,
      })
    }
  }

  // -----------------------------------------------------------------------
  // 3. Path traversal in stdout/stderr artifacts
  // -----------------------------------------------------------------------
  if (hasTraversal(record.stdout_artifact.path)) {
    errors.push({
      path: "stdout_artifact.path",
      message: `artifact path must not contain '..' traversal: ${record.stdout_artifact.path}`,
    })
  }
  if (hasTraversal(record.stderr_artifact.path)) {
    errors.push({
      path: "stderr_artifact.path",
      message: `artifact path must not contain '..' traversal: ${record.stderr_artifact.path}`,
    })
  }

  // -----------------------------------------------------------------------
  // 4. Duration mismatch (end_time - start_time vs duration_seconds)
  // -----------------------------------------------------------------------
  const startMs = new Date(record.invocation.start_time).getTime()
  const endMs = new Date(record.invocation.end_time).getTime()
  const expectedDuration = (endMs - startMs) / 1000
  if (Math.abs(record.invocation.duration_seconds - expectedDuration) > 0.001) {
    errors.push({
      path: "invocation.duration_seconds",
      message: `duration_seconds (${record.invocation.duration_seconds}) does not match end_time - start_time (${expectedDuration})`,
    })
  }

  // -----------------------------------------------------------------------
  // 5. Pass status with failing results
  // -----------------------------------------------------------------------
  if (record.status === "pass") {
    for (const r of record.results ?? []) {
      if (!r.passed) {
        errors.push({
          path: "status",
          message: `status is 'pass' but result '${r.kind}' has passed=false`,
        })
      }
    }
  }

  // -----------------------------------------------------------------------
  // 6. Fail with exit_code=0 and no failing results
  // -----------------------------------------------------------------------
  if (record.status === "fail" && record.invocation.exit_code === 0) {
    const hasFailing = (record.results ?? []).some((r) => !r.passed)
    if (!hasFailing) {
      errors.push({
        path: "status",
        message:
          "status is 'fail' with exit_code=0 but no result has passed=false",
      })
    }
  }

  // -----------------------------------------------------------------------
  // 7. not_applicable requires >=10 non-whitespace characters
  // -----------------------------------------------------------------------
  if (record.status === "not_applicable") {
    if (record.applicability_reason.trim().length < 10) {
      errors.push({
        path: "applicability_reason",
        message: `applicability_reason for not_applicable must be a substantive explanation (got ${record.applicability_reason.length} chars)`,
      })
    }
  }

  return errors
}

/**
 * Run the full validation pipeline: parse the JSON object as unknown with
 * EvidenceRecordSchema, then if structurally valid, apply the semantic
 * validator.  Returns true only when both layers accept.
 */
export function isEvidenceRecordValid(data: unknown): boolean {
  const schemaResult = EvidenceRecordSchema.safeParse(data)
  if (!schemaResult.success) return false
  return validateEvidenceRecordSemantic(schemaResult.data).length === 0
}
