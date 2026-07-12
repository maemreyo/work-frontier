#!/usr/bin/env python3
"""Cross-check entry-points.md, module Public interface sections, and source hypotheses.

The source scan is deliberately heuristic. It can prove that a recognizable
source registration was omitted from the docs, but absence of a hypothesis is
not proof that an entry point does not exist.
"""
import argparse
import json
import re
import sys
from pathlib import Path

TABLE_HEADINGS = {
    "http_routes": re.compile(r"^#{1,6}\s*HTTP routes", re.IGNORECASE),
    "cli_commands": re.compile(r"^#{1,6}\s*CLI commands", re.IGNORECASE),
    "queue_consumers": re.compile(r"^#{1,6}\s*Queue\s*/\s*event consumers", re.IGNORECASE),
    "cron_jobs": re.compile(r"^#{1,6}\s*Scheduled\s*/\s*cron jobs", re.IGNORECASE),
}
VALID_KINDS = set(TABLE_HEADINGS)
IGNORED_DISPOSITIONS = {"false_positive", "ignored", "not_an_entry_point"}
VALID_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "ANY"}
ANY_HEADING_RE = re.compile(r"^#{1,6}\s")
TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
CELL_SPLIT_RE = re.compile(r"\s*\|\s*")
BACKTICK_RE = re.compile(r"`([^`]+)`")
PUBLIC_INTERFACE_RE = re.compile(r"^#{1,6}\s*Public interface", re.IGNORECASE)
HTTP_VERB_PATH_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|ANY)\s+(`?/[^\s`]*`?)", re.IGNORECASE)
CRON_FIELD_RE = re.compile(r"`((?:[\d*/,\-]+\s+){4,5}[\d*/,\-]+)`")
QUEUE_KEYWORD_RE = re.compile(r"\b(topic|consumer|subscri\w+|publish\w*|queue)\b", re.IGNORECASE)
COLLAPSED_RE = re.compile(
    r"(?:^\s*\d+\s+(?:routes?|commands?|consumers?|jobs?)\b|\b(?:grouped|collapsed|representative|under)\b)",
    re.IGNORECASE,
)


def parse_table(text, heading_re):
    rows, in_section, header_seen = [], False, False
    for line in text.splitlines():
        if heading_re.match(line):
            in_section, header_seen = True, False
            continue
        if in_section and ANY_HEADING_RE.match(line) and not heading_re.match(line):
            break
        if not in_section:
            continue
        match = TABLE_ROW_RE.match(line)
        if not match:
            continue
        cells = [cell.strip() for cell in CELL_SPLIT_RE.split(match.group(1))]
        if not header_seen:
            header_seen = True
            continue
        if cells and set("".join(cells)) <= set("-: "):
            continue
        if cells:
            rows.append(cells)
    return rows


def strip_backticks(value):
    match = BACKTICK_RE.search(value)
    return match.group(1) if match else value.strip()


def is_collapsed_row(row):
    return bool(COLLAPSED_RE.search(row.get("detail", "")) or COLLAPSED_RE.search(row.get("raw", "")))


def extract_entry_point_rows(text):
    layout = {
        "http_routes": (2, 1, 0),
        "cli_commands": (1, 0, None),
        "queue_consumers": (1, 0, None),
        "cron_jobs": (1, 0, None),
    }
    result = []
    for kind, heading in TABLE_HEADINGS.items():
        module_index, detail_index, method_index = layout[kind]
        for cells in parse_table(text, heading):
            required = [module_index, detail_index] + ([method_index] if method_index is not None else [])
            if len(cells) <= max(required):
                continue
            row = {
                "kind": kind,
                "module": strip_backticks(cells[module_index]),
                "detail": strip_backticks(cells[detail_index]),
                "raw": " | ".join(cells),
            }
            if method_index is not None:
                row["method"] = strip_backticks(cells[method_index]).upper()
            if row["module"] not in {"", "...", "-", "--"} and row["detail"] not in {"", "...", "-", "--"}:
                result.append(row)
    return result


def extract_public_interface_text(module_text):
    lines, in_section = [], False
    for line in module_text.splitlines():
        if PUBLIC_INTERFACE_RE.match(line):
            in_section = True
            continue
        if in_section and ANY_HEADING_RE.match(line):
            break
        if in_section:
            lines.append(line)
    return "\n".join(lines)


def find_public_interface_candidates(section_text):
    candidates = []
    for match in HTTP_VERB_PATH_RE.finditer(section_text):
        candidates.append({
            "kind": "http_routes",
            "method": match.group(1).upper(),
            "detail": match.group(2).strip("`"),
        })
    for match in CRON_FIELD_RE.finditer(section_text):
        candidates.append({"kind": "cron_jobs", "detail": match.group(1).strip()})
    for line in section_text.splitlines():
        if QUEUE_KEYWORD_RE.search(line):
            ticks = BACKTICK_RE.findall(line)
            if ticks:
                candidates.append({"kind": "queue_consumers", "detail": ticks[0]})
    return candidates


