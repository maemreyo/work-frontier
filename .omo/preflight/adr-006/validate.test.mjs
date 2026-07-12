/**
 * Behavioral tests for ADR-006 contract-specific preflight validators.
 * Run: node --test .omo/preflight/adr-006/validate.test.mjs
 */
import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { describe, test } from "node:test";

import {
  applyMutation,
  baselineDecisionRecord,
  executeContractFixture,
  executeNegativeFixtures,
  getBaselineDocument,
  runGate,
  validateContract,
  validateDecisionRecord,
  validateTaxonomy,
} from "./validate.mjs";

const root = join(import.meta.dirname, "../../..");
const preflight = join(root, ".omo/preflight/adr-006");

async function loadNegativeFixtures() {
  const dir = join(preflight, "fixtures/negative");
  const files = (await readdir(dir)).filter((f) => f.endsWith(".json"));
  return Promise.all(
    files.map(async (file) => JSON.parse(await readFile(join(dir, file), "utf8"))),
  );
}

describe("contract-specific baselines", () => {
  test("each WF-P0-* has a distinct baseline document shape", () => {
    const ids = Array.from({ length: 7 }, (_, i) => `WF-P0-0${i + 1}`);
    const shapes = ids.map((id) => Object.keys(getBaselineDocument(id)).sort().join(","));
    const unique = new Set(shapes);
    // DecisionRecord is unique; others must not all collapse to DecisionRecord
    assert.equal(unique.size, 7, `expected 7 distinct baselines, got ${unique.size}: ${shapes.join(" | ")}`);
  });

  test("every positive baseline passes its own validator", () => {
    for (let i = 1; i <= 7; i++) {
      const id = `WF-P0-0${i}`;
      const result = validateContract(id, getBaselineDocument(id));
      assert.equal(result.success, true, `${id} baseline should pass: ${result.failureId}`);
    }
  });
});

describe("negative fixture execution", () => {
  test("all on-disk negative fixtures reject with expected_failure_id", async () => {
    const fixtures = await loadNegativeFixtures();
    assert.equal(fixtures.length, 16);

    for (const fixture of fixtures) {
      assert.ok(fixture.mutation, `${fixture.scenario}: mutation required`);
      assert.ok(fixture.expected_failure_id, `${fixture.scenario}: expected_failure_id required`);

      const observed = executeContractFixture(fixture);
      assert.equal(
        observed.success,
        false,
        `${fixture.contract_id}/${fixture.scenario} must not be a false positive`,
      );
      assert.equal(
        observed.failureId,
        fixture.expected_failure_id,
        `${fixture.contract_id}/${fixture.scenario}: expected ${fixture.expected_failure_id}, got ${observed.failureId}`,
      );
      assert.equal(observed.result, "rejected_by_contract");
    }
  });

  test("unexecuted fixture (missing mutation) fails the gate with unexecuted_fixture", () => {
    const failures = [];
    const results = executeNegativeFixtures(
      [
        {
          contract_id: "WF-P0-02",
          kind: "negative",
          scenario: "missing-mutation",
          assertion: "must fail",
          // no mutation
        },
      ],
      failures,
    );

    assert.equal(results[0].result, "unexecuted_fixture");
    assert.ok(
      failures.some((f) => f.includes("unexecuted fixture")),
      `failures should include unexecuted: ${failures.join("; ")}`,
    );
  });

  test("false positive mutation fails the gate", () => {
    // No-op mutation: remove a non-existent path field effectively by
    // re-setting a valid value — use empty mutation that leaves baseline valid
    // by applying violate_constraint that sets ready=true (already true).
    const fixture = {
      contract_id: "WF-P0-02",
      kind: "negative",
      scenario: "noop-mutation",
      assertion: "should not pass silently",
      expected_failure_id: "missing_field_workspace_id",
      mutation: {
        type: "violate_constraint",
        target: "$.ready",
        payload: { invalid_value: true },
      },
    };

    const observed = executeContractFixture(fixture);
    assert.equal(observed.success, true, "noop mutation must leave document valid");
    assert.equal(observed.result, "false_positive");

    const failures = [];
    executeNegativeFixtures([fixture], failures);
    assert.ok(
      failures.some((f) => f.includes("false positive")),
      `failures should include false positive: ${failures.join("; ")}`,
    );
  });

  test("wrong expected_failure_id fails the gate", () => {
    const fixture = {
      contract_id: "WF-P0-02",
      kind: "negative",
      scenario: "wrong-id",
      assertion: "must match typed failure",
      expected_failure_id: "totally_wrong_id",
      mutation: {
        type: "remove_field",
        target: "$.source_revision_set",
      },
    };

    const observed = executeContractFixture(fixture);
    assert.equal(observed.success, false);
    assert.equal(observed.failureId, "missing_field_source_revision_set");

    const failures = [];
    executeNegativeFixtures([fixture], failures);
    assert.ok(
      failures.some((f) => f.includes("expected totally_wrong_id")),
      `failures should include ID mismatch: ${failures.join("; ")}`,
    );
  });
});

