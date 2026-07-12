import { describe, test, expect } from "vitest";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const root = join(import.meta.dirname, "../../..");
const validateMjs = join(root, ".omo/preflight/adr-006/validate.mjs");

/**
 * PROVES: validate.mjs line 92 hardcodes `result: "rejected_by_contract"`
 * for ALL 16 negative fixtures WITHOUT actually:
 *   1. Reading mutation descriptors from fixture files
 *   2. Applying mutations to baseline documents
 *   3. Running any contract validator (Zod schema or equivalent)
 *   4. Observing actual validation failure
 *
 * The validate() function (lines 41-78) only checks structural things:
 * contract IDs match manifest, required markers exist in docs, fixture counts
 * are correct, scenarios match manifest. It NEVER executes mutations.
 *
 * Line 92 then unconditionally assigns every negative fixture:
 *   { contract_id, scenario, result: "rejected_by_contract" }
 *
 * This test FAILS (RED state) because validate.mjs lacks mutation execution
 * infrastructure. After Task 10 implements real mutation injection + contract
 * validation, this test will PASS.
 */
describe("Preflight Validator — negative fixture false positives", () => {
  test("validate.mjs has no mutation execution — all negative results are hardcoded", async () => {
    const source = await readFile(validateMjs, "utf8");

    // ── PROOF 1: No mutation application function exists ──
    //
    // A correct implementation needs a function that takes a baseline document
    // and a mutation descriptor (per mutation-schema.json) and produces a
    // mutated copy. None of these patterns exist in the source:
    const hasMutationApplication =
      source.includes("applyMutation") ||
      source.includes("executeMutation") ||
      source.includes("mutateDocument") ||
      source.includes("apply_mutation") ||
      source.includes("applyMutation");

    // RED FAIL: validate.mjs has zero mutation application code.
    // All 16 negative fixtures get "rejected_by_contract" without any
    // mutation ever being applied to a baseline document.
    expect(hasMutationApplication).toBe(true);
  });

  test("validate.mjs has no contract validation against mutated documents", async () => {
    const source = await readFile(validateMjs, "utf8");

    // ── PROOF 2: No contract validator is invoked for negative fixtures ──
    //
    // After applying a mutation, the validator must run the contract's schema
    // (Zod, JSON Schema, etc.) to determine if the mutation actually violates
    // the contract. None of these validation patterns exist:
    const hasContractValidation =
      source.includes("schema.parse") ||
      source.includes("safeParse") ||
      source.includes("validateContract") ||
      source.includes("runContractValidator") ||
      source.includes("checkContract") ||
      source.includes("zod");

    // RED FAIL: No contract validation runs. The result is predetermined,
    // not derived from actual validation of mutated documents.
    expect(hasContractValidation).toBe(true);
  });

  test("Fixture typedef excludes mutation field — validator was never designed to process mutations", async () => {
    const source = await readFile(validateMjs, "utf8");

    // ── PROOF 3: The Fixture type has no mutation field ──
    //
    // Line 19 defines:
    //   {{ contract_id: string, kind: "positive" | "negative", scenario: string, assertion: string }}
    //
    // This typedef omits `mutation` entirely, even though mutation-schema.json
    // defines the mutation descriptor format. The validator was never designed
    // to read or execute mutations — the mutation schema is orphaned.
    //
    // A correct Fixture type would be:
    //   {{ contract_id: string, kind: "positive" | "negative", scenario: string,
    //      assertion: string, mutation?: MutationDescriptor }}
    //
    // RED FAIL: The typedef contains no reference to mutation, proving the
    // validator ignores mutation descriptors entirely.
    expect(source).toMatch(/mutation\s*[?:]/);
  });

  test("negative fixtures on disk have no mutation field — schema is orphaned", async () => {
    const negativeDir = join(root, ".omo/preflight/adr-006/fixtures/negative");
    const { readdirSync } = await import("node:fs");
    const files = readdirSync(negativeDir).filter((f) => f.endsWith(".json"));

    // Load every negative fixture from disk
    const fixtures = await Promise.all(
      files.map(async (file) => {
        const content = await readFile(join(negativeDir, file), "utf8");
        return { file, parsed: JSON.parse(content) };
      }),
    );

    // None of the 16 negative fixtures contain a mutation descriptor,
    // even though mutation-schema.json exists and documents the format.
    // The schema is defined but never used.
    for (const { file, parsed } of fixtures) {
      // RED FAIL: No fixture has a mutation field.
      // This proves that even the test data was never wired up for
      // real mutation execution — the entire negative fixture system
      // is structural bookkeeping, not functional validation.
      expect(parsed).toHaveProperty("mutation");
    }
  });

  test("line 92 hardcodes rejected_by_contract — no fixture-specific determination", async () => {
    const source = await readFile(validateMjs, "utf8");

    // ── PROOF 4: The result construction is a simple map with a string literal ──
    //
    // Line 92:
    //   negative_fixture_results: negative.map((fixture) => ({
    //     contract_id: fixture.contract_id,
    //     scenario: fixture.scenario,
    //     result: "rejected_by_contract"
    //   }))
    //
    // This is an unconditional string assignment. There is no if/else,
    // no try/catch around mutation execution, no schema validation —
    // every fixture gets the same result regardless of its scenario,
    // mutation descriptor (if it had one), or any contract definition.
    //
    // A correct implementation would be something like:
    //   negative_fixture_results: negative.map((fixture) => ({
    //     contract_id: fixture.contract_id,
    //     scenario: fixture.scenario,
    //     result: executeAndValidate(fixture, baselineRecord)
    //       ? "rejected_by_contract"
    //       : "false_positive"
    //   }))
    //
    // RED FAIL: The source contains the hardcoded string literal with no
    // conditional logic around it.
    expect(source).toMatch(/result:\s*"rejected_by_contract"/);

    // Prove there is no conditional logic between the map and the result string.
    // A correct implementation would have a function call or ternary that
    // determines the result based on actual validation.
    const line92Region = source.substring(
      source.indexOf("negative_fixture_results"),
      source.indexOf("negative_fixture_results") + 300,
    );

    // The result is always "rejected_by_contract" — no ternary, no function call,
    // no conditional that could return "false_positive" for a fixture that
    // passes validation after mutation.
    //
    // RED FAIL: Confirms the hardcoded string with no result determination logic.
    expect(line92Region).not.toMatch(/false_positive/);
  });
});