def same_entry(left, right):
    if left.get("kind") != right.get("kind") or left.get("module") != right.get("module"):
        return False
    if left.get("kind") == "http_routes":
        methods = {left.get("method", "ANY").upper(), right.get("method", "ANY").upper()}
        if "ANY" not in methods and len(methods) > 1:
            return False
    return left.get("detail") == right.get("detail")


def collapsed_covers(row, candidate):
    if not is_collapsed_row(row) or row.get("kind") != candidate.get("kind"):
        return False
    if row.get("module") != candidate.get("module"):
        return False
    detail = row.get("detail", "")
    under = re.search(r"\bunder\s+([^\s]+)", detail, re.IGNORECASE)
    if under:
        prefix = under.group(1).split("*", 1)[0]
        return candidate.get("detail", "").startswith(prefix)
    if "*" in detail:
        return candidate.get("detail", "").startswith(detail.split("*", 1)[0])
    return True


def load_source_scan(path):
    if path is None or not Path(path).is_file():
        return None
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("could not read source scan %s: %s" % (path, exc))
    if not isinstance(data, dict) or not isinstance(data.get("hypotheses", []), list):
        raise ValueError("source scan must be an object with a hypotheses list")
    scan_errors = data.get("scan_errors", [])
    if not isinstance(scan_errors, list):
        raise ValueError("source scan scan_errors must be a list")

    hypotheses = []
    for index, candidate in enumerate(data.get("hypotheses", [])):
        if not isinstance(candidate, dict):
            raise ValueError("source scan hypotheses[%d] must be an object" % index)
        kind = candidate.get("kind")
        module = candidate.get("module")
        detail = candidate.get("detail")
        if kind not in VALID_KINDS:
            raise ValueError("source scan hypotheses[%d] has unsupported kind %r" % (index, kind))
        if not isinstance(module, str) or not module.strip():
            raise ValueError("source scan hypotheses[%d] requires a non-empty module" % index)
        if not isinstance(detail, str) or not detail.strip():
            raise ValueError("source scan hypotheses[%d] requires a non-empty detail" % index)
        if kind == "http_routes":
            method = str(candidate.get("method", "ANY")).upper()
            if method not in VALID_HTTP_METHODS:
                raise ValueError("source scan hypotheses[%d] has invalid HTTP method %r" % (index, method))
            candidate = dict(candidate, method=method)
        disposition = str(candidate.get("disposition", "")).strip().lower()
        if disposition in IGNORED_DISPOSITIONS:
            review_note = candidate.get("review_note")
            if not isinstance(review_note, str) or not review_note.strip():
                raise ValueError(
                    "source scan hypotheses[%d] marked %s requires a non-empty review_note"
                    % (index, disposition)
                )
        hypotheses.append(candidate)
    return {"hypotheses": hypotheses, "scan_errors": scan_errors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_root")
    parser.add_argument("--source-scan", default=None, help="entrypoint_scan.py JSON; defaults to _entrypoint-scan.json")
    parser.add_argument("--strict-source", action="store_true", help="exit non-zero for source hypotheses omitted from both docs")
    args = parser.parse_args()
    root = Path(args.output_root).resolve()
    ep_path, modules_dir = root / "entry-points.md", root / "modules"
    if not ep_path.is_file() or not modules_dir.is_dir():
        missing = ep_path if not ep_path.is_file() else modules_dir
        print(json.dumps({"error": "not found: %s" % missing}, indent=2))
        sys.exit(2)

    ep_text = ep_path.read_text(errors="ignore")
    rows = extract_entry_point_rows(ep_text)
    module_sections = {}
    for path in sorted(modules_dir.glob("*.md")):
        module_sections[path.stem] = extract_public_interface_text(path.read_text(errors="ignore"))

    unconfirmed, collapsed_skipped = [], []
    for row in rows:
        if is_collapsed_row(row):
            collapsed_skipped.append(row)
            continue
        section = module_sections.get(row["module"])
        if section is None:
            unconfirmed.append(dict(row, reason="module doc not found"))
        elif row["detail"] not in section:
            unconfirmed.append(dict(row, reason="detail not found in module Public interface"))

    uncaptured = []
    module_candidates = []
    for slug, section in module_sections.items():
        for candidate in find_public_interface_candidates(section):
            candidate = dict(candidate, module=slug)
            module_candidates.append(candidate)
            if not any(same_entry(row, candidate) or collapsed_covers(row, candidate) for row in rows):
                uncaptured.append(candidate)

    scan_path = Path(args.source_scan) if args.source_scan else root / "_entrypoint-scan.json"
    try:
        source_scan = load_source_scan(scan_path)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        sys.exit(2)
    if args.strict_source and source_scan is None:
        print(json.dumps({"error": "strict source verification requires a source scan: %s" % scan_path}, indent=2))
        sys.exit(2)
    if args.strict_source and source_scan and source_scan["scan_errors"]:
        print(json.dumps({
            "error": "source entry-point scan was incomplete because files could not be read",
            "scan_errors": source_scan["scan_errors"],
        }, indent=2))
        sys.exit(2)
    source_hypotheses = source_scan["hypotheses"] if source_scan else []
    ignored_hypotheses = []
    active_hypotheses = []
    for candidate in source_hypotheses:
        disposition = str(candidate.get("disposition", "")).strip().lower() if isinstance(candidate, dict) else ""
        if disposition in IGNORED_DISPOSITIONS:
            ignored_hypotheses.append(candidate)
        else:
            active_hypotheses.append(candidate)

    source_uncaptured = []
    for candidate in active_hypotheses:
        in_rollup = any(same_entry(row, candidate) or collapsed_covers(row, candidate) for row in rows)
        in_module = any(same_entry(doc_candidate, candidate) for doc_candidate in module_candidates)
        if not in_rollup or not in_module:
            source_uncaptured.append({
                "hypothesis": candidate,
                "missing_from_entry_points": not in_rollup,
                "missing_from_module_doc": not in_module,
            })

    unsupported_rows = [
        row for row in rows
        if source_scan is not None and not is_collapsed_row(row)
        and not any(same_entry(row, candidate) for candidate in active_hypotheses)
    ]
    result = {
        "output_root": str(root),
        "modules_found": sorted(module_sections),
        "entry_point_rows_checked": len(rows),
        "entry_points_unconfirmed": unconfirmed,
        "public_interface_uncaptured": uncaptured,
        "collapsed_rows_skipped": collapsed_skipped,
        "source_scan": str(scan_path) if source_scan is not None else None,
        "source_scan_errors": source_scan["scan_errors"] if source_scan else [],
        "source_hypotheses_unaccounted_for": source_uncaptured,
        "source_hypotheses_ignored_after_review": ignored_hypotheses,
        "entry_points_without_scanner_hypothesis": unsupported_rows,
        "counts": {
            "entry_points_unconfirmed": len(unconfirmed),
            "public_interface_uncaptured": len(uncaptured),
            "collapsed_rows_skipped": len(collapsed_skipped),
            "source_hypotheses_unaccounted_for": len(source_uncaptured),
            "source_hypotheses_ignored_after_review": len(ignored_hypotheses),
            "entry_points_without_scanner_hypothesis": len(unsupported_rows),
        },
        "note": (
            "The optional source scan is a hypothesis generator, not an exhaustive parser. "
            "Rows without a scanner hypothesis are reported for review but are not failures. "
            "Collapsed/grouped rows are deliberately skipped from literal forward matching. "
            "Reviewed false positives may be marked with disposition=false_positive and a review_note."
        ),
    }
    print(json.dumps(result, indent=2))
    blocking = unconfirmed or uncaptured or (args.strict_source and source_uncaptured)
    if blocking:
        sys.exit(1)


if __name__ == "__main__":
    main()