describe("contract-specific semantics", () => {
  test("WF-P0-01 rejects domain I/O, not as DecisionRecord extra field", () => {
    const baseline = getBaselineDocument("WF-P0-01");
    const mutated = applyMutation(baseline, {
      type: "violate_constraint",
      target: "$.modules.0.io_dependencies",
      payload: { invalid_value: ["db"] },
    });
    const result = validateTaxonomy(mutated);
    assert.equal(result.success, false);
    assert.equal(result.failureId, "domain_io_dependency");
  });

  test("WF-P0-03 rejects cross-scope access on tenancy model", () => {
    const baseline = getBaselineDocument("WF-P0-03");
    const mutated = applyMutation(baseline, {
      type: "violate_constraint",
      target: "$.cross_workspace_access",
      payload: { invalid_value: true },
    });
    const result = validateContract("WF-P0-03", mutated);
    assert.equal(result.success, false);
    assert.equal(result.failureId, "cross_scope_access");
  });

  test("WF-P0-04 rejects unsigned audit anchor", () => {
    const baseline = getBaselineDocument("WF-P0-04");
    const mutated = applyMutation(baseline, {
      type: "violate_constraint",
      target: "$.audit_anchor.signature",
      payload: { invalid_value: "unsigned" },
    });
    const result = validateContract("WF-P0-04", mutated);
    assert.equal(result.success, false);
    assert.equal(result.failureId, "missing_anchor_proof");
  });

  test("WF-P0-05 rejects partial internal commit", () => {
    const baseline = getBaselineDocument("WF-P0-05");
    const mutated = applyMutation(baseline, {
      type: "violate_constraint",
      target: "$.atomic_commit",
      payload: { invalid_value: false },
    });
    const result = validateContract("WF-P0-05", mutated);
    assert.equal(result.success, false);
    assert.equal(result.failureId, "partial_internal_commit");
  });

  test("WF-P0-06 rejects poison replay without dead-letter", () => {
    const baseline = getBaselineDocument("WF-P0-06");
    const mutated = applyMutation(baseline, {
      type: "violate_constraint",
      target: "$.poison_replay",
      payload: { invalid_value: true },
    });
    const result = validateContract("WF-P0-06", mutated);
    assert.equal(result.success, false);
    assert.equal(result.failureId, "poison_replay");
  });

  test("WF-P0-07 rejects outlier removal before percentiles", () => {
    const baseline = getBaselineDocument("WF-P0-07");
    const mutated = applyMutation(baseline, {
      type: "violate_constraint",
      target: "$.outlier_removal_before_percentile",
      payload: { invalid_value: true },
    });
    const result = validateContract("WF-P0-07", mutated);
    assert.equal(result.success, false);
    assert.equal(result.failureId, "outlier_removal");
  });

  test("DecisionRecord validator still rejects missing workspace_id", () => {
    const doc = baselineDecisionRecord();
    delete doc.workspace_id;
    const result = validateDecisionRecord(doc);
    assert.equal(result.success, false);
    assert.equal(result.failureId, "missing_field_workspace_id");
  });
});

describe("full gate integration", () => {
  test("on-disk fixtures pass the full gate", async () => {
    const manifest = JSON.parse(
      await readFile(join(preflight, "manifest.json"), "utf8"),
    );
    const positiveDir = join(preflight, "fixtures/positive");
    const positiveFiles = (await readdir(positiveDir)).filter((f) => f.endsWith(".json"));
    const positive = await Promise.all(
      positiveFiles.map(async (f) =>
        JSON.parse(await readFile(join(positiveDir, f), "utf8")),
      ),
    );
    const negative = await loadNegativeFixtures();

    // Minimal document text that includes all required markers from manifest
    const documents = manifest.contracts
      .flatMap((c) => c.required_markers)
      .join("\n");

    const result = runGate(manifest, positive, negative, documents);
    assert.equal(
      result.status,
      "passed",
      `gate failures: ${result.failures.join("; ")}`,
    );
    assert.equal(result.failures.length, 0);
    assert.equal(result.negative_fixture_results.length, 16);
    for (const r of result.negative_fixture_results) {
      assert.equal(r.result, "rejected_by_contract");
    }
  });
});
