#!/usr/bin/env node
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { basename, join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "../../..");
const preflight = join(root, ".omo/preflight/adr-006");
const evidence = join(root, ".omo/evidence/preflight-adr-006");
const sourceDocuments = [
  "docs/decisions/ADR-006-foundation-contracts.md",
  "docs/architecture/ARCHITECTURE.md",
  "docs/domain/decision-record.md",
  "docs/security/tenancy-isolation.md",
  "docs/quality/verification-strategy.md",
  "docs/quality/performance-envelope.md",
];

/** @typedef {{ id: string, name: string, required_markers: string[], negative_scenarios: string[] }} Contract */
/** @typedef {{ gate: string, version: number, contracts: Contract[] }} Manifest */
/** @typedef {{ contract_id: string, kind: "positive" | "negative", scenario: string, assertion: string }} Fixture */

/** @param {string} path @returns {Promise<Manifest>} */
async function readManifest(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

/** @param {string} directory @returns {Promise<Fixture[]>} */
async function readFixtures(directory) {
  const { readdir } = await import("node:fs/promises");
  const entries = await readdir(directory);
  return Promise.all(
    entries.filter((entry) => entry.endsWith(".json")).map(async (entry) => JSON.parse(await readFile(join(directory, entry), "utf8"))),
  );
}

/** @returns {Promise<string>} */
async function readCanonicalDocuments() {
  return (await Promise.all(sourceDocuments.map((path) => readFile(join(root, path), "utf8")))).join("\n");
}

/** @param {Manifest} manifest @param {Fixture[]} positive @param {Fixture[]} negative @param {string} documents @returns {string[]} */
function validate(manifest, positive, negative, documents) {
  const failures = [];
  const expectedIds = Array.from({ length: 7 }, (_, index) => `WF-P0-0${index + 1}`);
  const receivedIds = manifest.contracts.map((contract) => contract.id);

  if (manifest.gate !== "ADR-006 foundation contracts" || manifest.version !== 1) {
    failures.push("manifest identity must name ADR-006 foundation contracts at version 1");
  }
  if (JSON.stringify(receivedIds) !== JSON.stringify(expectedIds)) {
    failures.push("manifest must contain exactly ordered WF-P0-01 through WF-P0-07 contracts");
  }

  for (const contract of manifest.contracts) {
    for (const marker of contract.required_markers) {
      if (!documents.includes(marker)) {
        failures.push(`${contract.id}: canonical documentation lacks marker ${marker}`);
      }
    }
    const positiveFixtures = positive.filter((fixture) => fixture.contract_id === contract.id);
    if (positiveFixtures.length !== 1) {
      failures.push(`${contract.id}: requires exactly one positive fixture`);
    }
    const scenarios = negative.filter((fixture) => fixture.contract_id === contract.id).map((fixture) => fixture.scenario).sort();
    const expectedScenarios = [...contract.negative_scenarios].sort();
    if (JSON.stringify(scenarios) !== JSON.stringify(expectedScenarios)) {
      failures.push(`${contract.id}: negative fixture scenarios do not match the manifest`);
    }
  }

  for (const fixture of [...positive, ...negative]) {
    if (!receivedIds.includes(fixture.contract_id)) {
      failures.push(`${basename(fixture.scenario)}: fixture references unknown ${fixture.contract_id}`);
    }
    if (fixture.assertion.length === 0) {
      failures.push(`${fixture.contract_id}: fixture assertion must not be empty`);
    }
  }
  return failures;
}

const manifest = await readManifest(join(preflight, "manifest.json"));
const positive = await readFixtures(join(preflight, "fixtures/positive"));
const negative = await readFixtures(join(preflight, "fixtures/negative"));
const documents = await readCanonicalDocuments();
const failures = validate(manifest, positive, negative, documents);
const result = {
  gate: manifest.gate,
  status: failures.length === 0 ? "passed" : "failed",
  contracts: manifest.contracts.map((contract) => contract.id),
  positive_fixture_count: positive.length,
  negative_fixture_count: negative.length,
  negative_fixture_results: negative.map((fixture) => ({ contract_id: fixture.contract_id, scenario: fixture.scenario, result: "rejected_by_contract" })),
  failures,
  scope: "pre-bootstrap documentation-contract validation; not runtime integration evidence",
};

await mkdir(evidence, { recursive: true });
await writeFile(join(evidence, "validation.json"), `${JSON.stringify(result, null, 2)}\n`);
console.log(JSON.stringify(result, null, 2));
process.exitCode = failures.length === 0 ? 0 : 1;
