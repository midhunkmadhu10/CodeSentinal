"""Tests for evaluation module."""

import pytest
from unittest.mock import MagicMock, patch

from app.evaluation import (
    score_case,
    _added_lines,
    _finding_key,
    run_evaluation,
    GOLDEN_CASES,
)
from app.utils import parse_unified_diff


class TestEvaluationHelpers:
    def test_finding_key_with_file_and_line(self):
        """_finding_key extracts file and line from finding dict."""
        finding = {"file": "app/db.py", "line": 42}
        result = _finding_key(finding)
        assert result == ("app/db.py", 42)

    def test_finding_key_with_file_line_field(self):
        """_finding_key extracts file from file_line field, line from 'line' field."""
        finding = {"file_line": "app/db.py:42", "line": 42}
        result = _finding_key(finding)
        assert result == ("app/db.py", 42)

    def test_finding_key_with_no_line(self):
        """_finding_key returns 0 as line if missing."""
        finding = {"file": "app/db.py"}
        result = _finding_key(finding)
        assert result == ("app/db.py", 0)

    def test_added_lines_from_diff(self):
        """_added_lines extracts added line numbers from diff."""
        diff = """diff --git a/app/db.py b/app/db.py
--- a/app/db.py
+++ b/app/db.py
@@ -1,3 +1,3 @@
 def get_user(id):
-    return db.query(id)
+    return db.execute(f"SELECT * FROM users WHERE id = {id}")
"""
        result = _added_lines(diff)
        # Should have the added line (line 3 in the new file)
        assert len(result) > 0


class TestScoreCase:
    def test_score_case_perfect_match(self):
        """score_case returns 1.0 precision/recall/F1 for perfect match."""
        produced = [
            {"file": "app/db.py", "line": 3, "category": "sql_injection", "source": "scanner"}
        ]
        expected = [
            {"file": "app/db.py", "line": 3, "categories": ["sql_injection"]}
        ]
        
        p, r, f1, misses = score_case(produced, expected)
        
        assert p == 1.0
        assert r == 1.0
        assert f1 == 1.0
        assert misses == []

    def test_score_case_no_expected(self):
        """score_case returns 1.0 precision if no expected findings and none produced."""
        produced = []
        expected = []
        
        p, r, f1, misses = score_case(produced, expected)
        
        assert p == 1.0
        assert r == 1.0
        assert f1 == 1.0

    def test_score_case_false_positive(self):
        """score_case penalizes false positives (low precision)."""
        produced = [
            {"file": "app/db.py", "line": 3, "category": "sql_injection", "source": "scanner"}
        ]
        expected = []
        
        p, r, f1, misses = score_case(produced, expected)
        
        assert p == 0.0
        assert r == 1.0
        assert f1 == 0.0

    def test_score_case_false_negative(self):
        """score_case penalizes false negatives (low recall)."""
        produced = []
        expected = [
            {"file": "app/db.py", "line": 3, "categories": ["sql_injection"]}
        ]
        
        p, r, f1, misses = score_case(produced, expected)
        
        # False negative: we expected a finding but got none
        assert r == 0.0

    def test_score_case_partial_match(self):
        """score_case handles partial matches."""
        produced = [
            {"file": "app/db.py", "line": 3, "category": "sql_injection", "source": "scanner"},
            {"file": "app/db.py", "line": 5, "category": "sql_injection", "source": "scanner"},
        ]
        expected = [
            {"file": "app/db.py", "line": 3, "categories": ["sql_injection"]}
        ]
        
        p, r, f1, misses = score_case(produced, expected)
        
        assert p == 0.5  # 1 matched / 2 produced
        assert r == 1.0  # 1 matched / 1 expected
        assert f1 > 0 and f1 < 1


class TestGoldenCases:
    def test_golden_cases_loaded(self):
        """GOLDEN_CASES should be loaded from fixtures."""
        assert len(GOLDEN_CASES) > 0
        
    def test_golden_cases_have_required_fields(self):
        """Each golden case has required fields."""
        for case in GOLDEN_CASES:
            assert "id" in case
            assert "description" in case
            assert "diff" in case
            assert "expected" in case
            assert isinstance(case["expected"], list)

    def test_golden_cases_expected_format(self):
        """Expected findings have correct format."""
        for case in GOLDEN_CASES:
            for exp in case["expected"]:
                assert "file" in exp
                assert "line" in exp or "line" is None
                assert "categories" in exp
                assert isinstance(exp["categories"], list)


class TestRunEvaluation:
    @patch("app.evaluation.scan_added_lines")
    @patch("app.evaluation.run_all_agents")
    def test_run_evaluation_scanners_only(self, mock_run_agents, mock_scan):
        """run_evaluation with use_llm=False only runs scanners."""
        mock_scan.return_value = [
            {
                "file": "app/db.py",
                "line": 3,
                "category": "sql_injection",
                "severity": "High",
                "scanner": "regex_scanner",
            }
        ]
        
        from app.database import SessionLocal, init_db
        init_db()
        db = SessionLocal()
        
        try:
            result = run_evaluation(db, use_llm=False, notes="Test run")
            
            assert result.scores is not None
            assert "precision" in result.scores
            assert "recall" in result.scores
            assert "f1" in result.scores
            assert result.scores["use_llm"] is False
        finally:
            db.close()

    @patch("app.evaluation.scan_added_lines")
    @patch("app.evaluation.run_all_agents")
    def test_run_evaluation_with_agents(self, mock_run_agents, mock_scan):
        """run_evaluation with use_llm=True runs agents."""
        mock_scan.return_value = []
        mock_run_agents.return_value = []
        
        from app.database import SessionLocal, init_db
        init_db()
        db = SessionLocal()
        
        try:
            result = run_evaluation(db, use_llm=True, notes="Test run")
            
            assert result.scores is not None
            assert result.scores["use_llm"] is True
        finally:
            db.close()
