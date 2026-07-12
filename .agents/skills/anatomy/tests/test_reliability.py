import ast
import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
SUPPORT_DIR = TESTS_DIR / "support"
SCRIPTS = TESTS_DIR.parent / "scripts"
ASK_SCRIPTS = TESTS_DIR.parent.parent / "anatomy-ask" / "scripts"
GATE_SCRIPTS = TESTS_DIR.parent.parent / "anatomy-gate" / "scripts"

sys.path.insert(0, str(SCRIPTS))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Local fallback for connector-only test environments. In an applied checkout,
# the real scripts/rollup.py is imported instead.
try:
    import rollup  # noqa: F401
except ImportError:
    fallback = types.ModuleType("rollup")
    fallback.DEPENDS_HEADING_RE = re.compile(r"^#{1,6}\s*Depends on", re.I)
    fallback.USED_BY_HEADING_RE = re.compile(r"^#{1,6}\s*Used by", re.I)
    any_heading = re.compile(r"^#{1,6}\s")
    module_ref = re.compile(r"\*\*`([^`]+)`\*\*")
    footer = re.compile(r"Files examined in depth:\s*(.+?)\.?\s*$", re.I)

    def extract_refs(text, heading):
        refs, active = set(), False
        for line in text.splitlines():
            if heading.match(line):
                active = True
                continue
            if active and any_heading.match(line):
                break
            if active:
                refs.update(module_ref.findall(line))
        return refs

    def extract_coverage(text):
        match = footer.search(text)
        if not match:
            return "unstated", None
        value = match.group(1)
        if re.search(r"\ball\s+\d+\s+files?\b", value, re.I):
            return "full", value
        if re.search(r"sampled\s+\d+\s+of\s+\d+", value, re.I):
            return "sampled", value
        return "listed", value

    def find_cycles(graph):
        found = set()
        visiting, visited, stack = set(), set(), []

        def canonical(path):
            nodes = path[:-1]
            rotations = [tuple(nodes[i:] + nodes[:i]) for i in range(len(nodes))]
            best = min(rotations)
            return best + (best[0],)

        def dfs(node):
            visiting.add(node)
            stack.append(node)
            for nxt in sorted(graph.get(node, ())):
                if nxt in visiting:
                    index = stack.index(nxt)
                    found.add(canonical(stack[index:] + [nxt]))
                elif nxt not in visited:
                    dfs(nxt)
            stack.pop()
            visiting.remove(node)
            visited.add(node)

        for node in sorted(graph):
            if node not in visited:
                dfs(node)
        return [list(item) for item in sorted(found)]

    fallback.extract_refs = extract_refs
    fallback.extract_coverage = extract_coverage
    fallback.find_cycles = find_cycles
    sys.modules["rollup"] = fallback

common = load("anatomy_common", SCRIPTS / "_common.py")
# state imports module name `_common`, so make the same object available there.
sys.modules["_common"] = common
state = load("anatomy_state", SCRIPTS / "state.py")
inventory = load("anatomy_inventory", SCRIPTS / "inventory.py")
import_graph = load("anatomy_import_graph", SCRIPTS / "import_graph.py")
sync_edges = load("anatomy_sync_edges", SCRIPTS / "sync_reverse_edges.py")
verify_diagram = load("anatomy_verify_diagram", SCRIPTS / "verify_diagram.py")
verify_entry = load("anatomy_verify_entry", SCRIPTS / "verify_entry_points.py")
render = load("anatomy_render", SCRIPTS / "render_diagrams.py")
verify_html = load("anatomy_verify_html", SCRIPTS / "verify_html.py")
verify_health = load("anatomy_verify_health", SCRIPTS / "verify_health_signals.py")


def module_doc(name, depends=None, used_by=None, coverage="all 1 files"):
    depends = depends or []
    used_by = used_by or []
    dep_lines = depends if depends else ["None confirmed."]
    used_lines = used_by if used_by else ["None confirmed."]
    return (
        "# Module: %s\n\n**Path:** `src/%s`\n**Role:** test\n\n"
        "## Public interface\n\n- `GET /%s` -- route\n\n"
        "## Depends on\n\n%s\n\n## Used by\n\n%s\n\n---\n\n"
        "_Traced from source on 2026-07-11. Files examined in depth: %s._\n"
        % (name, name.lower(), name.lower(), "\n".join(dep_lines), "\n".join(used_lines), coverage)
    )


