"""AST and code-graph analysis.

Python files are parsed with the stdlib `ast` module (accurate symbols,
signatures, docstrings, call edges). Non-Python files use conservative regex
heuristics so JavaScript/TypeScript/Go/Java still contribute symbols. All
outputs are size-capped so a pathological repository cannot blow up memory.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

LANGUAGE_BY_SUFFIX = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript", ".go": "go", ".rb": "ruby",
    ".java": "java", ".php": "php", ".c": "c", ".h": "c", ".cpp": "cpp",
    ".hpp": "cpp", ".cc": "cpp", ".cs": "csharp", ".rs": "rust",
    ".swift": "swift", ".kt": "kotlin", ".scala": "scala", ".sh": "shell",
    ".sql": "sql", ".html": "html", ".css": "css", ".md": "markdown",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
}

MAX_SYMBOLS_PER_FILE = 200
MAX_CALLS_PER_FILE = 400
MAX_GRAPH_NODES = 500
MAX_GRAPH_EDGES = 2000


def detect_language(path: str) -> str:
    suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return LANGUAGE_BY_SUFFIX.get("." + suffix, "")


@dataclass
class Symbol:
    name: str
    qualname: str
    kind: str  # function | method | class
    start_line: int
    end_line: int
    signature: str = ""
    docstring: str = ""


@dataclass
class ParsedFile:
    path: str
    language: str
    symbols: List[Symbol] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    calls: List[Tuple[str, int]] = field(default_factory=list)  # (callee, line)
    parse_ok: bool = True


# ── Python (accurate AST) ────────────────────────────────────────────────────

def _py_signature(node: ast.AST) -> str:
    try:
        args: List[str] = []
        a = node.args  # type: ignore[attr-defined]
        pos = list(getattr(a, "posonlyargs", [])) + list(a.args)
        defaults = [None] * (len(pos) - len(a.defaults)) + list(a.defaults)
        for arg, default in zip(pos, defaults):
            text = arg.arg
            if arg.annotation is not None:
                text += f": {ast.unparse(arg.annotation)}"
            if default is not None:
                text += f"={ast.unparse(default)}"
            args.append(text)
        if a.vararg:
            args.append(f"*{a.vararg.arg}")
        elif a.kwonlyargs:
            args.append("*")
        for arg, default in zip(a.kwonlyargs, a.kw_defaults):
            text = arg.arg
            if default is not None:
                text += f"={ast.unparse(default)}"
            args.append(text)
        if a.kwarg:
            args.append(f"**{a.kwarg.arg}")
        returns = ""
        if getattr(node, "returns", None) is not None:
            returns = f" -> {ast.unparse(node.returns)}"
        return f"({', '.join(args)}){returns}"
    except Exception:
        return "(...)"


def _py_parse(path: str, source: str) -> ParsedFile:
    parsed = ParsedFile(path=path, language="python")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        parsed.parse_ok = False
        return parsed

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module = getattr(node, "module", None)
            for alias in node.names:
                parsed.imports.append(module or alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if len(parsed.symbols) >= MAX_SYMBOLS_PER_FILE:
                continue
            kind = "class" if isinstance(node, ast.ClassDef) else (
                "method" if _is_method(node, tree) else "function"
            )
            doc = ast.get_docstring(node) or ""
            parsed.symbols.append(
                Symbol(
                    name=node.name,
                    qualname=node.name,
                    kind=kind,
                    start_line=node.lineno,
                    end_line=getattr(node, "end_line", node.lineno),
                    signature=_py_signature(node) if kind != "class" else "",
                    docstring=doc.split("\n")[0][:500],
                )
            )
        elif isinstance(node, ast.Call):
            if len(parsed.calls) < MAX_CALLS_PER_FILE:
                name = _call_name(node.func)
                if name:
                    parsed.calls.append((name, node.lineno))
    return parsed


def _is_method(node: ast.AST, tree: ast.AST) -> bool:
    # A function whose direct parent scope in the walk is a class body; walk
    # does not track parents, so approximate: any function defined inside a
    # ClassDef anywhere in the tree is a method candidate. Precise parentage
    # is not needed for graph purposes.
    for parent in ast.walk(tree):
        if isinstance(parent, ast.ClassDef):
            for child in ast.walk(parent):
                if child is node:
                    return True
    return False


def _call_name(func: ast.AST) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        parts: List[str] = []
        node: ast.AST = func
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


# ── Regex heuristics (other languages) ───────────────────────────────────────

_JS_FUNC = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)", re.M
)
_JS_METHOD = re.compile(
    r"^\s{2,}(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*\{", re.M
)
_JS_CLASS = re.compile(r"^\s*(?:export\s+)?class\s+(\w+)", re.M)
_GO_FUNC = re.compile(r"^func\s+(?:\([^)]*\)\s*)?(\w+)\s*\(([^)]*)\)", re.M)
_OTHER_FUNC = re.compile(r"^\s*(?:pub\s+)?(?:fn|def|func)\s+(\w+)\s*\(([^)]*)\)", re.M)


def _regex_parse(path: str, source: str, language: str) -> ParsedFile:
    parsed = ParsedFile(path=path, language=language)
    patterns: List[Tuple[str, re.Pattern]] = []
    if language in ("javascript", "typescript"):
        patterns = [("function", _JS_FUNC), ("class", _JS_CLASS), ("method", _JS_METHOD)]
    elif language == "go":
        patterns = [("function", _GO_FUNC)]
    else:
        patterns = [("function", _OTHER_FUNC)]

    for kind, pattern in patterns:
        for match in pattern.finditer(source):
            if len(parsed.symbols) >= MAX_SYMBOLS_PER_FILE:
                break
            name = match.group(1)
            line = source.count("\n", 0, match.start()) + 1
            parsed.symbols.append(
                Symbol(
                    name=name,
                    qualname=name,
                    kind=kind,
                    start_line=line,
                    end_line=line,
                    signature=f"({match.group(2).strip()[:200]})" if kind != "class" else "",
                )
            )
    for match in re.finditer(r"(?:from\s+['\"]([^'\"]+)['\"]|import\s+.+from\s+['\"]([^'\"]+)['\"]|import\s+\"([^\"]+\")|(?:import|require)\s*\(?\s*['\"]([^'\"]+)['\"])", source):
        module = next(g for g in match.groups() if g)
        parsed.imports.append(module)
    for match in list(re.finditer(r"\b([A-Za-z_]\w*)\s*\(", source))[:MAX_CALLS_PER_FILE]:
        name = match.group(1)
        if name not in ("if", "for", "while", "switch", "catch", "return", "function"):
            line = source.count("\n", 0, match.start()) + 1
            parsed.calls.append((name, line))
    return parsed


def parse_file(path: str, source: str) -> ParsedFile:
    language = detect_language(path)
    if language == "python":
        return _py_parse(path, source)
    return _regex_parse(path, source, language)


def top_level_symbol_spans(source: str) -> List[Tuple[int, int]]:
    """Top-level def/class line spans, used by rag.chunk_code_file."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    spans: List[Tuple[int, int]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            end = getattr(node, "end_line", node.lineno) or node.lineno
            spans.append((node.lineno, end))
    return sorted(spans)


