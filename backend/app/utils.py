"""Diff parsing and text utilities.

`parse_unified_diff()` turns a unified diff into structured FileDiff/Hunk/Line
objects with real file paths and line numbers, so findings can be traced back
to the exact changed line. `parse_diff()` and `extract_code_snippets()` keep
the simplified string interfaces used by main.py and the RAG pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

CONTEXT = "context"
ADDED = "added"
REMOVED = "removed"


@dataclass
class DiffLine:
    kind: str  # "context" | "added" | "removed"
    content: str  # line content without the diff prefix character
    old_lineno: Optional[int] = None
    new_lineno: Optional[int] = None


@dataclass
class DiffHunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[DiffLine] = field(default_factory=list)


@dataclass
class FileDiff:
    old_path: Optional[str]
    new_path: Optional[str]
    is_binary: bool = False
    is_new: bool = False
    is_deleted: bool = False
    is_renamed: bool = False
    hunks: List[DiffHunk] = field(default_factory=list)

    @property
    def path(self) -> str:
        return self.new_path or self.old_path or "unknown"


def _clean_path(path: str) -> Optional[str]:
    """Normalize the path from a ---/+++ header; None means /dev/null."""
    path = path.split("\t")[0].strip()
    if path == "/dev/null":
        return None
    if path.startswith("a/") or path.startswith("b/"):
        return path[2:]
    return path


def parse_unified_diff(diff_text: str) -> List[FileDiff]:
    """Parse a unified diff into structured per-file data.

    Tolerates malformed input: unrecognized lines are skipped rather than
    raising, so a partially broken diff still yields whatever files parsed.
    """
    files: List[FileDiff] = []
    current: Optional[FileDiff] = None
    hunk: Optional[DiffHunk] = None
    old_line = 0
    new_line = 0

    for raw in diff_text.splitlines():
        if raw.startswith("diff --git "):
            current = FileDiff(old_path=None, new_path=None)
            files.append(current)
            hunk = None
            continue

        if current is None:
            # Tolerate diffs without a "diff --git" preamble.
            if raw.startswith("--- "):
                current = FileDiff(old_path=None, new_path=None)
                files.append(current)
            else:
                continue

        if raw.startswith("--- "):
            current.old_path = _clean_path(raw[4:])
            hunk = None
        elif raw.startswith("+++ "):
            current.new_path = _clean_path(raw[4:])
        elif raw.startswith("new file mode"):
            current.is_new = True
        elif raw.startswith("deleted file mode"):
            current.is_deleted = True
        elif raw.startswith("rename from "):
            current.is_renamed = True
            current.old_path = raw[len("rename from "):].strip()
        elif raw.startswith("rename to "):
            current.is_renamed = True
            current.new_path = raw[len("rename to "):].strip()
        elif raw.startswith("Binary files ") or raw.startswith("GIT binary patch"):
            current.is_binary = True
            hunk = None
        elif match := HUNK_HEADER_RE.match(raw):
            old_line = int(match.group(1))
            new_line = int(match.group(3))
            hunk = DiffHunk(
                old_start=old_line,
                old_count=int(match.group(2) or "1"),
                new_start=new_line,
                new_count=int(match.group(4) or "1"),
            )
            current.hunks.append(hunk)
        elif hunk is not None:
            if raw.startswith("\\"):
                # "\ No newline at end of file" carries no line content.
                continue
            prefix, content = raw[:1], raw[1:]
            if prefix == "+":
                hunk.lines.append(DiffLine(ADDED, content, new_lineno=new_line))
                new_line += 1
            elif prefix == "-":
                hunk.lines.append(DiffLine(REMOVED, content, old_lineno=old_line))
                old_line += 1
            elif prefix == " " or raw == "":
                hunk.lines.append(
                    DiffLine(CONTEXT, content, old_lineno=old_line, new_lineno=new_line)
                )
                old_line += 1
                new_line += 1
            # Any other garbage inside a hunk is ignored.

    return files


def parse_diff(diff_text: str) -> str:
    """Normalize a diff for the LLM prompt: drop binary file sections entirely."""
    cleaned: List[str] = []
    pending_header: Optional[str] = None
    skipping = False
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            pending_header = line
            skipping = False
            continue
        if line.startswith(("Binary files ", "GIT binary patch")):
            skipping = True
            pending_header = None
            continue
        if pending_header is not None:
            cleaned.append(pending_header)
            pending_header = None
        if not skipping:
            cleaned.append(line)
    return "\n".join(cleaned)


def extract_code_snippets(diff: str) -> str:
    """Extract the added lines with file path and new line number.

    Used as a focused retrieval query. Falls back to a line-based heuristic
    when the text does not parse as a unified diff.
    """
    files = parse_unified_diff(diff)
    if files:
        snippets = []
        for f in files:
            if f.is_binary:
                continue
            for hunk in f.hunks:
                for line in hunk.lines:
                    if line.kind == ADDED:
                        snippets.append(f"{f.path}:{line.new_lineno}: {line.content}")
        return "\n".join(snippets)

    snippets = []
    current_file = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            snippets.append(f"{current_file}: {line[1:]}")
    return "\n".join(snippets)