class FileSelectionTests(unittest.TestCase):
    def test_root_module_excludes_default_and_custom_output(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "src").mkdir()
            (repo / "src" / "app.py").write_text("print('x')\n")
            default_output = repo / "docs" / "anatomy"
            default_output.mkdir(parents=True)
            (default_output / "index.md").write_text("first")
            first = state.hash_module(repo, ".", common.normalize_excludes(repo))
            (default_output / "index.md").write_text("second")
            second = state.hash_module(repo, ".", common.normalize_excludes(repo))
            self.assertEqual(first, second)

            custom = repo / "architecture" / "generated"
            custom.mkdir(parents=True)
            (custom / "trace.md").write_text("one")
            excludes = common.normalize_excludes(repo, output_root=custom)
            third = state.hash_module(repo, ".", excludes)
            (custom / "trace.md").write_text("two")
            fourth = state.hash_module(repo, ".", excludes)
            self.assertEqual(third, fourth)

    def test_state_cli_preserves_flat_default_and_policy_opt_in(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "src").mkdir()
            (repo / "src" / "app.py").write_text("x")
            modules = repo / "modules.json"
            modules.write_text(json.dumps({"root": "."}))

            parser = state.build_parser()
            legacy_args = parser.parse_args(["hash-modules", str(repo), str(modules)])
            legacy_stdout = io.StringIO()
            with contextlib.redirect_stdout(legacy_stdout):
                legacy_args.func(legacy_args)
            legacy = json.loads(legacy_stdout.getvalue())
            self.assertEqual(set(legacy), {"root"})

            modern_args = parser.parse_args([
                "hash-modules", str(repo), str(modules), "--with-policy",
                "--output-root", str(repo / "custom" / "trace"),
            ])
            modern_stdout = io.StringIO()
            with contextlib.redirect_stdout(modern_stdout):
                modern_args.func(modern_args)
            modern = json.loads(modern_stdout.getvalue())
            self.assertEqual(modern["version"], 2)
            self.assertIn("custom/trace", modern["scan_policy"]["excludes"])

    def test_repo_gitignore_paths_and_bin_source(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / ".gitignore").write_text("generated/cache/\n")
            (repo / "generated" / "cache").mkdir(parents=True)
            (repo / "generated" / "cache" / "x.py").write_text("ignored")
            (repo / "bin").mkdir()
            (repo / "bin" / "tool.py").write_text("included")
            (repo / "src").mkdir()
            (repo / "src" / "app.py").write_text("included")
            files = [rel.as_posix() for _path, rel in common.walk_source_files(repo, gitignore_root=repo)]
            self.assertIn("bin/tool.py", files)
            self.assertIn("src/app.py", files)
            self.assertNotIn("generated/cache/x.py", files)

    def test_stable_slug_map_remains_unique_under_hash_prefix_collision(self):
        class ConstantHash(object):
            def hexdigest(self):
                return "0" * 40

        with mock.patch.object(common.hashlib, "sha1", return_value=ConstantHash()):
            mapping = common.stable_slug_map([
                ("same", "src/a"),
                ("same", "src/b"),
                ("same-00000000", "src/c"),
            ])
        self.assertEqual(len(mapping), 3)
        self.assertEqual(len(set(mapping.values())), 3)

    def test_symlinked_file_outside_repo_is_not_scanned(self):
        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are unavailable")
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            repo = base / "repo"
            outside = base / "outside.py"
            repo.mkdir()
            outside.write_text("secret")
            try:
                (repo / "linked.py").symlink_to(outside)
            except OSError as exc:
                self.skipTest("could not create symlink: %s" % exc)
            files = [rel.as_posix() for _path, rel in common.walk_source_files(repo, gitignore_root=repo)]
            self.assertNotIn("linked.py", files)

    def test_unreadable_file_is_error_not_pseudo_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "src").mkdir()
            target = repo / "src" / "app.py"
            target.write_text("x")
            real = state.sha256_file

            def fail(path):
                if Path(path) == target:
                    raise OSError("permission denied")
                return real(path)

            with mock.patch.object(state, "sha256_file", side_effect=fail):
                result = state.hash_module(repo, "src", common.normalize_excludes(repo))
            self.assertIn("error", result)
            self.assertNotEqual(result.get("hash"), "unreadable")

    def test_slug_collision_and_python_relative_import(self):
        mapping = common.stable_slug_map([
            ("foo bar", "src/a"),
            ("foo_bar", "src/b"),
            ("東京", "src/c"),
        ])
        self.assertEqual(len(set(mapping.values())), 3)
        self.assertRegex(mapping["src/c"], r"^module-[0-9a-f]{8}$")
        self.assertEqual(common.resolve_relative_import(Path("pkg/sub/mod.py"), "..services"), "pkg/services")
        self.assertEqual(common.resolve_relative_import(Path("pkg/sub/mod.py"), ".helpers"), "pkg/sub/helpers")