# ── Repository-level graph ───────────────────────────────────────────────────

@dataclass
class CodeGraph:
    nodes: List[Dict] = field(default_factory=list)   # {id, path, name, kind}
    edges: List[Tuple[str, str, str]] = field(default_factory=list)  # (src, dst, kind)

    def to_dict(self) -> Dict:
        return {"nodes": self.nodes, "edges": [list(e) for e in self.edges]}


def build_code_graph(files: List[ParsedFile]) -> CodeGraph:
    """Build a repo graph: defines edges (file → symbol) and call/import edges
    between files when a callee matches a symbol defined in another file."""
    graph = CodeGraph()
    symbol_files: Dict[str, str] = {}
    file_symbols: Dict[str, List[str]] = {}

    for parsed in files:
        names = []
        for sym in parsed.symbols:
            if len(graph.nodes) >= MAX_GRAPH_NODES:
                break
            node_id = f"{parsed.path}::{sym.qualname}"
            graph.nodes.append(
                {"id": node_id, "path": parsed.path, "name": sym.name, "kind": sym.kind}
            )
            names.append(sym.qualname)
            symbol_files.setdefault(sym.name, parsed.path)
        file_symbols[parsed.path] = names

    for parsed in files:
        # File → file import edges.
        for module in parsed.imports:
            for other_path in file_symbols:
                if other_path == parsed.path:
                    continue
                stem = other_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                if stem and stem in module:
                    if len(graph.edges) < MAX_GRAPH_EDGES:
                        graph.edges.append((parsed.path, other_path, "imports"))
                    break
        # Call edges: callee defined in another file.
        for callee, _line in parsed.calls:
            target = symbol_files.get(callee)
            if target and target != parsed.path:
                if len(graph.edges) < MAX_GRAPH_EDGES:
                    graph.edges.append((parsed.path, target, "calls"))
    return graph


def graph_summary(graph: CodeGraph, max_items: int = 8) -> str:
    """Compact textual summary for LLM agent context."""
    if not graph.nodes:
        return ""
    by_file: Dict[str, List[str]] = {}
    for node in graph.nodes:
        by_file.setdefault(node["path"], []).append(f"{node['name']} ({node['kind']})")
    lines = []
    for path, names in list(by_file.items())[:max_items]:
        lines.append(f"- {path}: {', '.join(names[:max_items])}")
    if len(graph.edges) > 0:
        lines.append(f"- {len(graph.edges)} cross-file call/import edges detected")
    return "\n".join(lines)
