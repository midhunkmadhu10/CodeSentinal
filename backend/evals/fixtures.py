"""Golden evaluation fixtures: vulnerable diffs + expected findings.

Each case pairs a diff with the findings a correct review must produce.
Categories are normalized (e.g., "sql_injection", "secrets", "dangerous_calls").
Scanners-only cases should find hits; clean diffs should produce none.
"""

# SQL Injection via f-string
SQLI_FSTRING = {
    "id": "sqli_fstring",
    "description": "f-string SQL query is detected",
    "diff": """diff --git a/app/users.py b/app/users.py
--- a/app/users.py
+++ b/app/users.py
@@ -1,4 +1,4 @@
 def get_user(conn, user_id):
-    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
+    return conn.execute(f"SELECT * FROM users WHERE id = {user_id}")
""",
    "expected": [
        {"file": "app/users.py", "line": 4, "categories": ["sql_injection", "injection"]}
    ],
    "llm_optional": True,
}

# Hardcoded API key
HARDCODED_SECRET = {
    "id": "hardcoded_secret",
    "description": "hardcoded API key is detected",
    "diff": """diff --git a/config/settings.py b/config/settings.py
--- a/config/settings.py
+++ b/config/settings.py
@@ -1,3 +1,3 @@
 import os
-DATABASE_URL = os.environ["DATABASE_URL"]
+API_KEY = "sk-live-abcdefghijklmnopqrstuvwxyz123456"
""",
    "expected": [
        {"file": "config/settings.py", "line": 3, "categories": ["secrets", "hardcoded_credentials"]}
    ],
    "llm_optional": True,
}

# eval() on untrusted input
DANGEROUS_EVAL = {
    "id": "dangerous_eval",
    "description": "eval() on untrusted input is detected",
    "diff": """diff --git a/tools/run.py b/tools/run.py
--- a/tools/run.py
+++ b/tools/run.py
@@ -1,3 +1,3 @@
-import json
-def run(payload):
-    return json.loads(payload)
+def run(payload):
+    return eval(payload)
""",
    "expected": [
        {"file": "tools/run.py", "line": 3, "categories": ["dangerous_calls", "code_injection"]}
    ],
    "llm_optional": True,
}

# pickle.loads on untrusted data
DANGEROUS_PICKLE = {
    "id": "dangerous_pickle",
    "description": "pickle.loads on untrusted data is detected",
    "diff": """diff --git a/handlers/deserialize.py b/handlers/deserialize.py
--- a/handlers/deserialize.py
+++ b/handlers/deserialize.py
@@ -1,5 +1,5 @@
 import pickle
 def load_obj(data):
-    import json
-    return json.loads(data)
+    return pickle.loads(data)
""",
    "expected": [
        {"file": "handlers/deserialize.py", "line": 4, "categories": ["dangerous_calls", "deserialization"]}
    ],
    "llm_optional": True,
}

# Weak crypto (MD5 for security)
WEAK_CRYPTO_MD5 = {
    "id": "weak_crypto_md5",
    "description": "MD5 used for security (password hashing)",
    "diff": """diff --git a/auth/hash.py b/auth/hash.py
--- a/auth/hash.py
+++ b/auth/hash.py
@@ -1,4 +1,4 @@
 import hashlib
 def hash_password(password):
-    return hashlib.sha256(password.encode()).hexdigest()
+    return hashlib.md5(password.encode()).hexdigest()
""",
    "expected": [
        {"file": "auth/hash.py", "line": 4, "categories": ["weak_crypto", "weak_hash"]}
    ],
    "llm_optional": True,
}

# Subprocess with shell=True
SUBPROCESS_SHELL_TRUE = {
    "id": "subprocess_shell_true",
    "description": "subprocess with shell=True on user input",
    "diff": """diff --git a/tasks/executor.py b/tasks/executor.py
--- a/tasks/executor.py
+++ b/tasks/executor.py
@@ -1,4 +1,4 @@
 import subprocess
 def run_command(cmd):
-    return subprocess.run(cmd, shell=False)
+    return subprocess.run(cmd, shell=True)
""",
    "expected": [
        {"file": "tasks/executor.py", "line": 4, "categories": ["dangerous_calls", "command_injection"]}
    ],
    "llm_optional": True,
}

# Path traversal vulnerability
PATH_TRAVERSAL = {
    "id": "path_traversal",
    "description": "path traversal from user input",
    "diff": """diff --git a/fileops/reader.py b/fileops/reader.py
--- a/fileops/reader.py
+++ b/fileops/reader.py
@@ -1,4 +1,4 @@
 def read_file(user_path):
-    safe_path = os.path.join("/data", os.path.basename(user_path))
+    safe_path = os.path.join("/data", user_path)
     return open(safe_path).read()
""",
    "expected": [
        {"file": "fileops/reader.py", "line": 3, "categories": ["path_traversal", "directory_traversal"]}
    ],
    "llm_optional": True,
}

# os.system with user input
OSSYSTEM_INJECTION = {
    "id": "ossystem_injection",
    "description": "os.system called with user input",
    "diff": """diff --git a/cmd/run.py b/cmd/run.py
--- a/cmd/run.py
+++ b/cmd/run.py
@@ -1,3 +1,3 @@
 import os
 def execute(user_cmd):
-    return os.system("safe_command")
+    return os.system(user_cmd)
""",
    "expected": [
        {"file": "cmd/run.py", "line": 4, "categories": ["dangerous_calls", "command_injection"]}
    ],
    "llm_optional": True,
}

