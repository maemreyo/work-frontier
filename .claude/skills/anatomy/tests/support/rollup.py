"""Minimal test-only fallback for connector-only bundle validation.

An applied repository checkout has the real scripts/rollup.py, which takes
precedence because each production script prepends its own directory to
sys.path. This module only lets subprocess integration tests run before the
bundle is applied to a checkout.
"""
import re

DEPENDS_HEADING_RE = re.compile(r"^#{1,6}\s*Depends on", re.IGNORECASE)
USED_BY_HEADING_RE = re.compile(r"^#{1,6}\s*Used by", re.IGNORECASE)
ANY_HEADING_RE = re.compile(r"^#{1,6}\s")
MODULE_REF_RE = re.compile(r"\*\*`([^`]+)`\*\*")
FOOTER_RE = re.compile(r"Files examined in depth:\s*(.+?)\.?\s*$", re.IGNORECASE)
SAMPLED_RE = re.compile(r"sampled\s+(\d+)\s+of\s+(\d+)", re.IGNORECASE)
ALL_N_RE = re.compile(r"\ball\s+(\d+)\s+files?\b", re.IGNORECASE)


def extract_refs(text, heading_re):
    refs, active = set(), False
    for line in text.splitlines():
        if heading_re.match(line):
            active = True
            continue
        if active and ANY_HEADING_RE.match(line):
            break
        if active:
            refs.update(MODULE_REF_RE.findall(line))
    return refs


def extract_coverage(text):
    match = FOOTER_RE.search(text)
    if not match:
        return "unstated", None
    value = match.group(1).strip().rstrip("*_.").strip()
    if ALL_N_RE.search(value):
        return "full", value
    if SAMPLED_RE.search(value):
        return "sampled", value
    return "listed", value


def find_cycles(graph, cap=25):
    cycles, visited, stack, on_stack = [], set(), [], set()

    def dfs(node):
        if len(cycles) >= cap:
            return
        visited.add(node)
        stack.append(node)
        on_stack.add(node)
        for nxt in sorted(graph.get(node, ())):
            if nxt in on_stack:
                start = stack.index(nxt)
                cycles.append(stack[start:] + [nxt])
            elif nxt not in visited:
                dfs(nxt)
        stack.pop()
        on_stack.discard(node)

    for node in sorted(graph):
        if node not in visited:
            dfs(node)
    return cycles
