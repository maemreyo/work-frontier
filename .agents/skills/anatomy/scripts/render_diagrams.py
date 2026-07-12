#!/usr/bin/env python3
"""Render system-diagram.md and system-diagram.html from one canonical JSON.

The canonical input is `<output_root>/_diagram-data.json`, using the schema
already documented for assets/diagram-template.html. This script deliberately
covers only the two diagram formats; module docs, index.md and entry-points.md
remain authored/verified artifacts rather than generated prose.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import AnatomyInputError, load_module_map_dict  # noqa: E402

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
PLACEHOLDER = "__ANATOMY_DATA_JSON__"


def read_json(path):
    def no_duplicates(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key in %s: %r" % (path, key))
            result[key] = value
        return result
    try:
        return json.loads(Path(path).read_text(), object_pairs_hook=no_duplicates)
    except OSError as exc:
        raise ValueError("could not read %s: %s" % (path, exc))
    except json.JSONDecodeError as exc:
        raise ValueError("invalid JSON in %s: %s" % (path, exc))



def single_line(value):
    return " ".join(str(value).splitlines()).strip()


def validate_data(data, output_root=None):
    if not isinstance(data, dict):
        raise ValueError("diagram data must be a JSON object")
    if not isinstance(data.get("project_name"), str) or not single_line(data.get("project_name")):
        raise ValueError("diagram data requires a non-empty string project_name")
    modules = data.get("modules")
    edges = data.get("edges")
    if not isinstance(modules, list) or not isinstance(edges, list):
        raise ValueError("diagram data requires list fields: modules and edges")

    slugs = set()
    for index, module in enumerate(modules):
        if not isinstance(module, dict):
            raise ValueError("modules[%d] must be an object" % index)
        slug = module.get("slug")
        if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
            raise ValueError("invalid module slug at modules[%d]: %r" % (index, slug))
        if slug in slugs:
            raise ValueError("duplicate module slug: %s" % slug)
        slugs.add(slug)
        for field in ("name", "path", "doc", "role"):
            if field in module and module[field] is not None and not isinstance(module[field], str):
                raise ValueError("module %s field %s must be a string" % (slug, field))
        doc = module.get("doc")
        if doc:
            doc_path = Path(doc)
            if doc_path.is_absolute() or ".." in doc_path.parts or "\n" in doc or "\r" in doc:
                raise ValueError("module %s has an unsafe doc path: %r" % (slug, doc))
        if "confirmed" in module and not isinstance(module["confirmed"], bool):
            raise ValueError("module %s confirmed must be boolean" % slug)

    seen_edges = set()
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise ValueError("edges[%d] must be an object" % index)
        source, target = edge.get("from"), edge.get("to")
        if source not in slugs or target not in slugs:
            raise ValueError("edge %r -> %r references an unknown module" % (source, target))
        key = (source, target)
        if key in seen_edges:
            raise ValueError("duplicate edge: %s -> %s" % key)
        seen_edges.add(key)
        if "confirmed" in edge and not isinstance(edge["confirmed"], bool):
            raise ValueError("edge %s -> %s confirmed must be boolean" % key)
        if edge.get("kind", "sync") not in {"sync", "async"}:
            raise ValueError("edge %s -> %s kind must be sync or async" % key)

    context = data.get("context")
    if context is not None:
        if not isinstance(context, dict):
            raise ValueError("context must be an object when present")
        actors = context.get("actors", []) or []
        external = context.get("external_systems", []) or []
        if not isinstance(actors, list) or not isinstance(external, list) or not all(isinstance(item, str) for item in actors + external):
            raise ValueError("context actors/external_systems must be string lists")
        names = [data["project_name"]] + actors + external
        if len(names) != len(set(names)):
            raise ValueError("context actor/system names must be unique")
        allowed = set(names)
        context_edges = context.get("edges", []) or []
        if not isinstance(context_edges, list):
            raise ValueError("context.edges must be a list")
        for index, edge in enumerate(context_edges):
            if not isinstance(edge, dict) or edge.get("from") not in allowed or edge.get("to") not in allowed:
                raise ValueError("context.edges[%d] references an unknown actor/system" % index)

    flows = data.get("flows", [])
    if not isinstance(flows, list):
        raise ValueError("flows must be a list")
    for flow_index, flow in enumerate(flows):
        if not isinstance(flow, dict) or not isinstance(flow.get("steps", []), list):
            raise ValueError("flows[%d] must be an object with a steps list" % flow_index)
        for step_index, step in enumerate(flow.get("steps", [])):
            if not isinstance(step, dict) or not isinstance(step.get("from"), str) or not isinstance(step.get("to"), str):
                raise ValueError("flows[%d].steps[%d] needs string from/to" % (flow_index, step_index))
            if step.get("kind", "sync") not in {"sync", "async"}:
                raise ValueError("flow step kind must be sync or async")

    if output_root is not None:
        module_map_path = Path(output_root) / "_modules.json"
        if not module_map_path.is_file():
            raise ValueError("required module map not found: %s" % module_map_path)
        try:
            module_map = load_module_map_dict(module_map_path)
        except AnatomyInputError as exc:
            raise ValueError(str(exc))
        mapped = set(module_map)
        if mapped != slugs:
            raise ValueError(
                "_diagram-data.json module set differs from _modules.json; missing=%s extra=%s"
                % (sorted(mapped - slugs), sorted(slugs - mapped))
            )
        modules_by_slug = {module["slug"]: module for module in modules}
        path_mismatches = []
        for slug, expected_path in sorted(module_map.items()):
            actual_path = modules_by_slug[slug].get("path")
            if actual_path != expected_path:
                path_mismatches.append({"module": slug, "expected": expected_path, "actual": actual_path})
        if path_mismatches:
            raise ValueError("_diagram-data.json module paths differ from _modules.json: %s" % path_mismatches)
    return data


def mermaid_label(value):
    # Mermaid accepts HTML entities inside quoted node/participant labels. This
    # avoids breaking syntax on quotes, brackets, pipes, ampersands or Unicode.
    return html.escape(single_line(value), quote=True).replace("'", "&#39;")


def mermaid_edge_label(value):
    # Pipe-delimited Mermaid edge labels need their own escaping in addition
    # to quoted node-label escaping.
    return mermaid_label(value).replace("|", "&#124;")


def markdown_link_label(value):
    return str(value).replace("[", r"\[").replace("]", r"\]")


def render_context(data):
    context = data.get("context")
    if not isinstance(context, dict):
        return []
    actors = context.get("actors", []) or []
    external = context.get("external_systems", []) or []
    edges = context.get("edges", []) or []
    if not actors and not external and not edges:
        return []

    project_name = data.get("project_name", "This system")
    nodes = {str(project_name): "system"}
    lines = ["## System context", "", "```mermaid", "graph LR", 'system["%s"]' % mermaid_label(project_name)]
    for index, name in enumerate(actors):
        node_id = "actor%d" % index
        nodes[str(name)] = node_id
        lines.append('%s(("%s"))' % (node_id, mermaid_label(name)))
    for index, name in enumerate(external):
        node_id = "external%d" % index
        nodes[str(name)] = node_id
        lines.append('%s["%s"]' % (node_id, mermaid_label(name)))
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = nodes.get(str(edge.get("from")))
        target = nodes.get(str(edge.get("to")))
        if source and target:
            label = edge.get("label")
            if label:
                lines.append('%s -->|%s| %s' % (source, mermaid_edge_label(label), target))
            else:
                lines.append("%s --> %s" % (source, target))
    lines.extend(["```", ""])
    return lines


def render_module_graph(data):
    modules = data.get("modules", [])
    edges = data.get("edges", [])
    has_unconfirmed = any(module.get("confirmed") is False for module in modules) or any(
        edge.get("confirmed") is False for edge in edges
    )
    lines = ["## Module dependency graph", "", "```mermaid", "graph TD"]
    if has_unconfirmed:
        lines.append("classDef unconfirmed stroke-dasharray: 3 2")
    for module in modules:
        suffix = ":::unconfirmed" if module.get("confirmed") is False else ""
        lines.append('%s["%s"]%s' % (module["slug"], mermaid_label(module.get("name") or module["slug"]), suffix))
    for edge in edges:
        arrow = "-.->" if edge.get("confirmed") is False else "-->"
        lines.append("%s %s %s" % (edge["from"], arrow, edge["to"]))
    lines.extend(["```", ""])

    links = []
    for module in modules:
        label = markdown_link_label(module.get("name") or module["slug"])
        doc = module.get("doc") or ("modules/%s.md" % module["slug"])
        links.append("[%s](%s)" % (label, doc))
    if links:
        lines.extend(["Modules: " + " · ".join(links), ""])
    return lines


def render_flows(data):
    flows = data.get("flows", []) or []
    if not flows:
        return []
    lines = ["## Key flows", ""]
    for flow_index, flow in enumerate(flows):
        lines.extend(["### %s" % single_line(flow.get("name", "Flow %d" % (flow_index + 1))), "", "```mermaid", "sequenceDiagram"])
        names = []
        for step in flow.get("steps", []):
            for name in (step.get("from"), step.get("to")):
                if name not in names:
                    names.append(name)
        ids = {name: "p%d" % index for index, name in enumerate(names)}
        for name in names:
            lines.append('participant %s as "%s"' % (ids[name], mermaid_label(name)))
        for step in flow.get("steps", []):
            arrow = "-->>" if step.get("kind") == "async" else "->>"
            label = mermaid_label(step.get("label", ""))
            lines.append("%s%s%s: %s" % (ids[step["from"]], arrow, ids[step["to"]], label))
            if step.get("note"):
                lines.append("Note over %s: %s" % (ids[step["to"]], mermaid_label(step["note"])))
        lines.extend(["```", ""])
    return lines


def render_markdown(data):
    project = single_line(data.get("project_name") or "Project")
    lines = ["# System Diagram: %s" % project, ""]
    lines.extend(render_context(data))
    lines.extend(render_module_graph(data))
    lines.extend(render_flows(data))
    return "\n".join(lines).rstrip() + "\n"


def safe_json_for_script(data):
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # Prevent an embedded string such as `</script>` from terminating the
    # script element. U+2028/U+2029 are escaped for older JS parsers.
    return (
        encoded.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_html(data, template_text):
    count = template_text.count(PLACEHOLDER)
    if count != 1:
        raise ValueError("HTML template must contain exactly one %s placeholder; found %d" % (PLACEHOLDER, count))
    output = template_text.replace(PLACEHOLDER, safe_json_for_script(data))
    output = output.replace("__PROJECT_NAME__", html.escape(str(data.get("project_name") or "Project"), quote=True))
    return output


def generated_outputs(output_root, data_path=None, template_path=None):
    root = Path(output_root).resolve()
    data_file = Path(data_path).resolve() if data_path else root / "_diagram-data.json"
    template_file = Path(template_path).resolve() if template_path else Path(__file__).resolve().parent.parent / "assets" / "diagram-template.html"
    data = validate_data(read_json(data_file), root)
    template = template_file.read_text(errors="strict")
    return {
        root / "system-diagram.md": render_markdown(data),
        root / "system-diagram.html": render_html(data, template),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output_root")
    parser.add_argument("--data", default=None, help="canonical JSON (default: <output_root>/_diagram-data.json)")
    parser.add_argument("--template", default=None, help="HTML template override")
    parser.add_argument("--check", action="store_true", help="verify generated files are current without writing")
    args = parser.parse_args()
    try:
        outputs = generated_outputs(args.output_root, args.data, args.template)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        sys.exit(2)

    stale = []
    try:
        for path, content in outputs.items():
            current = path.read_text(errors="strict") if path.is_file() else None
            if current != content:
                stale.append(path.name)
                if not args.check:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = path.with_name(path.name + ".tmp")
                    temporary.write_text(content)
                    temporary.replace(path)
    except OSError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        sys.exit(2)
    print(json.dumps({
        "output_root": str(Path(args.output_root).resolve()),
        "mode": "check" if args.check else "write",
        "stale_or_written": stale,
    }, indent=2))
    if args.check and stale:
        sys.exit(1)


if __name__ == "__main__":
    main()
