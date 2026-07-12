#!/usr/bin/env python3
"""
external_calls.py -- heuristic detection of cross-service/network
interactions, for Phase 3 of the anatomy skill's tracing workflow. This is
the companion to import_graph.py: that script only sees edges that go
through a same-language import/require/use statement, which makes it
structurally blind to how services actually talk to each other in most
real systems -- an HTTP call to another service, a gRPC stub invocation, a
message published to a queue and consumed somewhere else, a cron job, a
webhook registration. None of these involve importing the thing on the
other end, so import_graph.py has nothing to find. This script greps for
the common patterns of each instead.

Usage:
    python3 external_calls.py <repo_root> [--kinds http_client,grpc_client,queue,cron,webhook_route] [--modules modules.json]
                              [--output-root PATH] [--exclude PATH ...]

THIS IS A HYPOTHESIS GENERATOR, NOT GROUND TRUTH. Every hit needs its call
site opened and confirmed before it goes into a module doc or diagram.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    AnatomyInputError,
    load_module_map,
    normalize_excludes,
    resolve_module_for_path,
    walk_source_files,
)

ALL_KINDS = ["http_client", "grpc_client", "queue", "cron", "webhook_route"]
WEBHOOK_HINT = re.compile(r"webhook|callback|hook(?!s?\.)", re.IGNORECASE)


def top_level_of(rel_path):
    parts = rel_path.parts
    return parts[0] if len(parts) > 1 else "(root)"


HTTP_CLIENT_PATTERNS = [
    ("python-requests", re.compile(r"\brequests\.(get|post|put|delete|patch|head)\(\s*f?['\"]([^'\"]+)"), 2),
    ("python-httpx", re.compile(r"\bhttpx\.(get|post|put|delete|patch)\(\s*f?['\"]([^'\"]+)"), 2),
    ("python-urllib", re.compile(r"urlopen\(\s*f?['\"]([^'\"]+)"), 1),
    ("js-axios", re.compile(r"\baxios\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)"), 2),
    ("js-fetch", re.compile(r"\bfetch\(\s*['\"]([^'\"]+)"), 1),
    ("go-net-http", re.compile(r'http\.(Get|Post)\(\s*"([^"]+)"'), 2),
    ("java-resttemplate", re.compile(r"restTemplate\.\w+\(\s*\"([^\"]+)\""), 1),
    ("ruby-nethttp", re.compile(r"Net::HTTP\.get\(\s*[^)]*?['\"]([^'\"]+)"), 1),
    ("php-guzzle", re.compile(r"->request\(\s*['\"]\w+['\"]\s*,\s*['\"]([^'\"]+)"), 1),
    ("csharp-httpclient", re.compile(r"\.(?:GetAsync|PostAsync|PutAsync|DeleteAsync)\(\s*\"([^\"]+)\""), 1),
]
GRPC_CLIENT_PATTERNS = [
    ("python-grpc", re.compile(r"(\w+(?:Service)?Stub)\(\s*\w*channel\w*\s*\)")),
    ("go-grpc", re.compile(r"pb\.New(\w+)Client\(")),
    ("java-grpc", re.compile(r"(\w+)Grpc\.new(?:Blocking|Future)?Stub\(")),
]
QUEUE_PATTERNS = [
    ("kafka-producer", re.compile(r"\b\w*[Pp]roducer\w*\.send\(\s*['\"]([^'\"]+)"), "publish"),
    ("kafka-consumer-topic", re.compile(r"KafkaConsumer\(\s*['\"]([^'\"]+)"), "consume"),
    ("generic-publish", re.compile(r"\.publish\(\s*['\"]([^'\"]+)"), "publish"),
    ("rabbitmq-publish", re.compile(r"basic_publish\([^)]*routing_key\s*=\s*['\"]([^'\"]+)"), "publish"),
    ("rabbitmq-consume", re.compile(r"basic_consume\("), "consume"),
    ("sqs-send", re.compile(r"\.send_message\("), "publish"),
    ("sns-publish", re.compile(r"\bsns\w*\.publish\("), "publish"),
    ("generic-emit", re.compile(r"\.emit\(\s*['\"]([^'\"]+)"), "publish"),
    ("generic-subscribe", re.compile(r"\.subscribe\(\s*['\"]([^'\"]+)"), "consume"),
    ("generic-consume", re.compile(r"\.consume\(\s*['\"]([^'\"]+)"), "consume"),
    ("generic-on-event", re.compile(r"\.on\(\s*['\"]([^'\"]+)"), "consume"),
]
CRON_LINE_PATTERNS = [
    ("apscheduler", re.compile(r"\.add_job\(")),
    ("celery-beat", re.compile(r"(?:CELERYBEAT_SCHEDULE|beat_schedule)\s*=")),
    ("node-cron", re.compile(r"\bcron\.schedule\(\s*['\"]([^'\"]+)")),
    ("generic-decorator", re.compile(r"@(?:periodic_task|scheduled|cron)\b")),
]
CRONTAB_LINE = re.compile(r"^\s*(\S+\s+\S+\s+\S+\s+\S+\s+\S+)\s+(?!#)(\S.*)$")
K8S_CRONJOB_KIND = re.compile(r"^\s*kind:\s*CronJob\s*$")
K8S_SCHEDULE = re.compile(r"^\s*schedule:\s*['\"]?([^'\"\n]+?)['\"]?\s*$")
ROUTE_PATTERNS = [
    ("flask", re.compile(r'@\w*\.route\(\s*[\'\"]([^\'\"]+)[\'\"]')),
    ("fastapi", re.compile(r'@\w+\.(?:get|post|put|delete|patch)\(\s*[\'\"]([^\'\"]+)[\'\"]')),
    ("express", re.compile(r'\b(?:app|router)\.(?:get|post|put|delete|patch|all)\(\s*[\'\"]([^\'\"]+)[\'\"]')),
    ("rails", re.compile(r'^\s*(?:get|post|put|patch|delete)\s+[\'\"]([^\'\"]+)[\'\"]')),
    ("spring", re.compile(r'@(?:Get|Post|Put|Delete|Patch|Request)Mapping\(\s*(?:value\s*=\s*)?[\'\"]([^\'\"]*)[\'\"]')),
    ("laravel", re.compile(r'Route::(?:get|post|put|patch|delete)\(\s*[\'\"]([^\'\"]+)[\'\"]')),
]


def scan_file(rel_path, lines, kinds_wanted, hits, module_map=None):
    top = resolve_module_for_path(rel_path.parts, module_map) if module_map is not None else top_level_of(rel_path)
    if top is None:
        top = top_level_of(rel_path)
    is_crontab_like = rel_path.name == "crontab" or rel_path.suffix == ".cron"
    is_yaml = rel_path.suffix.lower() in {".yaml", ".yml"}
    saw_cronjob_kind = False
    for index, line in enumerate(lines, start=1):
        if "http_client" in kinds_wanted:
            for framework, pattern, url_group in HTTP_CLIENT_PATTERNS:
                match = pattern.search(line)
                if match:
                    hits.append({"file": str(rel_path), "line": index, "kind": "http_client", "framework": framework, "detail": match.group(url_group), "top_level": top})
        if "grpc_client" in kinds_wanted:
            for framework, pattern in GRPC_CLIENT_PATTERNS:
                match = pattern.search(line)
                if match:
                    hits.append({"file": str(rel_path), "line": index, "kind": "grpc_client", "framework": framework, "detail": "stub: " + match.group(1), "top_level": top})
        if "queue" in kinds_wanted:
            for framework, pattern, direction in QUEUE_PATTERNS:
                match = pattern.search(line)
                if match:
                    name = match.group(1) if match.groups() else None
                    hits.append({"file": str(rel_path), "line": index, "kind": "queue_" + direction, "framework": framework, "detail": name, "top_level": top})
        if "cron" in kinds_wanted:
            for framework, pattern in CRON_LINE_PATTERNS:
                match = pattern.search(line)
                if match:
                    detail = match.group(1) if match.groups() else line.strip()[:80]
                    hits.append({"file": str(rel_path), "line": index, "kind": "cron", "framework": framework, "detail": detail, "top_level": top})
            if is_crontab_like:
                match = CRONTAB_LINE.match(line)
                if match:
                    hits.append({"file": str(rel_path), "line": index, "kind": "cron", "framework": "crontab", "detail": line.strip(), "top_level": top})
            if is_yaml:
                if K8S_CRONJOB_KIND.match(line):
                    saw_cronjob_kind = True
                elif saw_cronjob_kind:
                    match = K8S_SCHEDULE.match(line)
                    if match:
                        hits.append({"file": str(rel_path), "line": index, "kind": "cron", "framework": "k8s-cronjob", "detail": match.group(1).strip(), "top_level": top})
                        saw_cronjob_kind = False
        if "webhook_route" in kinds_wanted:
            for framework, pattern in ROUTE_PATTERNS:
                match = pattern.search(line)
                if match and WEBHOOK_HINT.search(match.group(1)):
                    hits.append({"file": str(rel_path), "line": index, "kind": "webhook_route", "framework": framework, "detail": match.group(1), "top_level": top})


def find_pub_sub_pairs(hits):
    publishers, consumers = {}, {}
    for hit in hits:
        if not hit.get("detail"):
            continue
        if hit["kind"] == "queue_publish":
            publishers.setdefault(hit["detail"], []).append(hit)
        elif hit["kind"] == "queue_consume":
            consumers.setdefault(hit["detail"], []).append(hit)
    return [
        {
            "topic_or_event": name,
            "published_from": sorted({hit["top_level"] for hit in publishers[name]}),
            "consumed_by": sorted({hit["top_level"] for hit in consumers[name]}),
        }
        for name in sorted(set(publishers) & set(consumers))
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_root")
    parser.add_argument("--kinds", default=",".join(ALL_KINDS), help="comma-separated subset of: " + ",".join(ALL_KINDS))
    parser.add_argument("--modules", default=None, help="Phase 2 modules.json; groups top_level by actual module boundary")
    parser.add_argument("--output-root", default="docs/anatomy", help="generated anatomy output to exclude from scanning")
    parser.add_argument("--exclude", action="append", default=[], help="additional path to exclude (repeatable)")
    args = parser.parse_args()

    kinds_wanted = {kind.strip() for kind in args.kinds.split(",") if kind.strip()}
    unknown = kinds_wanted - set(ALL_KINDS)
    if unknown:
        parser.error("unknown kinds: " + ", ".join(sorted(unknown)))
    repo_root = Path(args.repo_root).resolve()
    if not repo_root.is_dir():
        print(json.dumps({"error": "not a directory: %s" % repo_root}, indent=2))
        sys.exit(2)
    try:
        module_map = load_module_map(args.modules, repo_root)
        excludes = normalize_excludes(repo_root, args.exclude, args.output_root)
    except AnatomyInputError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        sys.exit(2)

    hits = []
    for abs_path, rel_path in walk_source_files(repo_root, gitignore_root=repo_root, exclude_paths=excludes):
        try:
            text = abs_path.read_text(errors="ignore")
        except OSError:
            continue
        if text:
            scan_file(rel_path, text.splitlines(), kinds_wanted, hits, module_map=module_map)

    counts_by_kind, counts_by_top_level = {}, {}
    for hit in hits:
        counts_by_kind[hit["kind"]] = counts_by_kind.get(hit["kind"], 0) + 1
        counts_by_top_level[hit["top_level"]] = counts_by_top_level.get(hit["top_level"], 0) + 1
    result = {
        "repo_root": str(repo_root),
        "hits": hits,
        "counts_by_kind": counts_by_kind,
        "counts_by_top_level": counts_by_top_level,
        "possible_pub_sub_pairs": find_pub_sub_pairs(hits),
        "note": (
            "Hypothesis generator, not ground truth. Every hit needs its call site opened and confirmed. "
            + ("top_level fields use --modules boundaries." if module_map is not None else "top_level fields use first path segment; pass --modules for accurate grouping.")
        ),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
