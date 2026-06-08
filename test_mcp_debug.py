"""Focused MCP tool wrapper tests."""

import json

import pytest

pytest.importorskip("mcp.server.fastmcp")

from mcp_server import about_tool, known_ec_entities_tool


def test_mcp_about_tool_returns_server_metadata():
    payload = json.loads(about_tool())
    assert payload["project"] == "sf-config-debt-radar"
    assert "sf_scan_metadata_xml" in payload["tools"]


def test_mcp_known_entities_tool_returns_core_entities():
    payload = json.loads(known_ec_entities_tool())
    assert "EmpJob" in payload["core_ec_entities"]
    assert payload["custom_patterns"] == ["cust_", "custom_"]