class ScannerTests(unittest.TestCase):
    def test_multiline_ci_fallback(self):
        text = """jobs:\n  test:\n    steps:\n      - name: Verify\n        run: |\n          python -m pytest\n          python -m compileall src\n      - name: Build\n        run: npm run build\n"""
        commands = inventory.extract_run_commands_regex(text)
        self.assertEqual(len(commands), 2)
        self.assertIn("python -m pytest", commands[0]["command"])
        self.assertIn("python -m compileall src", commands[0]["command"])
        self.assertEqual(commands[1]["command"], "npm run build")

    def test_import_graph_python_relative(self):
        module_map = [(('pkg', 'services'), 'services'), (('pkg', 'api'), 'api')]
        result = import_graph.resolve_target(Path("pkg/api/routes.py"), "..services", module_map, {"api", "services"})
        self.assertEqual(result, "services")


class ReverseEdgeTests(unittest.TestCase):
    def test_preserves_footer_external_and_adds_new_reverse_edge(self):
        a = module_doc("A", depends=["- **`b`** — calls save (`src/a.py:4`)"])
        a = a.replace("None confirmed.\n\n---", "- external: `partner` — webhook (`src/a.py:8`)\n\n---")
        b = module_doc("B", used_by=["- **`stale`** — old (`old.py:1`)"])
        docs = {"a": a, "b": b}
        reverse, dangling = sync_edges.build_reverse_map(docs)
        self.assertEqual(dangling, [])
        patched_a = sync_edges.patch_used_by(a, reverse["a"])
        patched_b = sync_edges.patch_used_by(b, reverse["b"])
        self.assertIn("external: `partner`", patched_a)
        self.assertIn("Files examined in depth: all 1 files", patched_a)
        self.assertIn("- **`a`** — calls save (`src/a.py:4`)", patched_b)
        self.assertNotIn("**`stale`**", patched_b)
        self.assertIn("Files examined in depth: all 1 files", patched_b)

    def test_dangling_internal_target_blocks_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "modules").mkdir()
            original = module_doc("A", depends=["- **`removed`** — stale call (`src/a.py:2`)"])
            path = root / "modules" / "a.md"
            path.write_text(original)
            result = sync_edges.run(root, write=True)
            self.assertTrue(result["write_blocked"])
            self.assertEqual(result["dangling_internal_targets"], [{"from": "a", "to": "removed"}])
            self.assertEqual(path.read_text(), original)



class DiagramTests(unittest.TestCase):
    def test_quick_scan_dotted_and_classed_edges(self):
        text = """# Diagram\n\n## Module dependency graph\n\n```mermaid\ngraph TD\na[\"A\"]:::unconfirmed\nb((\"B\"))\na -.-> b\nb --> c[\"C\"]\n```\n"""
        self.assertEqual(verify_diagram.extract_module_graph_edges(text), {("a", "b"): False, ("b", "c"): True})

    def test_renderer_escapes_and_html_embeds_safe_json(self):
        data = {
            "project_name": "A </script> & B",
            "generated_at": "2026-07-11",
            "mode": "quick-scan",
            "source_commit": "abc",
            "modules": [
                {"slug": "api", "name": 'API "Core" [v1] | edge', "role": "HTTP", "path": "src/api", "doc": "modules/api.md", "confirmed": False},
                {"slug": "svc", "name": "Service", "role": "logic", "path": "src/svc", "doc": "modules/svc.md"},
            ],
            "edges": [{"from": "api", "to": "svc", "label": "calls", "kind": "sync", "confirmed": False}],
            "context": {
                "actors": ["User"],
                "external_systems": ["Partner"],
                "edges": [{"from": "User", "to": "A </script> & B", "label": "uses | safely"}],
            },
            "flows": [],
        }
        markdown = render.render_markdown(data)
        self.assertIn("api -.-> svc", markdown)
        self.assertIn(":::unconfirmed", markdown)
        self.assertNotIn('api["API "Core"', markdown)
        self.assertIn("-->|uses &#124; safely|", markdown)
        template = "<html><title>__PROJECT_NAME__</title><script>const DATA = __ANATOMY_DATA_JSON__;</script></html>"
        output = render.render_html(data, template)
        self.assertEqual(output.lower().count("</script>"), 1)
        embedded = verify_html.extract_embedded_data(output)
        self.assertEqual(embedded, data)

    def test_module_set_validation_catches_silent_drop(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "_modules.json").write_text(json.dumps({"a": "src/a", "b": "src/b"}))
            data = {"modules": [{"slug": "a", "name": "A", "path": "src/a", "doc": "modules/a.md"}], "edges": []}
            with self.assertRaises(ValueError):
                render.validate_data(data, root)


