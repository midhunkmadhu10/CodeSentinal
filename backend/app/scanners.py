"""Deterministic security scanners.

Regex-based detectors for the highest-signal issue classes. They run on every
review with zero LLM cost and their hits are sent to the LLM agents for
corroboration. Each hit is a dict compatible with the ReviewFinding schema:
category, severity, file, line, snippet, rule, cwe, suggestion.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from .observability import METRICS
from .utils import ADDED, parse_unified_diff

ScannerHit = Dict[str, Any]

MAX_SNIPPET_CHARS = 300
MAX_HITS_PER_SCANNER = 40


class Scanner:
    """One detector: name, description, line patterns."""

    def __init__(
        self,
        name: str,
        description: str,
        category: str,
        severity: str,
        rule: str,
        cwe: str,
        patterns: List[re.Pattern],
        suggestion: str,
        allow_tests: bool = True,
    ):
        self.name = name
        self.description = description
        self.category = category
        self.severity = severity
        self.rule = rule
        self.cwe = cwe
        self.patterns = patterns
        self.suggestion = suggestion
        self.allow_tests = allow_tests

    def scan_line(self, line: str) -> bool:
        return any(p.search(line) for p in self.patterns)


def _rx(pattern: str) -> re.Pattern:
    return re.compile(pattern)


SCANNERS: List[Scanner] = [
    Scanner(
        name="hardcoded_secrets",
        description="Hardcoded credentials, API keys, tokens, or private keys",
        category="secrets",
        severity="High",
        rule="Never hardcode secrets. Load them from environment variables or a secrets manager.",
        cwe="CWE-798",
        suggestion="Move the secret to an environment variable and read it at runtime.",
        patterns=[
            _rx(r"""(?i)(api[_-]?key|secret|password|passwd|token|auth[_-]?token|access[_-]?key)\s*[:=]\s*["'][^"']{8,}["']"""),
            _rx(r"""(?i)bearer\s+["'][A-Za-z0-9\-_.]{20,}["']"""),
            _rx(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
            _rx(r"""(?i)(aws_access_key_id|aws_secret_access_key)\s*[:=]\s*["'][A-Za-z0-9/+=]{16,}["']"""),
            _rx(r"""(?i)sk-[A-Za-z0-9]{20,}"""),
            _rx(r"ghp_[A-Za-z0-9]{30,}"),
        ],
    ),
    Scanner(
        name="sql_injection",
        description="String-formatted SQL queries (f-strings, format, concatenation)",
        category="sql_injection",
        severity="High",
        rule="Use parameterized queries or an ORM; never build SQL by string formatting.",
        cwe="CWE-89",
        suggestion="Replace string formatting with parameterized queries (e.g. cursor.execute(sql, (param,))).",
        patterns=[
            _rx(r"""(?i)(select|insert\s+into|update|delete\s+from)\s.+(f["']|\.format\(|%\s*\(|\+\s*\w+)"""),
            _rx(r"""(?i)execute\s*\(\s*f["']""",),
            _rx(r"""(?i)execute\s*\(\s*["'][^"']*["']\s*\+"""),
            _rx(r"""(?i)query\s*=\s*f["']\s*(select|insert|update|delete)"""),
        ],
    ),
    Scanner(
        name="dangerous_calls",
        description="Dangerous dynamic execution (eval, exec, pickle, system shells)",
        category="dangerous_calls",
        severity="High",
        rule="Avoid eval/exec and unsafe deserialization of untrusted input.",
        cwe="CWE-95",
        suggestion="Replace dynamic evaluation with explicit parsing or a safe serializer such as JSON.",
        patterns=[
            _rx(r"\beval\s*\("),
            _rx(r"\bexec\s*\("),
            _rx(r"\bpickle\.loads?\s*\("),
            _rx(r"\byaml\.load\s*\((?![^)]*Loader\s*=\s*yaml\.SafeLoader)"),
            _rx(r"os\.system\s*\("),
            _rx(r"subprocess\.\w+\([^)]*shell\s*=\s*True"),
        ],
    ),
    Scanner(
        name="weak_crypto",
        description="Weak or broken cryptographic primitives",
        category="weak_crypto",
        severity="High",
        rule="Use modern algorithms: SHA-256+ for hashing, AES-GCM, and vetted libraries.",
        cwe="CWE-327",
        suggestion="Switch to hashlib.sha256/bcrypt/argon2 and a vetted TLS configuration.",
        patterns=[
            _rx(r"\bhashlib\.(md5|sha1)\s*\("),
            _rx(r"\bDES\.|\bRC4\b|\bBlowfish\b"),
            _rx(r"(?i)insecure[_-]?md5|use[_-]?md5\s*=\s*True"),
        ],
    ),
    Scanner(
        name="insecure_tls",
        description="TLS certificate verification disabled",
        category="insecure_tls",
        severity="High",
        rule="Never disable certificate verification; keep verify=True.",
        cwe="CWE-295",
        suggestion="Remove verify=False / InsecureSkipVerify and trust the system CA bundle.",
        patterns=[
            _rx(r"verify\s*=\s*False"),
            _rx(r"InsecureSkipVerify\s*:\s*true"),
            _rx(r"ssl\._create_unverified_context\s*\("),
            _rx(r"rejectUnauthorized\s*:\s*false"),
        ],
    ),
    Scanner(
        name="insecure_config",
        description="Insecure application configuration (debug mode, wildcard CORS, permissive auth)",
        category="insecure_config",
        severity="Medium",
        rule="Disable debug mode and permissive CORS in production configurations.",
        cwe="CWE-489",
        suggestion="Bind debug=False, restrict CORS origins, and require strong session settings.",
        allow_tests=False,
        patterns=[
            _rx(r"(?i)debug\s*=\s*True\b"),
            _rx(r"(?i)allow_origins\s*=\s*\[?\s*[\"']\*[\"']"),
            _rx(r"(?i)Access-Control-Allow-Origin[\"']?\s*[,:]\s*[\"']\*[\"']"),
            _rx(r"(?i)secret_key\s*=\s*[\"'](changeme|secret|password|test)[\"']"),
        ],
    ),
    Scanner(
        name="path_traversal",
        description="File paths built from unvalidated user input",
        category="path_traversal",
        severity="Medium",
        rule="Validate and normalize file paths; resolve within an allowed root.",
        cwe="CWE-22",
        suggestion="Use os.path.realpath + a prefix check against an allow-listed base directory.",
        patterns=[
            _rx(r"""(?i)open\s*\(\s*[^)]*(request|params|args|input|user)\w*\[[^\]]*\]"""),
            _rx(r"os\.path\.join\s*\([^)]*(?:request\.|params\b|args\b|user_input)"),
        ],
    ),
    Scanner(
        name="jwt_weakness",
        description="Weak JWT configuration (none algorithm, missing expiry, hardcoded secret)",
        category="jwt_weakness",
        severity="High",
        rule="Sign JWTs with a strong server-side secret, explicit algorithm, and expiry.",
        cwe="CWE-347",
        suggestion="Use HS256/RS256 with a strong secret from the environment and set exp claims.",
        patterns=[
            _rx(r"""(?i)jwt\.encode\s*\([^)]*algorithm\s*=\s*[\"']none[\"']"""),
            _rx(r"""(?i)jwt\.decode\s*\([^)]*(?:verify\s*=\s*False|algorithms\s*=\s*\[\s*[\"']none)"""),
        ],
    ),
]


