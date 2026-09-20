"""Unified diff parser tests."""
from app.utils import (
    ADDED,
    CONTEXT,
    REMOVED,
    extract_code_snippets,
    parse_diff,
    parse_unified_diff,
)

STANDARD_DIFF = """diff --git a/src/auth.ts b/src/auth.ts
index e9f6d1a..0c5bb21 100644
--- a/src/auth.ts
+++ b/src/auth.ts
@@ -10,7 +10,8 @@ export async function login() {
 context line
-removed line
+added line 1
+added line 2
 another context
"""


def test_standard_diff_paths_and_lines():
    files = parse_unified_diff(STANDARD_DIFF)
    assert len(files) == 1
    f = files[0]
    assert f.old_path == "src/auth.ts"
    assert f.new_path == "src/auth.ts"
    assert not f.is_binary
    assert len(f.hunks) == 1
    hunk = f.hunks[0]
    assert (hunk.old_start, hunk.new_start) == (10, 10)
    kinds = [line.kind for line in hunk.lines]
    assert kinds == [CONTEXT, REMOVED, ADDED, ADDED, CONTEXT]
    added = [line for line in hunk.lines if line.kind == ADDED]
    assert [line.new_lineno for line in added] == [11, 12]


def test_multiple_files():
    diff = STANDARD_DIFF + """diff --git a/src/api/users.py b/src/api/users.py
--- a/src/api/users.py
+++ b/src/api/users.py
@@ -1,3 +1,4 @@
+new line
"""
    files = parse_unified_diff(diff)
    assert [f.new_path for f in files] == ["src/auth.ts", "src/api/users.py"]


def test_multiple_hunks():
    diff = """diff --git a/x.txt b/x.txt
--- a/x.txt
+++ b/x.txt
@@ -1,2 +1,2 @@
 one
-two
+TWO
@@ -20,3 +20,4 @@
 twenty
+twenty-one
 thirty
"""
    files = parse_unified_diff(diff)
    assert len(files[0].hunks) == 2
    assert files[0].hunks[1].old_start == 20


def test_new_file():
    diff = """diff --git a/new.py b/new.py
new file mode 100644
--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+a
+b
"""
    f = parse_unified_diff(diff)[0]
    assert f.is_new
    assert f.old_path is None
    assert f.new_path == "new.py"


def test_deleted_file():
    diff = """diff --git a/gone.py b/gone.py
deleted file mode 100644
--- a/gone.py
+++ /dev/null
@@ -1,1 +0,0 @@
-old
"""
    f = parse_unified_diff(diff)[0]
    assert f.is_deleted
    assert f.new_path is None
    assert f.path == "gone.py"


def test_renamed_file():
    diff = """diff --git a/old.py b/new.py
similarity index 90%
rename from old.py
rename to new.py
"""
    f = parse_unified_diff(diff)[0]
    assert f.is_renamed
    assert f.old_path == "old.py"
    assert f.new_path == "new.py"


def test_binary_file():
    diff = """diff --git a/logo.png b/logo.png
index 123..456 100644
Binary files a/logo.png and b/logo.png differ
"""
    f = parse_unified_diff(diff)[0]
    assert f.is_binary
    assert f.hunks == []


def test_binary_section_removed_from_clean_diff():
    cleaned = parse_diff("""diff --git a/logo.png b/logo.png
Binary files a/logo.png and b/logo.png differ
diff --git a/code.py b/code.py
--- a/code.py
+++ b/code.py
@@ -1,1 +1,1 @@
-old
+new
""")
    lines = cleaned.splitlines()
    assert "Binary files" not in cleaned
    assert lines[0].startswith("diff --git a/code.py")
    assert "logo.png" not in cleaned


def test_malformed_diff_is_tolerated():
    assert parse_unified_diff("not a diff at all\njust text\n") == []
    assert parse_unified_diff("") == []


def test_diff_without_preamble_is_parsed():
    diff = """--- a/x.txt
+++ b/x.txt
@@ -1,1 +1,1 @@
-old
+new
"""
    files = parse_unified_diff(diff)
    assert len(files) == 1
    assert files[0].new_path == "x.txt"


def test_no_newline_marker_ignored():
    diff = """--- a/x.txt
+++ b/x.txt
@@ -1,1 +1,1 @@
-old
+new
\\ No newline at end of file
"""
    lines = parse_unified_diff(diff)[0].hunks[0].lines
    assert all(line.content not in ("No newline at end of file",) for line in lines)


def test_extract_code_snippets_traces_file_and_line():
    snippets = extract_code_snippets(STANDARD_DIFF)
    assert "src/auth.ts:11: added line 1" in snippets
    assert "src/auth.ts:12: added line 2" in snippets
    assert "removed line" not in snippets


def test_extract_code_snippets_fallback_for_free_text():
    assert extract_code_snippets("+foo\n+bar") == ": foo\n: bar"
