#!/usr/bin/env python3
"""Run anatomy reliability tests in isolated subprocesses.

Isolation prevents a leaked module/global/subprocess state in one integration
test from hanging the remainder of the suite. Every test keeps its original
unittest assertion behavior and gets a hard timeout.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import unittest
from pathlib import Path


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            for test in flatten(item):
                yield test
        else:
            yield item


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=90, help="seconds allowed per test")
    parser.add_argument("--retry-timeout", action="store_true", help="retry a timed-out test once")
    parser.add_argument("--start", type=int, default=1, help="1-based first sorted test to run")
    parser.add_argument("--limit", type=int, default=None, help="maximum number of sorted tests to run")
    args = parser.parse_args()

    tests_dir = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(str(tests_dir), pattern="test_*.py")
    all_test_ids = sorted(test.id() for test in flatten(suite))
    start = max(args.start, 1) - 1
    stop = start + args.limit if args.limit is not None else None
    test_ids = all_test_ids[start:stop]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tests_dir) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")

    failures = []
    timed_out = []
    for index, test_id in enumerate(test_ids, 1):
        print("[%d/%d; global %d/%d] %s" % (index, len(test_ids), start + index, len(all_test_ids), test_id), flush=True)
        command = [sys.executable, "-m", "unittest", "-v", test_id]
        attempts = 2 if args.retry_timeout else 1
        for attempt in range(1, attempts + 1):
            process = subprocess.Popen(
                command,
                cwd=str(tests_dir),
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=(os.name != "nt"),
            )
            try:
                output, _ = process.communicate(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                try:
                    if os.name == "nt":
                        process.kill()
                    else:
                        os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                output, _ = process.communicate()
                print(output, end="" if output.endswith("\n") else "\n")
                if attempt < attempts:
                    print("timed out; killed process group and retrying once", flush=True)
                    continue
                timed_out.append(test_id)
                failures.append(test_id)
                print("TIMEOUT after %ds" % args.timeout, flush=True)
                break
            else:
                print(output, end="" if output.endswith("\n") else "\n")
                if process.returncode:
                    failures.append(test_id)
                break

    print("\nExecuted %d isolated tests" % len(test_ids))
    if timed_out:
        print("Timed out: %s" % ", ".join(timed_out))
    if failures:
        print("FAILED: %d test(s)" % len(failures))
        return 1
    print("OK: all tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
