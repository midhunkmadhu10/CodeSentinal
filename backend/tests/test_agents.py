"""Tests for agents module: specialized LLM review agents."""

import pytest
from unittest.mock import MagicMock, patch

from app.agents import (
    AgentFinding,
    AgentRun,
    AGENT_IDS,
    run_agent,
    run_all_agents,
    corroborate,
    generate_fixes,
)


class TestAgentFinding:
    def test_to_dict(self):
        """AgentFinding.to_dict() returns all expected keys."""
        finding = AgentFinding(
            agent="security",
            severity="High",
            category="sql_injection",
            title="SQL Injection",
            description="String interpolation in SQL",
            file="app/db.py",
            line=42,
            cwe="CWE-89",
            confidence=0.95,
        )
        result = finding.to_dict()
        assert result["source"] == "agent"
        assert result["agent"] == "security"
        assert result["severity"] == "High"
        assert result["category"] == "sql_injection"
        assert result["file"] == "app/db.py"
        assert result["line"] == 42
        assert result["confidence"] == 0.95


class TestRunAgent:
    @patch("app.agents.llm_chat")
    @patch("app.agents.route")
    def test_run_agent_success(self, mock_route, mock_llm_chat):
        """run_agent successfully parses agent response."""
        mock_route.return_value = MagicMock(model="test-model")
        mock_llm_chat.return_value = MagicMock(
            content='{"findings": [{"severity": "High", "category": "sql_injection", "title": "Test", "description": "Test finding", "file": "app/db.py", "line": 10}]}',
            model="test-model",
            cost_usd=0.01,
        )
        
        diff = "diff content"
        result = run_agent("security", diff)
        
        assert result.agent == "security"
        assert len(result.findings) == 1
        assert result.findings[0].category == "sql_injection"
        assert result.error is None

    @patch("app.agents.llm_chat")
    @patch("app.agents.route")
    def test_run_agent_invalid_agent(self, mock_route, mock_llm_chat):
        """run_agent returns error for unknown agent."""
        mock_route.return_value = MagicMock(model="test-model")
        
        result = run_agent("unknown_agent", "diff")
        
        assert result.agent == "unknown_agent"
        assert len(result.findings) == 0
        assert "Unknown agent" in result.error

    @patch("app.agents.run_agent")
    def test_run_all_agents(self, mock_run_agent):
        """run_all_agents calls each agent sequentially."""
        finding = AgentFinding(
            agent="security",
            severity="High",
            category="injection",
            title="Test",
            description="Test",
        )
        mock_run_agent.return_value = AgentRun(
            agent="security",
            decision=MagicMock(),
            findings=[finding],
        )
        
        diff = "diff content"
        results = run_all_agents(diff, [])
        
        # Should have called run_agent for each agent ID
        assert mock_run_agent.call_count == len(AGENT_IDS)


class TestCorroboration:
    def test_corroborate_empty_scanner_hits(self):
        """corroborate returns findings unchanged if no scanner hits."""
        finding = AgentFinding(
            agent="security",
            severity="High",
            category="sql_injection",
            title="Test",
            description="Test",
            file="app/db.py",
            line=10,
        )
        
        result = corroborate([finding], [])
        
        assert result[0].corroborated is False
        assert result[0].confidence == 0.5

    def test_corroborate_matching_line(self):
        """corroborate boosts confidence when file and line match."""
        finding = AgentFinding(
            agent="security",
            severity="High",
            category="sql_injection",
            title="Test",
            description="Test",
            file="app/db.py",
            line=10,
        )
        scanner_hit = {
            "file": "app/db.py",
            "line": 10,
            "category": "sql_injection",
            "scanner": "regex_scanner",
        }
        
        result = corroborate([finding], [scanner_hit])
        
        assert result[0].corroborated is True
        assert result[0].confidence == 0.75  # 0.5 + 0.25
        assert "regex_scanner" in result[0].matched_scanners

    def test_corroborate_matching_category(self):
        """corroborate marks findings as corroborated if category mentioned."""
        finding = AgentFinding(
            agent="security",
            severity="High",
            category="injection",
            title="SQL Injection Detected",
            description="String interpolation in SQL query",
            file="app/db.py",
        )
        scanner_hit = {
            "file": "app/db.py",
            "category": "sql_injection",
            "scanner": "ast_scanner",
        }
        
        result = corroborate([finding], [scanner_hit])
        
        assert result[0].corroborated is True
        assert result[0].confidence > 0.5


class TestGenerateFixes:
    @patch("app.agents.llm_chat")
    @patch("app.agents.route")
    def test_generate_fixes_for_high_severity(self, mock_route, mock_llm_chat):
        """generate_fixes creates fixes for high-severity findings."""
        mock_route.return_value = MagicMock(model="test-model")
        mock_llm_chat.return_value = MagicMock(
            content='{"fixes": [{"file": "app/db.py", "line": 10, "fix_code": "query = db.execute(...)", "tests": []}]}',
            model="test-model",
            cost_usd=0.02,
        )
        
        findings = [
            {
                "severity": "High",
                "file": "app/db.py",
                "line": 10,
                "category": "sql_injection",
                "title": "Test",
                "description": "Test",
                "corroborated": False,
                "fix_code": None,
            }
        ]
        
        result = generate_fixes(findings)
        
        assert len(result) == 1
        assert result[0]["fix_code"] == "query = db.execute(...)"

    @patch("app.agents.llm_chat")
    @patch("app.agents.route")
    def test_generate_fixes_llm_failure(self, mock_route, mock_llm_chat):
        """generate_fixes returns empty list on LLM failure."""
        from app.llm import LLMError
        
        mock_route.return_value = MagicMock(model="test-model")
        mock_llm_chat.side_effect = LLMError("API unavailable")
        
        findings = [
            {
                "severity": "High",
                "file": "app/db.py",
                "corroborated": False,
                "fix_code": None,
            }
        ]
        
        result = generate_fixes(findings)
        
        assert result == []

    def test_generate_fixes_skips_already_fixed(self):
        """generate_fixes skips findings that already have fix_code."""
        findings = [
            {
                "severity": "High",
                "file": "app/db.py",
                "fix_code": "already provided",
            }
        ]
        
        result = generate_fixes(findings)
        
        assert result == []

    def test_generate_fixes_ignores_low_severity(self):
        """generate_fixes ignores low-severity non-corroborated findings."""
        findings = [
            {
                "severity": "Low",
                "file": "app/db.py",
                "corroborated": False,
                "fix_code": None,
            }
        ]
        
        result = generate_fixes(findings)
        
        assert result == []
