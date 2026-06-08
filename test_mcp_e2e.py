"""End-to-end MCP wrapper test using the sample metadata file."""

import json
from pathlib import Path

import pytest

pytest.importorskip("mcp.server.fastmcp")

from mcp_server import scan_metadata_xml_tool


def test_scan_metadata_xml_tool_returns_report_sections():
    sample_xml = Path(__file__).resolve().parent / "samples" / "ec_metadata_sample.xml"
    payload = json.loads(scan_metadata_xml_tool(sample_xml.read_text(encoding="utf-8")))

    assert payload["summary"]["entity_count"] >= 1
    assert "score" in payload
    assert "findings" in payload
    assert "classified" in payload