def _is_test_path(path: str) -> bool:
    lowered = path.lower()
    return (
        "test" in lowered
        or lowered.startswith("tests/")
        or "/tests/" in lowered
        or lowered.endswith("_test.go")
        or lowered.endswith(".test.ts")
        or lowered.endswith(".test.js")
        or lowered.endswith(".spec.ts")
        or lowered.endswith(".spec.js")
    )


def _hit(scanner: Scanner, path: str, line_no: int, content: str) -> ScannerHit:
    return {
        "source": "scanner",
        "scanner": scanner.name,
        "category": scanner.category,
        "severity": scanner.severity,
        "file": path,
        "line": line_no,
        "file_line": f"{path}:{line_no}" if line_no else path,
        "title": f"{scanner.category.replace('_', ' ').title()} detected by {scanner.name}",
        "description": scanner.description,
        "rule": scanner.rule,
        "cwe": scanner.cwe,
        "snippet": content.strip()[:MAX_SNIPPET_CHARS],
        "suggestion": scanner.suggestion,
        "confidence": 0.6,
        "corroborated": False,
    }


def scan_added_lines(diff_text: str) -> List[ScannerHit]:
    """Scan the added lines of a unified diff; returns non-overlapping hits."""
    hits: List[ScannerHit] = []
    seen: set = set()

    files = parse_unified_diff(diff_text)
    sources: List[tuple] = []
    if files:
        for f in files:
            if f.is_binary:
                continue
            for hunk in f.hunks:
                for dl in hunk.lines:
                    if dl.kind == ADDED and dl.new_lineno:
                        sources.append((f.path, dl.new_lineno, dl.content))
    else:
        current_file = ""
        for idx, line in enumerate(diff_text.splitlines(), start=1):
            if line.startswith("+++ b/"):
                current_file = line[6:]
            elif line.startswith("+") and not line.startswith("+++"):
                sources.append((current_file, idx, line[1:]))

    for path, line_no, content in sources:
        for scanner in SCANNERS:
            if scanner.allow_tests is False and _is_test_path(path):
                continue
            if scanner.scan_line(content):
                key = (path, line_no, scanner.name)
                if key in seen:
                    continue
                seen.add(key)
                hits.append(_hit(scanner, path, line_no, content))
                METRICS.inc("scanner_findings_total", scanner=scanner.name)
                if len(hits) >= 200:
                    return hits
    return hits


def scan_source_file(path: str, content: str) -> List[ScannerHit]:
    """Scan a whole source file (used during repository indexing)."""
    hits: List[ScannerHit] = []
    for line_no, line in enumerate(content.splitlines(), start=1):
        for scanner in SCANNERS:
            if scanner.allow_tests is False and _is_test_path(path):
                continue
            if scanner.scan_line(line):
                hits.append(_hit(scanner, path, line_no, line))
                if len(hits) >= MAX_HITS_PER_SCANNER:
                    return hits
    return hits


def scanner_summary(hits: List[ScannerHit], max_lines: int = 12) -> str:
    """Compact bullet list of scanner hits for LLM agent context."""
    if not hits:
        return "No deterministic scanner hits on the added lines."
    lines = [
        f"- [{h['severity']}] {h['file_line']} {h['scanner']}: {h['snippet'][:120]}"
        for h in hits[:max_lines]
    ]
    if len(hits) > max_lines:
        lines.append(f"- ... and {len(hits) - max_lines} more")
    return "\n".join(lines)
