import { describe, expect, it, beforeEach, afterEach } from "vitest";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { EvidenceCollector } from "../../lib/evidence-collector";

describe("EvidenceCollector", () => {
  let tempDir: string;

  beforeEach(() => {
    tempDir = mkdtempSync(join(tmpdir(), "evidence-test-"));
  });

  afterEach(() => {
    rmSync(tempDir, { recursive: true, force: true });
  });

  it("initializes and captures 40-character commit SHA", () => {
    const collector = new EvidenceCollector(
      "WF-HAR-TYPESCRIPT-01",
      "vitest",
      "2.1.0"
    );

    const startTime = new Date();
    const endTime = new Date(startTime.getTime() + 1000);
    const record = collector.build("vitest run", 0, startTime, endTime);

    expect(record.tool.commit_sha).toMatch(/^[0-9a-f]{40}$/);
  });

  it("accumulates multiple results via addResult", () => {
    const collector = new EvidenceCollector(
      "WF-HAR-TYPESCRIPT-02",
      "vitest",
      "2.1.0"
    );

    collector.addResult("test", true, "test_foo passed");
    collector.addResult("test", true, "test_bar passed");
    collector.addResult("lint", false, "line too long");

    const startTime = new Date();
    const endTime = new Date(startTime.getTime() + 1000);
    const record = collector.build("vitest run", 0, startTime, endTime);

    expect(record.results).toHaveLength(3);
    expect(record.results[0]).toEqual({
      kind: "test",
      passed: true,
      detail: "test_foo passed",
    });
    expect(record.results[1]).toEqual({
      kind: "test",
      passed: true,
      detail: "test_bar passed",
    });
    expect(record.results[2]).toEqual({
      kind: "lint",
      passed: false,
      detail: "line too long",
    });
  });

  it("computes SHA-256 hash for artifacts via addArtifact", () => {
    const collector = new EvidenceCollector(
      "WF-HAR-TYPESCRIPT-03",
      "vitest",
      "2.1.0"
    );

    const artifactPath = join(tempDir, "test-artifact.txt");
    writeFileSync(artifactPath, "test content");

    collector.addArtifact(artifactPath);

    const startTime = new Date();
    const endTime = new Date(startTime.getTime() + 1000);
    const record = collector.build("vitest run", 0, startTime, endTime);

    expect(record.artifacts).toHaveLength(1);
    expect(record.artifacts[0]!.path).toBe(artifactPath);
    expect(record.artifacts[0]!.hashes?.['sha256']).toBe(
      "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"
    );
  });

  it("sets status to pass when exit_code is 0 and all results passed", () => {
    const collector = new EvidenceCollector(
      "WF-HAR-TYPESCRIPT-04",
      "vitest",
      "2.1.0"
    );

    collector.addResult("test", true);
    collector.addResult("test", true);

    const startTime = new Date();
    const endTime = new Date(startTime.getTime() + 1000);
    const record = collector.build("vitest run", 0, startTime, endTime);

    expect(record.status).toBe("pass");
    expect(record.invocation.exit_code).toBe(0);
  });

  it("sets status to fail when any result failed", () => {
    const collector = new EvidenceCollector(
      "WF-HAR-TYPESCRIPT-05",
      "vitest",
      "2.1.0"
    );

    collector.addResult("test", true);
    collector.addResult("test", false, "assertion failed");

    const startTime = new Date();
    const endTime = new Date(startTime.getTime() + 1000);
    const record = collector.build("vitest run", 0, startTime, endTime);

    expect(record.status).toBe("fail");
  });

  it("sets status to fail when exit_code is non-zero", () => {
    const collector = new EvidenceCollector(
      "WF-HAR-TYPESCRIPT-06",
      "vitest",
      "2.1.0"
    );

    collector.addResult("test", true);

    const startTime = new Date();
    const endTime = new Date(startTime.getTime() + 1000);
    const record = collector.build("vitest run", 1, startTime, endTime);

    expect(record.status).toBe("fail");
    expect(record.invocation.exit_code).toBe(1);
  });

  it("calculates duration_seconds correctly", () => {
    const collector = new EvidenceCollector(
      "WF-HAR-TYPESCRIPT-07",
      "vitest",
      "2.1.0"
    );

    const startTime = new Date("2026-07-12T00:00:00.000Z");
    const endTime = new Date("2026-07-12T00:00:05.500Z");
    const record = collector.build("vitest run", 0, startTime, endTime);

    expect(record.invocation.duration_seconds).toBe(5.5);
  });

  it("includes working_directory when provided", () => {
    const collector = new EvidenceCollector(
      "WF-HAR-TYPESCRIPT-08",
      "vitest",
      "2.1.0"
    );

    const startTime = new Date();
    const endTime = new Date(startTime.getTime() + 1000);
    const record = collector.build(
      "vitest run",
      0,
      startTime,
      endTime,
      "/path/to/workdir"
    );

    expect(record.invocation.working_directory).toBe("/path/to/workdir");
  });

  it("omits working_directory when not provided", () => {
    const collector = new EvidenceCollector(
      "WF-HAR-TYPESCRIPT-09",
      "vitest",
      "2.1.0"
    );

    const startTime = new Date();
    const endTime = new Date(startTime.getTime() + 1000);
    const record = collector.build("vitest run", 0, startTime, endTime);

    expect(record.invocation.working_directory).toBeUndefined();
  });

  it("produces valid EvidenceRecord structure that serializes to JSON", () => {
    const collector = new EvidenceCollector(
      "WF-HAR-TYPESCRIPT-10",
      "vitest",
      "2.1.0"
    );

    collector.addResult("test", true, "all tests passed");

    const startTime = new Date();
    const endTime = new Date(startTime.getTime() + 1000);
    const record = collector.build("vitest run", 0, startTime, endTime);

    expect(record.schema_version).toBe("1.0.0");
    expect(record.harness_id).toBe("WF-HAR-TYPESCRIPT-10");
    expect(record.status).toBe("pass");
    expect(record.tool.name).toBe("vitest");
    expect(record.tool.version).toBe("2.1.0");
    expect(record.invocation.command).toBe("vitest run");
    expect(record.invocation.start_time).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(record.invocation.end_time).toMatch(/^\d{4}-\d{2}-\d{2}T/);

    // Verify JSON serialization works
    const json = JSON.stringify(record);
    expect(() => JSON.parse(json)).not.toThrow();
  });

  it("handles empty results array correctly", () => {
    const collector = new EvidenceCollector(
      "WF-HAR-TYPESCRIPT-11",
      "vitest",
      "2.1.0"
    );

    // No results added

    const startTime = new Date();
    const endTime = new Date(startTime.getTime() + 1000);
    const record = collector.build("vitest run", 0, startTime, endTime);

    expect(record.results).toEqual([]);
    expect(record.status).toBe("pass"); // No results, exit_code 0 → pass
  });

  it("accumulates multiple artifacts via addArtifact", () => {
    const collector = new EvidenceCollector(
      "WF-HAR-TYPESCRIPT-12",
      "vitest",
      "2.1.0"
    );

    const artifact1 = join(tempDir, "artifact1.txt");
    const artifact2 = join(tempDir, "artifact2.txt");
    writeFileSync(artifact1, "content 1");
    writeFileSync(artifact2, "content 2");

    collector.addArtifact(artifact1);
    collector.addArtifact(artifact2);

    const startTime = new Date();
    const endTime = new Date(startTime.getTime() + 1000);
    const record = collector.build("vitest run", 0, startTime, endTime);

    expect(record.artifacts).toHaveLength(2);
    expect(record.artifacts[0]!.path).toBe(artifact1);
    expect(record.artifacts[1]!.path).toBe(artifact2);
    expect(record.artifacts[0]!.hashes?.['sha256']).toMatch(/^[0-9a-f]{64}$/);
    expect(record.artifacts[1]!.hashes?.['sha256']).toMatch(/^[0-9a-f]{64}$/);
  });

  it("includes optional detail in addResult", () => {
    const collector = new EvidenceCollector(
      "WF-HAR-TYPESCRIPT-13",
      "vitest",
      "2.1.0"
    );

    collector.addResult("test", true, "test passed with flying colors");
    collector.addResult("test", true); // No detail

    const startTime = new Date();
    const endTime = new Date(startTime.getTime() + 1000);
    const record = collector.build("vitest run", 0, startTime, endTime);

    expect(record.results[0]!.detail).toBe("test passed with flying colors");
    expect(record.results[1]!.detail).toBeUndefined();
  });
});
