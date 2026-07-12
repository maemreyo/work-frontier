/**
 * Evidence collector for verification harness execution.
 *
 * Builds EvidenceRecord instances by accumulating results and artifacts during
 * harness execution, then finalizing with invocation metadata.
 */

import { execSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

type Invocation = {
  command: string;
  exit_code: number;
  working_directory?: string;
  start_time: string; // ISO 8601
  end_time: string; // ISO 8601
  duration_seconds: number;
};

type Tool = {
  name: string;
  version: string;
  commit_sha: string; // 40 hex chars
};

type Result = {
  kind: string;
  passed: boolean;
  detail?: string;
};

type Artifact = {
  path: string;
  hashes?: Record<string, string>;
};

type EvidenceRecord = {
  schema_version: "1.0.0";
  harness_id: string; // WF-HAR-{CATEGORY}-{NN}
  status: "pass" | "fail" | "skip";
  invocation: Invocation;
  tool: Tool;
  artifacts: Artifact[];
  results: Result[];
  property_bag?: Record<string, unknown>;
};

/**
 * Collects evidence during harness execution and builds final record.
 *
 * Usage:
 *   const collector = new EvidenceCollector(
 *     "WF-HAR-TYPESCRIPT-01",
 *     "vitest",
 *     "2.1.0"
 *   );
 *   collector.addResult("test", true, "test_foo passed");
 *   collector.addArtifact("coverage.xml");
 *   const record = collector.build(
 *     "vitest run",
 *     0,
 *     new Date(),
 *     new Date()
 *   );
 */
export class EvidenceCollector {
  private readonly harnessId: string;
  private readonly toolName: string;
  private readonly toolVersion: string;
  private readonly commitSha: string;
  private readonly results: Result[] = [];
  private readonly artifacts: Artifact[] = [];

  /**
   * Initialize collector with harness and tool metadata.
   *
   * @param harnessId - Harness identifier matching WF-HAR-{CATEGORY}-{NN}
   * @param toolName - Name of the tool being executed
   * @param toolVersion - Version string of the tool
   */
  constructor(harnessId: string, toolName: string, toolVersion: string) {
    this.harnessId = harnessId;
    this.toolName = toolName;
    this.toolVersion = toolVersion;
    this.commitSha = this.getCommitSha();
  }

  /**
   * Get current git commit SHA.
   *
   * @returns 40-character hexadecimal commit SHA
   * @throws Error if git command fails
   */
  private getCommitSha(): string {
    return execSync("git rev-parse HEAD", { encoding: "utf-8" }).trim();
  }

  /**
   * Add a test result or finding.
   *
   * @param kind - Result type identifier (e.g., "test", "lint", "type-check")
   * @param passed - Whether this specific result passed
   * @param detail - Optional human-readable detail about the result
   */
  addResult(kind: string, passed: boolean, detail?: string): void {
    if (detail !== undefined) {
      this.results.push({ kind, passed, detail });
    } else {
      this.results.push({ kind, passed });
    }
  }

  /**
   * Add an artifact with SHA-256 hash.
   *
   * @param path - Path to the artifact file
   */
  addArtifact(path: string): void {
    const content = readFileSync(path);
    const sha256 = createHash("sha256").update(content).digest("hex");
    this.artifacts.push({ path, hashes: { sha256 } });
  }

  /**
   * Build the final EvidenceRecord.
   *
   * Status is determined by:
   * - "pass": exit_code === 0 AND all results passed
   * - "fail": otherwise
   *
   * @param command - Full command invoked by the harness
   * @param exitCode - Process exit code
   * @param startTime - Execution start timestamp
   * @param endTime - Execution end timestamp
   * @param workingDirectory - Optional working directory where command was executed
   * @returns Complete EvidenceRecord ready for serialization
   */
  build(
    command: string,
    exitCode: number,
    startTime: Date,
    endTime: Date,
    workingDirectory?: string
  ): EvidenceRecord {
    const allPassed = this.results.every((r) => r.passed);
    const status = exitCode === 0 && allPassed ? "pass" : "fail";

    return {
      schema_version: "1.0.0",
      harness_id: this.harnessId,
      status,
      invocation: {
        command,
        exit_code: exitCode,
        ...(workingDirectory !== undefined
          ? { working_directory: workingDirectory }
          : {}),
        start_time: startTime.toISOString(),
        end_time: endTime.toISOString(),
        duration_seconds: (endTime.getTime() - startTime.getTime()) / 1000,
      },
      tool: {
        name: this.toolName,
        version: this.toolVersion,
        commit_sha: this.commitSha,
      },
      artifacts: this.artifacts,
      results: this.results,
    };
  }
}