class EntryPointTests(unittest.TestCase):
    def test_collapsed_row_is_not_literal_false_positive(self):
        text = """## HTTP routes\n\n| Method | Path | Module | Handler | File |\n|---|---|---|---|---|\n| ANY | 38 routes under /api/v1/resources/* | `api` | grouped | api.md |\n"""
        rows = verify_entry.extract_entry_point_rows(text)
        self.assertEqual(len(rows), 1)
        self.assertTrue(verify_entry.is_collapsed_row(rows[0]))
        candidate = {"kind": "http_routes", "method": "GET", "detail": "/api/v1/resources/orders", "module": "api"}
        self.assertTrue(verify_entry.collapsed_covers(rows[0], candidate))


class HealthTests(unittest.TestCase):
    def test_exact_orphan_and_cycle_parsing(self):
        parsed = verify_health.parse_index_health_signals("""## Codebase health signals\n\n1. `a` -- 2\n2. `b` -- 2\n3. `c` -- 0\n\n**Possible dead code / orphan modules:** `c`\n\n**Dependency cycles:** `a` -> `b` -> `a`\n\n**Trace coverage:** 3 of 3 modules were traced in full.\n""")
        self.assertEqual(parsed["orphan_modules"], ["c"])
        self.assertEqual(parsed["cycles"], [("a", "b")])


class SatelliteParityTests(unittest.TestCase):
    def test_satellite_hashes_match_anatomy(self):
        ask = load("ask_state_lite_test", ASK_SCRIPTS / "_state_lite.py")
        gate = load("gate_state_lite_test", GATE_SCRIPTS / "_state_lite.py")
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "src").mkdir()
            (repo / "src" / "app.py").write_text("x")
            output = repo / "custom" / "trace"
            output.mkdir(parents=True)
            (output / "index.md").write_text("generated")
            modules = {"root": "."}
            canonical = state.hash_modules(repo, modules, output_root=output)
            ask_hashes = ask.hash_modules(repo, modules, output_root=output)
            gate_hashes = gate.hash_modules(repo, modules, output_root=output)
            self.assertEqual(canonical, ask_hashes)
            self.assertEqual(canonical, gate_hashes)


