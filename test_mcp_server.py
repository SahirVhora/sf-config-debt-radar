"""MCP tool wrapper smoke tests."""

import json

import pytest

pytest.importorskip("mcp.server.fastmcp")

from mcp_server import assessment_questions_tool, rate_findings_tool


def test_assessment_questions_can_filter_by_category():
    payload = json.loads(assessment_questions_tool("governance"))
    assert payload["count"] > 0
    assert {question["category"] for question in payload["questions"]} == {"governance"}


def test_rate_findings_scores_valid_json():
    findings = [
        {"severity": "HIGH", "area": "Business Rules", "title": "Rule collision"},
        {"severity": "MEDIUM", "area": "Custom Fields", "title": "Field concentration"},
    ]
    payload = json.loads(rate_findings_tool(json.dumps(findings)))
    assert payload["finding_count"] == 2
    assert payload["score"]["risk_level"] in {"Low", "Medium", "High", "Critical"}


def test_rate_findings_reports_invalid_json():
    payload = json.loads(rate_findings_tool("{not-json"))
    assert "Invalid JSON" in payload["error"]