# YAML unsafe load
YAML_UNSAFE_LOAD = {
    "id": "yaml_unsafe_load",
    "description": "yaml.load without Loader",
    "diff": """diff --git a/config/parser.py b/config/parser.py
--- a/config/parser.py
+++ b/config/parser.py
@@ -1,3 +1,3 @@
 import yaml
 def parse_config(data):
-    return yaml.safe_load(data)
+    return yaml.load(data)
""",
    "expected": [
        {"file": "config/parser.py", "line": 4, "categories": ["dangerous_calls", "deserialization"]}
    ],
    "llm_optional": True,
}

# Benign refactor (should produce no findings)
CLEAN_DIFF_REFACTOR = {
    "id": "clean_diff_refactor",
    "description": "benign code refactor produces no findings",
    "diff": """diff --git a/app/math.py b/app/math.py
--- a/app/math.py
+++ b/app/math.py
@@ -1,2 +1,4 @@
 def add(a, b):
-    return a + b
+    \"\"\"Return the sum of two numbers.\"\"\"
+    return a + b
""",
    "expected": [],
    "llm_optional": True,
}

# Benign doc string addition
CLEAN_DIFF_DOCS = {
    "id": "clean_diff_docs",
    "description": "adding docstrings is benign",
    "diff": """diff --git a/lib/math.py b/lib/math.py
--- a/lib/math.py
+++ b/lib/math.py
@@ -1,2 +1,5 @@
 def multiply(x, y):
+    \"\"\"Multiply two numbers.
+    Args: x, y (int or float)
+    \"\"\"
     return x * y
""",
    "expected": [],
    "llm_optional": True,
}

# Multiple findings in one diff
MULTIPLE_VULNS = {
    "id": "multiple_vulns",
    "description": "multiple vulnerabilities in one diff",
    "diff": """diff --git a/app/api.py b/app/api.py
--- a/app/api.py
+++ b/app/api.py
@@ -1,7 +1,7 @@
 import subprocess
 import hashlib
-def handle_request(user_input):
-    hash_val = hashlib.sha256(user_input.encode()).hexdigest()
+def handle_request(user_input):
+    hash_val = hashlib.md5(user_input.encode()).hexdigest()
-    query = "SELECT * FROM users WHERE id = ?"
-    result = db.execute(query, (user_input,))
+    query = f"SELECT * FROM users WHERE id = {user_input}"
+    result = db.execute(query)
     subprocess.run(user_input, shell=True)
""",
    "expected": [
        {"file": "app/api.py", "line": 4, "categories": ["weak_crypto", "weak_hash"]},
        {"file": "app/api.py", "line": 6, "categories": ["sql_injection", "injection"]},
        {"file": "app/api.py", "line": 7, "categories": ["dangerous_calls", "command_injection"]},
    ],
    "llm_optional": True,
}

# Random module for security
RANDOM_FOR_SECURITY = {
    "id": "random_for_security",
    "description": "random module used for security token generation",
    "diff": """diff --git a/auth/tokens.py b/auth/tokens.py
--- a/auth/tokens.py
+++ b/auth/tokens.py
@@ -1,4 +1,4 @@
 import random
 def generate_token():
-    return os.urandom(32).hex()
+    return ''.join(random.choices('0123456789', k=32))
""",
    "expected": [
        {"file": "auth/tokens.py", "line": 4, "categories": ["weak_crypto", "insecure_randomness"]}
    ],
    "llm_optional": True,
}

# SQL Injection with format
SQLI_FORMAT = {
    "id": "sqli_format",
    "description": "SQL injection via .format()",
    "diff": """diff --git a/db/queries.py b/db/queries.py
--- a/db/queries.py
+++ b/db/queries.py
@@ -1,3 +1,3 @@
 def search_user(name):
-    query = "SELECT * FROM users WHERE name = ?"
+    query = "SELECT * FROM users WHERE name = '{}'".format(name)
     return db.execute(query)
""",
    "expected": [
        {"file": "db/queries.py", "line": 3, "categories": ["sql_injection", "injection"]}
    ],
    "llm_optional": True,
}

# Variable reassignment (benign)
CLEAN_VAR_REASSIGN = {
    "id": "clean_var_reassign",
    "description": "benign variable reassignment",
    "diff": """diff --git a/lib/calc.py b/lib/calc.py
--- a/lib/calc.py
+++ b/lib/calc.py
@@ -1,3 +1,3 @@
 def compute(x):
     result = x * 2
-    return result
+    return result + 1
""",
    "expected": [],
    "llm_optional": True,
}

# Exec on untrusted input
DANGEROUS_EXEC = {
    "id": "dangerous_exec",
    "description": "exec() on user input",
    "diff": """diff --git a/sandbox/runner.py b/sandbox/runner.py
--- a/sandbox/runner.py
+++ b/sandbox/runner.py
@@ -1,3 +1,3 @@
 def run_code(user_code):
-    return compile(user_code, '<string>', 'eval')
+    exec(user_code)
""",
    "expected": [
        {"file": "sandbox/runner.py", "line": 3, "categories": ["dangerous_calls", "code_injection"]}
    ],
    "llm_optional": True,
}

# ALL GOLDEN CASES
ALL_CASES = [
    SQLI_FSTRING,
    HARDCODED_SECRET,
    DANGEROUS_EVAL,
    DANGEROUS_PICKLE,
    WEAK_CRYPTO_MD5,
    SUBPROCESS_SHELL_TRUE,
    PATH_TRAVERSAL,
    OSSYSTEM_INJECTION,
    YAML_UNSAFE_LOAD,
    CLEAN_DIFF_REFACTOR,
    CLEAN_DIFF_DOCS,
    MULTIPLE_VULNS,
    RANDOM_FOR_SECURITY,
    SQLI_FORMAT,
    CLEAN_VAR_REASSIGN,
    DANGEROUS_EXEC,
]