class IntegrationTests(unittest.TestCase):
    def run_script(self, script, *args, cwd=None, expected=0):
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(SUPPORT_DIR) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
        proc = subprocess.run(
            [sys.executable, str(script), *map(str, args)],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        self.assertEqual(proc.returncode, expected, msg="stdout:\n%s\nstderr:\n%s" % (proc.stdout, proc.stderr))
        return json.loads(proc.stdout)

    def test_state_v1_v2_manifest_migration_and_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "src").mkdir()
            (repo / "src" / "a.py").write_text("x")
            modules = {"root": "."}
            output = repo / "docs" / "anatomy"
            legacy = state.hash_modules(repo, modules, output_root=output)
            self.assertIn("root", legacy)
            modern = {
                "version": 2,
                "scan_policy": common.scan_policy_metadata(repo, output_root=output),
                "modules": state.hash_modules(repo, modules, output_root=output),
            }
            self.assertEqual(modern["version"], 2)
            self.assertIn("docs/anatomy", modern["scan_policy"]["excludes"])
            diff = state.compute_diff({"modules": legacy}, modern)
            self.assertEqual(diff["unchanged"], ["root"])
            self.assertFalse(diff["scan_policy_changed"])

    def test_state_reports_policy_migration_and_change(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            old_modules = {"a": {"hash": "same", "file_count": 1}}
            fresh_modules = {"a": {"hash": "same", "file_count": 1}}
            migrated = state.compute_diff(
                {"modules": old_modules},
                {"version": 2, "scan_policy": {"version": 1, "excludes": ["docs/anatomy"]}, "modules": fresh_modules},
            )
            self.assertTrue(migrated["scan_policy_migrated"])
            self.assertFalse(migrated["scan_policy_changed"])
            self.assertIn("metadata added", migrated["recommendation"])
            order_only = state.compute_diff(
                {"modules": old_modules, "scan_policy": {"version": 1, "excludes": ["generated", "docs/anatomy"]}},
                {"version": 2, "scan_policy": {"version": 1, "excludes": ["docs/anatomy", "generated"]}, "modules": fresh_modules},
            )
            self.assertFalse(order_only["scan_policy_changed"])
            changed = state.compute_diff(
                {"modules": old_modules, "scan_policy": {"version": 1, "excludes": ["docs/anatomy"]}},
                {"version": 2, "scan_policy": {"version": 1, "excludes": ["docs/anatomy", "generated"]}, "modules": fresh_modules},
            )
            self.assertTrue(changed["scan_policy_changed"])
            self.assertIn("scan policy changed", changed["recommendation"])

    def test_renderer_requires_module_map(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = {
                "project_name": "Missing map",
                "modules": [{"slug": "a", "name": "A", "path": "src/a", "doc": "modules/a.md"}],
                "edges": [],
                "flows": [],
            }
            (root / "_diagram-data.json").write_text(json.dumps(data))
            template = root / "template.html"
            template.write_text("<title>__PROJECT_NAME__</title><script>const DATA = __ANATOMY_DATA_JSON__;</script>")
            result = self.run_script(SCRIPTS / "render_diagrams.py", root, "--template", template, expected=2)
            self.assertIn("required module map not found", result["error"])

    def test_render_and_verify_cli_with_nested_json_and_real_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "_modules.json").write_text(json.dumps({"a": "src/a", "b": "src/b"}))
            data = {
                "project_name": "Project }; </script>",
                "generated_at": "2026-07-11",
                "mode": "deep",
                "source_commit": "abcdef",
                "modules": [
                    {"slug": "a", "name": "A", "role": "entry", "path": "src/a", "doc": "modules/a.md"},
                    {"slug": "b", "name": "B", "role": "service", "path": "src/b", "doc": "modules/b.md"},
                ],
                "edges": [{"from": "a", "to": "b", "label": "save }; safely", "kind": "sync", "confirmed": True}],
                "context": {"actors": ["User"], "external_systems": ["Partner"], "edges": [{"from": "User", "to": "Project }; </script>", "label": "uses"}]},
                "flows": [{"name": "Request", "steps": [{"from": "User", "to": "a", "label": "call", "kind": "sync"}]}],
            }
            (root / "_diagram-data.json").write_text(json.dumps(data))
            template = root / "template.html"
            template.write_text("<!doctype html><title>__PROJECT_NAME__</title><script>const DATA = __ANATOMY_DATA_JSON__;</script>")
            written = self.run_script(SCRIPTS / "render_diagrams.py", root, "--template", template)
            self.assertEqual(set(written["stale_or_written"]), {"system-diagram.md", "system-diagram.html"})
            checked = self.run_script(SCRIPTS / "render_diagrams.py", root, "--template", template, "--check")
            self.assertEqual(checked["stale_or_written"], [])
            verified = self.run_script(SCRIPTS / "verify_html.py", root, "--template", template)
            self.assertTrue(verified["embedded_data_matches"])
            html_text = (root / "system-diagram.html").read_text()
            self.assertEqual(html_text.lower().count("</script>"), 1)

    def test_verify_diagram_cli_accepts_explicit_quick_scan(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "modules").mkdir()
            (root / "modules/a.md").write_text(module_doc("A", depends=["- **`b`** — _unconfirmed_, hypothesis (`a.py:1`)"]))
            (root / "modules/b.md").write_text(module_doc("B", used_by=["- **`a`** — _unconfirmed_, hypothesis (`a.py:1`)"]))
            (root / "system-diagram.md").write_text("# D\n\n## Module dependency graph\n\n```mermaid\ngraph TD\na[\"A\"]:::unconfirmed\nb[\"B\"]\na -.-> b\n```\n")
            result = self.run_script(SCRIPTS / "verify_diagram.py", root)
            self.assertEqual(result["counts"]["edge_confirmation_style_mismatch"], 0)
            self.assertEqual(result["counts"]["quick_scan_unconfirmed_edges"], 1)

    def test_reverse_edge_cli_check_and_write(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "modules").mkdir()
            (root / "modules/a.md").write_text(module_doc("A", depends=["- **`b`** — call (`a.py:1`)"]))
            (root / "modules/b.md").write_text(module_doc("B"))
            check = self.run_script(SCRIPTS / "sync_reverse_edges.py", root, "--check", expected=1)
            self.assertEqual(check["modules_needing_update"], ["b"])
            self.run_script(SCRIPTS / "sync_reverse_edges.py", root, "--write")
            self.run_script(SCRIPTS / "sync_reverse_edges.py", root, "--check")
            self.assertIn("**`a`**", (root / "modules/b.md").read_text())

    def test_strict_source_requires_scan_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "modules").mkdir()
            (root / "modules/api.md").write_text(module_doc("Api"))
            (root / "entry-points.md").write_text(
                "## HTTP routes\n\n| Method | Path | Module | Handler | File |\n"
                "|---|---|---|---|---|\n| GET | `/api` | `api` | h | f |\n"
            )
            result = self.run_script(SCRIPTS / "verify_entry_points.py", root, "--strict-source", expected=2)
            self.assertIn("requires a source scan", result["error"])

    def test_source_entrypoint_hypothesis_is_three_way_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "modules").mkdir()
            (root / "modules/api.md").write_text(module_doc("Api"))
            (root / "entry-points.md").write_text("## HTTP routes\n\n| Method | Path | Module | Handler | File |\n|---|---|---|---|---|\n| GET | `/api` | `api` | h | f |\n")
            scan = root / "_entrypoint-scan.json"
            scan.write_text(json.dumps({"hypotheses": [{"kind": "http_routes", "method": "POST", "detail": "/missing", "module": "api", "file": "api.py", "line": 3}]}))
            result = self.run_script(SCRIPTS / "verify_entry_points.py", root, "--source-scan", scan)
            self.assertEqual(result["counts"]["source_hypotheses_unaccounted_for"], 1)
            self.run_script(SCRIPTS / "verify_entry_points.py", root, "--source-scan", scan, "--strict-source", expected=1)
            payload = json.loads(scan.read_text())
            payload["hypotheses"][0]["disposition"] = "false_positive"
            payload["hypotheses"][0]["review_note"] = "test fixture intentionally has no route"
            scan.write_text(json.dumps(payload))
            reviewed = self.run_script(SCRIPTS / "verify_entry_points.py", root, "--source-scan", scan, "--strict-source")
            self.assertEqual(reviewed["counts"]["source_hypotheses_ignored_after_review"], 1)

    def test_source_scan_review_contract_and_empty_scan_reporting(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "modules").mkdir()
            (root / "modules/api.md").write_text(module_doc("Api"))
            (root / "entry-points.md").write_text(
                "## HTTP routes\n\n| Method | Path | Module | Handler | File |\n"
                "|---|---|---|---|---|\n| GET | `/api` | `api` | h | f |\n"
            )
            scan = root / "_entrypoint-scan.json"
            scan.write_text(json.dumps({"hypotheses": [], "scan_errors": []}))
            empty = self.run_script(SCRIPTS / "verify_entry_points.py", root, "--source-scan", scan)
            self.assertEqual(empty["counts"]["entry_points_without_scanner_hypothesis"], 1)

            scan.write_text(json.dumps({
                "hypotheses": [{
                    "kind": "http_routes", "method": "GET", "detail": "/api", "module": "api",
                    "disposition": "false_positive",
                }],
                "scan_errors": [],
            }))
            invalid_review = self.run_script(
                SCRIPTS / "verify_entry_points.py", root, "--source-scan", scan, expected=2
            )
            self.assertIn("requires a non-empty review_note", invalid_review["error"])

            scan.write_text(json.dumps({"hypotheses": [], "scan_errors": {"bad": "shape"}}))
            invalid_errors = self.run_script(
                SCRIPTS / "verify_entry_points.py", root, "--source-scan", scan, expected=2
            )
            self.assertIn("scan_errors must be a list", invalid_errors["error"])

    def test_renderer_rejects_module_path_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "_modules.json").write_text(json.dumps({"a": "src/a"}))
            (root / "_diagram-data.json").write_text(json.dumps({
                "project_name": "Path drift",
                "modules": [{"slug": "a", "name": "A", "path": "src/wrong", "doc": "modules/a.md"}],
                "edges": [],
                "flows": [],
            }))
            template = root / "template.html"
            template.write_text("<title>__PROJECT_NAME__</title><script>const DATA = __ANATOMY_DATA_JSON__;</script>")
            result = self.run_script(SCRIPTS / "render_diagrams.py", root, "--template", template, expected=2)
            self.assertIn("module paths differ", result["error"])

    def test_graph_export_uses_repository_source_root_and_complete_module_set(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            root = repo / "docs" / "anatomy"
            (root / "modules").mkdir(parents=True)
            (root / "_modules.json").write_text(json.dumps({"a": "src/a", "b": "src/b"}))
            (root / "_manifest.json").write_text(json.dumps({"source_root": str(repo)}))
            (root / "modules/a.md").write_text(module_doc("A", depends=["- **`b`** — calls save (`src/a.py:4`)"]))
            (root / "modules/b.md").write_text(module_doc("B", used_by=["- **`a`** — calls save (`src/a.py:4`)"]))
            (root / "entry-points.md").write_text(
                "## HTTP routes\n\n| Method | Path | Module | Handler | File |\n"
                "|---|---|---|---|---|\n| GET | `/a` | `a` | h | f |\n"
            )
            result = self.run_script(SCRIPTS / "graph_export.py", root)
            self.assertEqual(result["source_root"], str(repo))
            self.assertNotEqual(result["source_root"], str(root))
            self.assertEqual(set(result["modules"]), {"a", "b"})
            self.assertEqual(result["entry_points"]["http_routes"][0]["detail"], "/a")

            (root / "modules/b.md").unlink()
            mismatch = self.run_script(SCRIPTS / "graph_export.py", root, expected=1)
            self.assertEqual(mismatch["missing_docs"], ["b"])

    def test_graph_export_requires_module_map(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "modules").mkdir()
            (root / "modules/a.md").write_text(module_doc("A"))
            result = self.run_script(SCRIPTS / "graph_export.py", root, expected=2)
            self.assertIn("required non-empty module map", result["error"])

    def test_graph_export_rejects_duplicate_module_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "modules").mkdir()
            (root / "modules/a.md").write_text(module_doc("A"))
            (root / "_modules.json").write_text('{"a":"src/a","a":"src/other"}')
            result = self.run_script(SCRIPTS / "graph_export.py", root, expected=2)
            self.assertIn("duplicate JSON key", result["error"])

    def test_health_verifier_rejects_wrong_nonempty_orphan_and_cycle_lists(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "modules").mkdir()
            (root / "modules/a.md").write_text(module_doc("A", depends=["- **`b`** — call (`a.py:1`)"]))
            (root / "modules/b.md").write_text(module_doc("B", depends=["- **`a`** — call (`b.py:1`)"]))
            (root / "modules/c.md").write_text(module_doc("C"))
            (root / "index.md").write_text(
                "## Codebase health signals\n\n"
                "1. `a` -- 2\n2. `b` -- 2\n3. `c` -- 0\n\n"
                "**Possible dead code / orphan modules:** `wrong`\n\n"
                "**Dependency cycles:** `a` -> `c` -> `a`\n\n"
                "**Trace coverage:** 3 of 3 modules were traced in full.\n"
            )
            result = self.run_script(SCRIPTS / "verify_health_signals.py", root, expected=1)
            signals = {finding["signal"] for finding in result["findings"]}
            self.assertIn("orphan_candidates", signals)
            self.assertIn("cycles", signals)

    def test_entrypoint_scanner_finds_cli_route_queue_and_cron_hypotheses(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            src = repo / "src" / "api"
            src.mkdir(parents=True)
            (src / "app.py").write_text(
                "@app.get('/orders')\n"
                "def orders(): pass\n"
                "@app.route('/admin', methods=['POST'])\n"
                "def admin(): pass\n"
                "@click.command('ship')\n"
                "def ship(): pass\n"
                "consumer.subscribe('orders.shipped')\n"
                "cron.schedule('0 2 * * *', run)\n"
            )
            modules = repo / "modules.json"
            modules.write_text(json.dumps({"api": "src/api"}))
            result = self.run_script(SCRIPTS / "entrypoint_scan.py", repo, "--modules", modules)
            kinds = {row["kind"] for row in result["hypotheses"]}
            self.assertTrue({"http_routes", "cli_commands", "queue_consumers", "cron_jobs"}.issubset(kinds))
            self.assertTrue(any(row.get("method") == "POST" and row.get("detail") == "/admin" for row in result["hypotheses"]))

    def test_scanners_reject_invalid_module_map_cleanly(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "src").mkdir()
            (repo / "src" / "app.py").write_text("import x\n")
            modules = repo / "modules.json"
            modules.write_text('{"bad slug":"src"}')
            for script in ("import_graph.py", "external_calls.py", "entrypoint_scan.py"):
                with self.subTest(script=script):
                    result = self.run_script(SCRIPTS / script, repo, "--modules", modules, expected=2)
                    self.assertIn("invalid module slug", result["error"])

    def test_real_repository_template_when_available(self):
        template = SCRIPTS.parent / "assets" / "diagram-template.html"
        if not template.is_file():
            self.skipTest("real repository template is available after applying the bundle to a checkout")
        text = template.read_text(errors="strict")
        self.assertGreater(len(text), 20000)
        self.assertEqual(text.count("__ANATOMY_DATA_JSON__"), 1)
        data = {
            "project_name": "Real-template smoke",
            "modules": [{"slug": "a", "name": "A", "path": "src/a", "doc": "modules/a.md"}],
            "edges": [],
            "flows": [],
        }
        output = render.render_html(data, text)
        self.assertEqual(verify_html.extract_embedded_data(output), data)
        self.assertNotIn("__ANATOMY_DATA_JSON__", output)


class GateBehaviorTests(unittest.TestCase):
    def test_empty_trace_state_is_setup_error(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            output = repo / "docs" / "anatomy"
            output.mkdir(parents=True)
            (output / "_modules.json").write_text("{}")
            (output / "_manifest.json").write_text(json.dumps({"modules": {}}))
            gate = subprocess.run(
                [sys.executable, str(GATE_SCRIPTS / "docs_gate.py"), str(output), "--repo-root", str(repo)],
                capture_output=True, text=True,
            )
            self.assertEqual(gate.returncode, 2, msg=gate.stdout + gate.stderr)
            self.assertEqual(json.loads(gate.stdout)["status"], "error")
            ask = subprocess.run(
                [sys.executable, str(ASK_SCRIPTS / "freshness_check.py"), str(output), "--repo-root", str(repo)],
                capture_output=True, text=True,
            )
            self.assertEqual(ask.returncode, 2, msg=ask.stdout + ask.stderr)
            self.assertEqual(json.loads(ask.stdout)["status"], "error")

    def test_hashing_unknown_is_setup_error_even_in_report_only_mode(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            output = repo / "docs" / "anatomy"
            output.mkdir(parents=True)
            # A persisted path escaping the repo is invalid/unknown, not clean or removed.
            (output / "_modules.json").write_text(json.dumps({"bad": "../outside"}))
            (output / "_manifest.json").write_text(json.dumps({
                "modules": {"bad": {"hash": "old", "file_count": 1}},
                "scan_policy": {"version": 1, "excludes": ["docs/anatomy"], "gitignore_root": ".", "unreadable_file_policy": "error"},
            }))
            proc = subprocess.run(
                [sys.executable, str(GATE_SCRIPTS / "docs_gate.py"), str(output), "--repo-root", str(repo), "--fail-on", "none"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 2, msg=proc.stdout + proc.stderr)
            result = json.loads(proc.stdout)
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["findings"][0]["status"], "unknown")
            self.assertEqual(result["findings"][0]["severity"], "high")


class SatelliteBehaviorTests(unittest.TestCase):
    def test_missing_persisted_module_is_removed_not_clean(self):
        ask = load("ask_state_lite_removed_test", ASK_SCRIPTS / "_state_lite.py")
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            fresh = ask.hash_modules(repo, {"gone": "src/gone"}, output_root=repo / "docs/anatomy")
            diff = ask.diff_hashes({"gone": {"hash": "old", "file_count": 1}}, fresh)
            self.assertEqual(diff["removed"], ["gone"])
            self.assertEqual(diff["errors"], {})


class SyntaxTests(unittest.TestCase):
    def test_all_python_files_parse_as_python38(self):
        roots = [SCRIPTS, ASK_SCRIPTS, GATE_SCRIPTS, TESTS_DIR]
        for root in roots:
            for path in root.glob("*.py"):
                with self.subTest(path=path.name):
                    ast.parse(path.read_text(), feature_version=(3, 8))


if __name__ == "__main__":
    unittest.main(verbosity=2)
