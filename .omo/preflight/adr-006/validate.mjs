#!/usr/bin/env node
/**
 * ADR-006 foundation-contract preflight gate.
 *
 * Executes contract-specific validators for WF-P0-01..07. Negative fixtures
 * must carry an executable mutation and expected_failure_id. Missing mutation,
 * false positive acceptance, or wrong failure ID fails the process.
 */
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { basename, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

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

const HEX64 = /^[a-f0-9]{64}$/;
const CANONICAL_LAYERS = new Set([
  "Domain",
  "Platform",
  "Application",
  "Interfaces",
  "Adapters",
]);
const CANONICAL_MODULES = new Set([
  "graph",
  "policies",
  "decisions",
  "identity",
  "tenancy",
  "connections",
  "audit",
  "ingestion",
  "normalization",
  "projections",
  "approvals",
  "copilot",
  "control-room",
]);

/** @typedef {{ type: string, target: string, payload?: { field?: string, value?: any, invalid_value?: any, malformed?: any }, comment?: string }} MutationDescriptor */
/** @typedef {{ id: string, name: string, required_markers: string[], negative_scenarios: string[] }} Contract */
/** @typedef {{ gate: string, version: number, contracts: Contract[] }} Manifest */
/**
 * @typedef {{
 *   contract_id: string,
 *   kind: "positive" | "negative",
 *   scenario: string,
 *   assertion: string,
 *   payload?: object,
 *   mutation?: MutationDescriptor,
 *   expected_failure_id?: string
 * }} Fixture
 */
/** @typedef {{ success: boolean, failureId?: string }} ValidationResult */
/** @typedef {{ success: boolean, failureId?: string, result: string, contract_id: string, scenario: string }} FixtureObservation */

// ── Baselines (one abstract model per contract) ─────────────────────────────

/** @returns {object} */
export function baselineTaxonomy() {
  return {
    modules: [
      { name: "graph", layer: "Domain", io_dependencies: [] },
      { name: "policies", layer: "Domain", io_dependencies: [] },
      { name: "decisions", layer: "Domain", io_dependencies: [] },
      { name: "identity", layer: "Platform", io_dependencies: ["db"] },
      { name: "tenancy", layer: "Platform", io_dependencies: ["db"] },
      { name: "connections", layer: "Platform", io_dependencies: ["db"] },
      { name: "audit", layer: "Platform", io_dependencies: ["db"] },
      { name: "ingestion", layer: "Application", io_dependencies: [] },
      { name: "normalization", layer: "Application", io_dependencies: [] },
      { name: "projections", layer: "Application", io_dependencies: [] },
      { name: "approvals", layer: "Application", io_dependencies: [] },
      { name: "copilot", layer: "Application", io_dependencies: [] },
      { name: "control-room", layer: "Interfaces", io_dependencies: [] },
    ],
    ports: [{ name: "GitHubPort", owner: "application.ports" }],
  };
}

/** @returns {object} */
export function baselineDecisionRecord() {
  return {
    decision_id: "WF-DEC-0001",
    workspace_id: "WF-WS-0001",
    program_id: null,
    item_id: "WF-ITEM-0001",
    computed_at: "2026-07-12T03:20:00Z",
    causation_id: "WF-CAU-0001",
    correlation_id: "WF-COR-0001",
    normalized_snapshot_id: "WF-SNP-0001",
    normalized_snapshot_hash: "a".repeat(64),
    source_revision_set: { backend: "abc123" },
    graph_revision: "rev-1",
    policy_bundle_id: "WF-PB-0001",
    policy_bundle_hash: "b".repeat(64),
    ranking_pipeline_hash: "c".repeat(64),
    engine_version: "1.0.0",
    normalization_profile_version: "1.0.0",
    ready: true,
    ranking_position: 1,
  };
}

/** @returns {object} */
export function baselineTenancy() {
  return {
    workspace_id: "WF-WS-0001",
    rls_forced: true,
    bypassrls: false,
    transaction_local_workspace_context: true,
    scoped_namespaces: {
      cache: "ws:WF-WS-0001:cache",
      object: "ws:WF-WS-0001:object",
      job: "ws:WF-WS-0001:job",
      inbox: "ws:WF-WS-0001:inbox",
      audit: "ws:WF-WS-0001:audit",
      idempotency: "ws:WF-WS-0001:idempotency",
    },
    cross_workspace_access: false,
  };
}

/** @returns {object} */
export function baselineAudit() {
  return {
    envelope: {
      actor: "system",
      timestamp: "2026-07-12T03:20:00Z",
      ordering_key: 1,
      workspace_id: "WF-WS-0001",
    },
    payload_hash: "d".repeat(64),
    audit_anchor: {
      signature: "ed25519:valid-signature",
      worm: true,
      timestamp: "2026-07-12T03:20:00Z",
      segment_id: "seg-0001",
    },
  };
}

/** @returns {object} */
export function baselineTransaction() {
  return {
    inbox_committed: true,
    normalized_snapshot_committed: true,
    decision_records_committed: true,
    projection_committed: true,
    outbox_committed: true,
    cursor_advanced: true,
    atomic_commit: true,
    projection_fingerprint: "fp-current",
    outbox_fingerprint: "fp-current",
  };
}

/** @returns {object} */
export function baselineQueue() {
  return {
    claim_id: "claim-001",
    lease_owner: "worker-1",
    lease_state: "active",
    cas_version: 1,
    skip_locked: true,
    dead_letter: false,
    poison_replay: false,
    duplicate_claim: false,
  };
}

/** @returns {object} */
export function baselinePerformance() {
  return {
    valid_completions_ms: [100, 110, 120, 130, 140],
    failures: 2,
    timeouts: 1,
    report_failures: true,
    report_timeouts: true,
    outlier_removal_before_percentile: false,
    p95_ms: 140,
  };
}

/**
 * @param {string} contractId
 * @returns {object}
 */
export function getBaselineDocument(contractId) {
  switch (contractId) {
    case "WF-P0-01":
      return baselineTaxonomy();
    case "WF-P0-02":
      return baselineDecisionRecord();
    case "WF-P0-03":
      return baselineTenancy();
    case "WF-P0-04":
      return baselineAudit();
    case "WF-P0-05":
      return baselineTransaction();
    case "WF-P0-06":
      return baselineQueue();
    case "WF-P0-07":
      return baselinePerformance();
    default:
      throw new Error(`unknown contract baseline: ${contractId}`);
  }
}

// ── Mutation application ────────────────────────────────────────────────────

/**
 * @param {object} baselineDoc
 * @param {MutationDescriptor} mutation
 * @returns {object}
 */
export function applyMutation(baselineDoc, mutation) {
  const doc = structuredClone(baselineDoc);
  const path = mutation.target.replace(/^\$\.?/, "");

  if (mutation.type === "remove_field") {
    if (path === "" || path === "$") {
      return {};
    }
    const parts = path.split(".");
    let current = doc;
    for (let i = 0; i < parts.length - 1; i++) {
      if (current[parts[i]] == null || typeof current[parts[i]] !== "object") {
        return doc;
      }
      current = current[parts[i]];
    }
    delete current[parts[parts.length - 1]];
    return doc;
  }

  if (mutation.type === "add_invalid_field") {
    if (!mutation.payload) return doc;
    if (path === "" || path === "$") {
      doc[mutation.payload.field] = mutation.payload.value;
      return doc;
    }
    const parts = path.split(".");
    let current = doc;
    for (const part of parts) {
      if (current[part] == null || typeof current[part] !== "object") {
        return doc;
      }
      current = current[part];
    }
    current[mutation.payload.field] = mutation.payload.value;
    return doc;
  }

  if (mutation.type === "violate_constraint") {
    if (!mutation.payload) return doc;
    const parts = path.split(".");
    let current = doc;
    for (let i = 0; i < parts.length - 1; i++) {
      if (current[parts[i]] == null || typeof current[parts[i]] !== "object") {
        return doc;
      }
      current = current[parts[i]];
    }
    current[parts[parts.length - 1]] = mutation.payload.invalid_value;
    return doc;
  }

  if (mutation.type === "malform_structure") {
    if (!mutation.payload) return doc;
    const parts = path.split(".");
    let current = doc;
    for (let i = 0; i < parts.length - 1; i++) {
      if (current[parts[i]] == null || typeof current[parts[i]] !== "object") {
        return doc;
      }
      current = current[parts[i]];
    }
    current[parts[parts.length - 1]] = mutation.payload.malformed;
    return doc;
  }

  throw new Error(`unknown mutation type: ${mutation.type}`);
}

// ── Contract-specific validators ────────────────────────────────────────────

/**
 * @param {object} document
 * @returns {ValidationResult}
 */
export function validateTaxonomy(document) {
  if (!Array.isArray(document.modules)) {
    return { success: false, failureId: "missing_field_modules" };
  }
  if (!Array.isArray(document.ports)) {
    return { success: false, failureId: "missing_field_ports" };
  }

  const allowedRoot = new Set(["modules", "ports"]);
  for (const key of Object.keys(document)) {
    if (!allowedRoot.has(key)) {
      if (key === "io_dependency" || key === "domain_io") {
        return { success: false, failureId: "domain_io_dependency" };
      }
      if (key === "non_canonical_module") {
        return { success: false, failureId: "taxonomy_drift" };
      }
      if (key === "port_owner") {
        return { success: false, failureId: "wrong_port_owner" };
      }
      return { success: false, failureId: `extra_field_${key}` };
    }
  }

  for (const mod of document.modules) {
    if (!mod || typeof mod !== "object") {
      return { success: false, failureId: "malformed_module" };
    }
    if (!CANONICAL_MODULES.has(mod.name)) {
      return { success: false, failureId: "taxonomy_drift" };
    }
    if (!CANONICAL_LAYERS.has(mod.layer)) {
      return { success: false, failureId: "taxonomy_drift" };
    }
    if (
      mod.layer === "Domain" &&
      Array.isArray(mod.io_dependencies) &&
      mod.io_dependencies.length > 0
    ) {
      return { success: false, failureId: "domain_io_dependency" };
    }
  }

  for (const port of document.ports) {
    if (!port || typeof port !== "object") {
      return { success: false, failureId: "malformed_port" };
    }
    if (port.owner !== "application.ports") {
      return { success: false, failureId: "wrong_port_owner" };
    }
  }

  return { success: true };
}

/**
 * @param {object} document
 * @returns {ValidationResult}
 */
export function validateDecisionRecord(document) {
  const requiredFields = [
    "decision_id",
    "workspace_id",
    "program_id",
    "item_id",
    "computed_at",
    "causation_id",
    "correlation_id",
    "normalized_snapshot_id",
    "normalized_snapshot_hash",
    "source_revision_set",
    "graph_revision",
    "policy_bundle_id",
    "policy_bundle_hash",
    "ranking_pipeline_hash",
    "engine_version",
    "normalization_profile_version",
    "ready",
  ];

  for (const field of requiredFields) {
    if (!(field in document)) {
      return { success: false, failureId: `missing_field_${field}` };
    }
  }

  const allowedFields = new Set([...requiredFields, "ranking_position"]);
  for (const key of Object.keys(document)) {
    if (!allowedFields.has(key)) {
      return { success: false, failureId: `extra_field_${key}` };
    }
  }

  if (typeof document.workspace_id === "string" && document.workspace_id.length === 0) {
    return { success: false, failureId: "empty_workspace_id" };
  }

  if (
    typeof document.ranking_position === "number" &&
    document.ranking_position < 1
  ) {
    return { success: false, failureId: "invalid_ranking_position" };
  }

  if (
    document.source_revision_set == null ||
    typeof document.source_revision_set !== "object" ||
    Array.isArray(document.source_revision_set)
  ) {
    return { success: false, failureId: "malformed_source_revision_set" };
  }

  for (const hashField of [
    "normalized_snapshot_hash",
    "policy_bundle_hash",
    "ranking_pipeline_hash",
  ]) {
    if (
      typeof document[hashField] === "string" &&
      !HEX64.test(document[hashField])
    ) {
      return { success: false, failureId: `invalid_${hashField}` };
    }
  }

  return { success: true };
}

/**
 * @param {object} document
 * @returns {ValidationResult}
 */
export function validateTenancy(document) {
  const required = [
    "workspace_id",
    "rls_forced",
    "bypassrls",
    "transaction_local_workspace_context",
    "scoped_namespaces",
    "cross_workspace_access",
  ];
  for (const field of required) {
    if (!(field in document)) {
      if (field === "workspace_id") {
        return { success: false, failureId: "missing_workspace_context" };
      }
      return { success: false, failureId: `missing_field_${field}` };
    }
  }

  const allowed = new Set(required);
  for (const key of Object.keys(document)) {
    if (!allowed.has(key)) {
      if (key === "cross_workspace_access_flag") {
        return { success: false, failureId: "cross_scope_access" };
      }
      return { success: false, failureId: `extra_field_${key}` };
    }
  }

  if (
    typeof document.workspace_id !== "string" ||
    document.workspace_id.length === 0
  ) {
    return { success: false, failureId: "missing_workspace_context" };
  }
  if (document.rls_forced !== true) {
    return { success: false, failureId: "rls_not_forced" };
  }
  if (document.bypassrls === true) {
    return { success: false, failureId: "bypassrls_forbidden" };
  }
  if (document.transaction_local_workspace_context !== true) {
    return { success: false, failureId: "missing_workspace_context" };
  }
  if (document.cross_workspace_access === true) {
    return { success: false, failureId: "cross_scope_access" };
  }

  const namespaces = document.scoped_namespaces;
  if (!namespaces || typeof namespaces !== "object" || Array.isArray(namespaces)) {
    return { success: false, failureId: "malformed_scoped_namespaces" };
  }
  for (const ns of ["cache", "object", "job", "inbox", "audit", "idempotency"]) {
    if (!(ns in namespaces)) {
      return { success: false, failureId: `missing_namespace_${ns}` };
    }
  }

  return { success: true };
}

/**
 * @param {object} document
 * @returns {ValidationResult}
 */
export function validateAudit(document) {
  if (!("envelope" in document)) {
    return { success: false, failureId: "missing_field_envelope" };
  }
  if (
    document.envelope == null ||
    typeof document.envelope !== "object" ||
    Array.isArray(document.envelope)
  ) {
    return { success: false, failureId: "audit_envelope_tamper" };
  }
  if (!("payload_hash" in document)) {
    return { success: false, failureId: "missing_field_payload_hash" };
  }
  if (typeof document.payload_hash !== "string" || !HEX64.test(document.payload_hash)) {
    return { success: false, failureId: "invalid_payload_hash" };
  }
  if (!("audit_anchor" in document)) {
    return { success: false, failureId: "missing_anchor_proof" };
  }

  const allowed = new Set(["envelope", "payload_hash", "audit_anchor"]);
  for (const key of Object.keys(document)) {
    if (!allowed.has(key)) {
      return { success: false, failureId: `extra_field_${key}` };
    }
  }

  const anchor = document.audit_anchor;
  // Present but structurally rewritten (string/array/null) is envelope tamper,
  // not merely missing proof.
  if (anchor == null || typeof anchor !== "object" || Array.isArray(anchor)) {
    return { success: false, failureId: "audit_envelope_tamper" };
  }
  if (
    typeof anchor.signature !== "string" ||
    !anchor.signature.startsWith("ed25519:") ||
    anchor.signature === "ed25519:unsigned" ||
    anchor.signature === "unsigned"
  ) {
    return { success: false, failureId: "missing_anchor_proof" };
  }
  if (anchor.worm !== true) {
    return { success: false, failureId: "missing_anchor_proof" };
  }
  if (typeof anchor.timestamp !== "string" || Number.isNaN(Date.parse(anchor.timestamp))) {
    return { success: false, failureId: "audit_envelope_tamper" };
  }

  const envelope = document.envelope;
  for (const field of ["actor", "timestamp", "ordering_key", "workspace_id"]) {
    if (!(field in envelope)) {
      return { success: false, failureId: "audit_envelope_tamper" };
    }
  }

  return { success: true };
}

/**
 * @param {object} document
 * @returns {ValidationResult}
 */
export function validateTransaction(document) {
  const flags = [
    "inbox_committed",
    "normalized_snapshot_committed",
    "decision_records_committed",
    "projection_committed",
    "outbox_committed",
    "cursor_advanced",
    "atomic_commit",
  ];
  for (const field of flags) {
    if (!(field in document)) {
      return { success: false, failureId: `missing_field_${field}` };
    }
  }
  if (!("projection_fingerprint" in document) || !("outbox_fingerprint" in document)) {
    return { success: false, failureId: "missing_fingerprint" };
  }

  const allowed = new Set([...flags, "projection_fingerprint", "outbox_fingerprint"]);
  for (const key of Object.keys(document)) {
    if (!allowed.has(key)) {
      if (key === "stale_outbox_fingerprint") {
        return { success: false, failureId: "stale_outbox_fingerprint" };
      }
      if (key === "partial_commit_state") {
        return { success: false, failureId: "partial_internal_commit" };
      }
      return { success: false, failureId: `extra_field_${key}` };
    }
  }

  for (const field of flags) {
    if (document[field] !== true) {
      return { success: false, failureId: "partial_internal_commit" };
    }
  }

  if (document.projection_fingerprint !== document.outbox_fingerprint) {
    return { success: false, failureId: "stale_outbox_fingerprint" };
  }

  return { success: true };
}

/**
 * @param {object} document
 * @returns {ValidationResult}
 */
export function validateQueue(document) {
  const required = [
    "claim_id",
    "lease_owner",
    "lease_state",
    "cas_version",
    "skip_locked",
    "dead_letter",
    "poison_replay",
    "duplicate_claim",
  ];
  for (const field of required) {
    if (!(field in document)) {
      return { success: false, failureId: `missing_field_${field}` };
    }
  }

  const allowed = new Set(required);
  for (const key of Object.keys(document)) {
    if (!allowed.has(key)) {
      if (key === "duplicate_claim_id") {
        return { success: false, failureId: "duplicate_claim" };
      }
      return { success: false, failureId: `extra_field_${key}` };
    }
  }

  if (document.duplicate_claim === true) {
    return { success: false, failureId: "duplicate_claim" };
  }
  if (document.lease_state !== "active") {
    return { success: false, failureId: "lease_loss_completion" };
  }
  if (document.poison_replay === true && document.dead_letter !== true) {
    return { success: false, failureId: "poison_replay" };
  }
  if (document.skip_locked !== true) {
    return { success: false, failureId: "missing_skip_locked" };
  }
  if (typeof document.cas_version !== "number" || document.cas_version < 1) {
    return { success: false, failureId: "invalid_cas_version" };
  }

  return { success: true };
}

/**
 * @param {object} document
 * @returns {ValidationResult}
 */
export function validatePerformance(document) {
  const required = [
    "valid_completions_ms",
    "failures",
    "timeouts",
    "report_failures",
    "report_timeouts",
    "outlier_removal_before_percentile",
    "p95_ms",
  ];
  for (const field of required) {
    if (!(field in document)) {
      if (field === "failures" || field === "timeouts" || field === "report_failures") {
        return { success: false, failureId: "missing_failure_reporting" };
      }
      return { success: false, failureId: `missing_field_${field}` };
    }
  }

  const allowed = new Set(required);
  for (const key of Object.keys(document)) {
    if (!allowed.has(key)) {
      return { success: false, failureId: `extra_field_${key}` };
    }
  }

  if (!Array.isArray(document.valid_completions_ms)) {
    return { success: false, failureId: "malformed_completions" };
  }
  if (document.report_failures !== true || document.report_timeouts !== true) {
    return { success: false, failureId: "missing_failure_reporting" };
  }
  if (typeof document.failures !== "number" || typeof document.timeouts !== "number") {
    return { success: false, failureId: "missing_failure_reporting" };
  }
  if (document.outlier_removal_before_percentile === true) {
    return { success: false, failureId: "outlier_removal" };
  }

  return { success: true };
}

/**
 * @param {string} contractId
 * @param {object} document
 * @returns {ValidationResult}
 */
export function validateContract(contractId, document) {
  switch (contractId) {
    case "WF-P0-01":
      return validateTaxonomy(document);
    case "WF-P0-02":
      return validateDecisionRecord(document);
    case "WF-P0-03":
      return validateTenancy(document);
    case "WF-P0-04":
      return validateAudit(document);
    case "WF-P0-05":
      return validateTransaction(document);
    case "WF-P0-06":
      return validateQueue(document);
    case "WF-P0-07":
      return validatePerformance(document);
    default:
      return { success: false, failureId: `unknown_contract_${contractId}` };
  }
}

/**
 * Execute a negative fixture against its contract-specific baseline/validator.
 * @param {Fixture} fixture
 * @returns {FixtureObservation}
 */
export function executeContractFixture(fixture) {
  if (!fixture.mutation) {
    return {
      contract_id: fixture.contract_id,
      scenario: fixture.scenario,
      success: false,
      failureId: "unexecuted_fixture",
      result: "unexecuted_fixture",
    };
  }

  const baselineDoc = getBaselineDocument(fixture.contract_id);
  const mutatedDoc = applyMutation(baselineDoc, fixture.mutation);
  const validationResult = validateContract(fixture.contract_id, mutatedDoc);

  return {
    contract_id: fixture.contract_id,
    scenario: fixture.scenario,
    success: validationResult.success,
    failureId: validationResult.failureId,
    result: validationResult.success ? "false_positive" : "rejected_by_contract",
  };
}

// ── Manifest / documentation structural checks ──────────────────────────────

/** @param {string} path @returns {Promise<Manifest>} */
async function readManifest(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

/** @param {string} directory @returns {Promise<Fixture[]>} */
async function readFixtures(directory) {
  const entries = await readdir(directory);
  return Promise.all(
    entries
      .filter((entry) => entry.endsWith(".json"))
      .map(async (entry) => JSON.parse(await readFile(join(directory, entry), "utf8"))),
  );
}

/** @returns {Promise<string>} */
async function readCanonicalDocuments() {
  return (
    await Promise.all(sourceDocuments.map((path) => readFile(join(root, path), "utf8")))
  ).join("\n");
}

/**
 * @param {Manifest} manifest
 * @param {Fixture[]} positive
 * @param {Fixture[]} negative
 * @param {string} documents
 * @returns {string[]}
 */
export function validateManifestStructure(manifest, positive, negative, documents) {
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
    const scenarios = negative
      .filter((fixture) => fixture.contract_id === contract.id)
      .map((fixture) => fixture.scenario)
      .sort();
    const expectedScenarios = [...contract.negative_scenarios].sort();
    if (JSON.stringify(scenarios) !== JSON.stringify(expectedScenarios)) {
      failures.push(`${contract.id}: negative fixture scenarios do not match the manifest`);
    }
  }

  for (const fixture of [...positive, ...negative]) {
    if (!receivedIds.includes(fixture.contract_id)) {
      failures.push(`${basename(fixture.scenario)}: fixture references unknown ${fixture.contract_id}`);
    }
    if (!fixture.assertion || fixture.assertion.length === 0) {
      failures.push(`${fixture.contract_id}: fixture assertion must not be empty`);
    }
  }

  // Positive fixtures: the fixture's own payload must pass its own contract
  // validator. A hard-coded baseline is no longer a substitute; the fixture
  // is the executable proof of its own contract.
  for (const fixture of positive) {
    if (fixture.payload == null || typeof fixture.payload !== "object") {
      failures.push(
        `${fixture.contract_id}: positive fixture ${fixture.scenario} must carry an executable payload`,
      );
      continue;
    }
    const result = validateContract(fixture.contract_id, fixture.payload);
    if (!result.success) {
      failures.push(
        `${fixture.contract_id}: positive fixture ${fixture.scenario} rejected (${result.failureId ?? "unknown"})`,
      );
    }
  }

  return failures;
}

/**
 * Run negative fixture execution checks. Mutates failures array.
 * @param {Fixture[]} negative
 * @param {string[]} failures
 * @returns {Array<{contract_id: string, scenario: string, result: string, failure_id?: string, expected_failure_id?: string}>}
 */
export function executeNegativeFixtures(negative, failures) {
  return negative.map((fixture) => {
    if (!fixture.mutation) {
      failures.push(
        `${fixture.contract_id}: unexecuted fixture ${fixture.scenario}`,
      );
      return {
        contract_id: fixture.contract_id,
        scenario: fixture.scenario,
        result: "unexecuted_fixture",
      };
    }

    if (!fixture.expected_failure_id) {
      failures.push(
        `${fixture.contract_id}: missing expected_failure_id for ${fixture.scenario}`,
      );
      return {
        contract_id: fixture.contract_id,
        scenario: fixture.scenario,
        result: "missing_expected_failure_id",
      };
    }

    const observed = executeContractFixture(fixture);

    if (observed.success) {
      failures.push(
        `${fixture.contract_id}: false positive ${fixture.scenario}`,
      );
    }

    if (!observed.success && observed.failureId !== fixture.expected_failure_id) {
      failures.push(
        `${fixture.contract_id}: expected ${fixture.expected_failure_id}, observed ${observed.failureId}`,
      );
    }

    return {
      contract_id: fixture.contract_id,
      scenario: fixture.scenario,
      result: observed.result,
      failure_id: observed.failureId,
      expected_failure_id: fixture.expected_failure_id,
    };
  });
}

/**
 * Full gate evaluation.
 * @param {Manifest} manifest
 * @param {Fixture[]} positive
 * @param {Fixture[]} negative
 * @param {string} documents
 */
export function runGate(manifest, positive, negative, documents) {
  const failures = validateManifestStructure(manifest, positive, negative, documents);
  const negative_fixture_results = executeNegativeFixtures(negative, failures);
  return {
    gate: manifest.gate,
    status: failures.length === 0 ? "passed" : "failed",
    contracts: manifest.contracts.map((contract) => contract.id),
    positive_fixture_count: positive.length,
    negative_fixture_count: negative.length,
    negative_fixture_results,
    failures,
    scope:
      "pre-bootstrap documentation-contract validation with contract-specific executable mutations",
  };
}

/** CLI entry point */
export async function main() {
  const manifest = await readManifest(join(preflight, "manifest.json"));
  const positive = await readFixtures(join(preflight, "fixtures/positive"));
  const negative = await readFixtures(join(preflight, "fixtures/negative"));
  const documents = await readCanonicalDocuments();
  const result = runGate(manifest, positive, negative, documents);

  await mkdir(evidence, { recursive: true });
  await writeFile(join(evidence, "validation.json"), `${JSON.stringify(result, null, 2)}\n`);
  console.log(JSON.stringify(result, null, 2));
  process.exitCode = failuresExit(result.failures);
  return result;
}

/** @param {string[]} failures */
function failuresExit(failures) {
  return failures.length === 0 ? 0 : 1;
}

const isDirectRun =
  process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isDirectRun) {
  await main();
}
