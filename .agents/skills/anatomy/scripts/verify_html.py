#!/usr/bin/env python3
"""Verify system-diagram.html embeds canonical diagram data and is current."""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_diagrams import generated_outputs, read_json  # noqa: E402

DATA_START_RE = re.compile(r"\bconst\s+DATA\s*=\s*", re.DOTALL)


def extract_embedded_data(html_text):
    match = DATA_START_RE.search(html_text)
    if not match:
        raise ValueError("could not find `const DATA = {...};` in system-diagram.html")
    decoder = json.JSONDecoder()
    try:
        value, end = decoder.raw_decode(html_text[match.end():])
    except json.JSONDecodeError as exc:
        raise ValueError("embedded DATA is not valid JSON: %s" % exc)
    remainder = html_text[match.end() + end:].lstrip()
    if not remainder.startswith(";"):
        raise ValueError("embedded DATA JSON is not followed by a semicolon")
    if not isinstance(value, dict):
        raise ValueError("embedded DATA must be a JSON object")
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_root")
    parser.add_argument("--data", default=None)
    parser.add_argument("--template", default=None)
    args = parser.parse_args()
    root = Path(args.output_root).resolve()
    data_path = Path(args.data).resolve() if args.data else root / "_diagram-data.json"
    html_path = root / "system-diagram.html"
    try:
        canonical = read_json(data_path)
        html_text = html_path.read_text(errors="strict")
        embedded = extract_embedded_data(html_text)
        expected = generated_outputs(root, args.data, args.template)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        sys.exit(2)

    findings = []
    if embedded != canonical:
        findings.append({"issue": "embedded DATA differs from _diagram-data.json"})
    for path, content in expected.items():
        current = path.read_text(errors="strict") if path.is_file() else None
        if current != content:
            findings.append({"issue": "%s is stale relative to canonical data" % path.name})
    if "__ANATOMY_DATA_JSON__" in html_text:
        findings.append({"issue": "unreplaced HTML template placeholder remains"})
    result = {
        "output_root": str(root),
        "embedded_data_matches": embedded == canonical,
        "findings": findings,
        "note": "This checks parity/currentness; it does not execute the browser JavaScript.",
    }
    print(json.dumps(result, indent=2))
    if findings:
        sys.exit(1)


if __name__ == "__main__":
    main()
