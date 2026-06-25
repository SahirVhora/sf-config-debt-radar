#!/usr/bin/env python3
"""MCP server for SAP SuccessFactors Configuration Debt Radar.

Exposes SF config debt scanning as MCP tools that any MCP-compatible
client (Hermes Agent, Claude Code, Cursor, etc.) can discover and call.

Transport: stdio (for local AI agent integration).
Also supports SSE for remote/HTTP access.

Usage:
    python3 mcp_server.py                          # stdio (default)
    python3 mcp_server.py --transport sse --port 8090  # HTTP/SSE
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Ensure the project root is on sys.path so we can import sf_config_debt_radar
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Imports below must follow the sys.path manipulation above so the package
# can be located when this module is run directly (python mcp_server.py).
from sf_config_debt_radar.auth import SFClient  # noqa: E402
from sf_config_debt_radar.metadata import classify_ec_entities, CORE_EC_ENTITIES  # noqa: E402
from sf_config_debt_radar.scanner import (  # noqa: E402
    scan_metadata_xml,
    run_count_checks,
)
from sf_config_debt_radar.report import build_report_model  # noqa: E402

# ── MCP Server Setup ──────────────────────────────────────────────────

mcp = FastMCP(
    "SF Config Debt Scanner",
    instructions="SAP SuccessFactors EC Configuration Debt Scanner - analyse metadata, detect config debt, score risk. Tools: sf_scan_metadata_xml (offline XML scan), sf_scan_tenant (live tenant scan), sf_test_connection (test credentials), sf_assessment_questions (guided questionnaire), sf_rate_findings (score finding sets).",
)

# ── Tool: Scan Metadata XML ───────────────────────────────────────────


@mcp.tool(
    name="sf_scan_metadata_xml",
    description="Analyse SAP SuccessFactors $metadata XML text for configuration debt indicators. No tenant connection needed - paste raw XML metadata and get findings, classification, and debt score.",
)
def scan_metadata_xml_tool(
    xml_text: str,
    high_field_limit: int = 100,
    custom_field_limit: int = 20,
    custom_mdf_warning: int = 15,
) -> str:
    """Analyse SF metadata XML and return structured findings.

    Args:
        xml_text: The raw $metadata XML content from an SAP SuccessFactors tenant.
        high_field_limit: Entities with fields above this count get flagged (default 100).
        custom_field_limit: Entities with custom fields above this count get flagged (default 20).
        custom_mdf_warning: Tenant-wide warning if custom MDF objects exceed this (default 15).

    Returns:
        JSON string with scan results: summary, entity classification, findings, debt score, roadmap.
    """
    config = {
        "thresholds": {
            "high_field_limit": high_field_limit,
            "custom_field_limit": custom_field_limit,
            "custom_mdf_warning": custom_mdf_warning,
        }
    }
    result = scan_metadata_xml(xml_text, config)
    report = build_report_model(result["summary"], result["findings"])
    return json.dumps({
        "summary": report["summary"],
        "score": report["score"],
        "findings": report["findings"],
        "roadmap": report["roadmap"],
        "classified": {
            name: list(entities.keys())
            for name, entities in classify_ec_entities(result["entities"]).items()
        },
    }, indent=2, default=str)


# ── Tool: Test Connection ─────────────────────────────────────────────


@mcp.tool(
    name="sf_test_connection",
    description="Test an SAP SuccessFactors OData v2 connection. Returns connectivity status, latency signal, and record counts for core entities. Use this before running a full scan.",
)
def test_connection_tool(
    base_url: str,
    auth_method: str = "basic",
    username: str = "",
    password: str = "",
    client_id: str = "",
    client_secret: str = "",
    company_id: str = "",
    token_url: str = "",
) -> str:
    """Test connectivity to an SF OData v2 endpoint.

    Args:
        base_url: SAP SF OData v2 base URL (e.g. https://api55.sapsf.eu/odata/v2).
        auth_method: 'basic' or 'oauth2'.
        username: Basic Auth username (required for basic auth).
        password: Basic Auth password (required for basic auth).
        client_id: OAuth2 client ID (required for oauth2).
        client_secret: OAuth2 client secret (required for oauth2).
        company_id: OAuth2 company ID (required for oauth2).
        token_url: OAuth2 token URL (auto-derived if blank).

    Returns:
        JSON string with connection status, message, and entity counts.
    """
    try:
        client = SFClient(
            base_url=base_url,
            auth_method=auth_method,
            username=username,
            password=password,
            client_id=client_id,
            client_secret=client_secret,
            company_id=company_id,
            token_url=token_url or "",
        )
        ok, message = client.test_connection()
        entity_counts = {}
        for entity in ("EmpJob", "EmpEmployment", "User", "Position", "PerPerson"):
            count = client.count(entity)
            if count is not None:
                entity_counts[entity] = count
        return json.dumps({
            "success": ok,
            "message": message,
            "entity_counts": entity_counts,
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


# ── Tool: Full Tenant Scan ────────────────────────────────────────────


@mcp.tool(
    name="sf_scan_tenant",
    description="Run a full EC configuration debt scan against a live SAP SuccessFactors tenant. Connects via OData v2, pulls $metadata, runs count checks (Tier 1), and returns findings with debt score and 90-day roadmap. Zero employee data stored - schema and counts only.",
)
def scan_tenant_tool(
    base_url: str,
    auth_method: str = "basic",
    username: str = "",
    password: str = "",
    client_id: str = "",
    client_secret: str = "",
    company_id: str = "",
    token_url: str = "",
    high_field_limit: int = 100,
    custom_field_limit: int = 20,
    custom_mdf_warning: int = 15,
    blank_rate_high: int = 95,
    max_null_rate_fields: int = 25,
    tier1_enabled: bool = True,
) -> str:
    """Full EC config debt scan against a live SF tenant.

    Args:
        base_url: SAP SF OData v2 base URL.
        auth_method: 'basic' or 'oauth2'.
        username: Basic Auth username.
        password: Basic Auth password.
        client_id: OAuth2 client ID.
        client_secret: OAuth2 client secret.
        company_id: OAuth2 company ID.
        token_url: OAuth2 token URL (auto-derived if blank).
        high_field_limit: High field count threshold (default 100).
        custom_field_limit: Custom field concentration threshold (default 20).
        custom_mdf_warning: Custom MDF sprawl warning count (default 15).
        blank_rate_high: Blank field rate % for HIGH finding (default 95).
        max_null_rate_fields: Max nullable fields to check for blank rates (default 25).
        tier1_enabled: Run $count checks on the tenant (default true).

    Returns:
        JSON string with full scan results including score, findings, roadmap, and metadata summary.
    """
    try:
        client = SFClient(
            base_url=base_url,
            auth_method=auth_method,
            username=username,
            password=password,
            client_id=client_id,
            client_secret=client_secret,
            company_id=company_id,
            token_url=token_url or "",
        )
        ok, test_message = client.test_connection()
        if not ok:
            return json.dumps({"success": False, "error": f"Connection failed: {test_message}"}, indent=2)

        config = {
            "thresholds": {
                "high_field_limit": high_field_limit,
                "custom_field_limit": custom_field_limit,
                "custom_mdf_warning": custom_mdf_warning,
                "blank_rate_high": blank_rate_high,
            },
            "scan": {
                "tier1_enabled": tier1_enabled,
                "max_null_rate_fields": max_null_rate_fields,
            },
        }

        # Pull and scan metadata
        from sf_config_debt_radar.scanner import pull_and_scan_metadata
        result = pull_and_scan_metadata(client, config)

        # Tier 1 count checks
        findings = list(result["findings"])
        if tier1_enabled:
            findings.extend(run_count_checks(client, result, config))

        report = build_report_model(result["summary"], findings)
        return json.dumps({
            "success": True,
            "connection": test_message,
            "summary": report["summary"],
            "score": report["score"],
            "findings": report["findings"],
            "roadmap": report["roadmap"],
        }, indent=2, default=str)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2, default=str)


# ── Tool: Assessment Questionnaire ────────────────────────────────────


@mcp.tool(
    name="sf_assessment_questions",
    description="Generate the guided configuration debt assessment questions for SAP SuccessFactors EC. Covers governance, custom fields, MDF, picklists, event reasons, foundation objects, and business rules. Use as a starting point for client workshops or self-assessment.",
)
def assessment_questions_tool(
    category: str = "all",
) -> str:
    """Get guided assessment questions for SF EC configuration debt.

    Args:
        category: Filter by area - 'governance', 'custom_fields', 'mdf', 'picklists',
                  'event_reasons', 'foundation', 'rules', or 'all' (default).

    Returns:
        JSON string with assessment questions, optionally filtered by category.
    """
    questions = _assessment_db()
    if category and category != "all":
        questions = [q for q in questions if q["category"] == category]
    return json.dumps({"count": len(questions), "questions": questions}, indent=2)


def _assessment_db() -> list[dict[str, str]]:
    """Return the full assessment question set."""
    return [
        {"id": "GOV-01", "category": "governance", "question": "Do you have a documented configuration governance process for EC?", "severity": "HIGH", "rationale": "Without governance, config debt accumulates silently."},
        {"id": "GOV-02", "category": "governance", "question": "Is there a named owner per EC module (job, comp, org, personal)?", "severity": "MEDIUM", "rationale": "Orphaned config has no accountability."},
        {"id": "GOV-03", "category": "governance", "question": "Do you review custom fields quarterly for usage and retirement?", "severity": "HIGH", "rationale": "Unused custom fields add complexity and testing cost."},
        {"id": "GOV-04", "category": "governance", "question": "Is there a change advisory board or approval process for EC config changes?", "severity": "MEDIUM", "rationale": "Uncontrolled changes introduce risk."},
        {"id": "GOV-05", "category": "governance", "question": "Do you maintain a design decision register for EC?", "severity": "LOW", "rationale": "Tribal knowledge about why config exists is a risk."},
        {"id": "GOV-06", "category": "governance", "question": "Are your EC integrations documented with field mappings and payload samples?", "severity": "HIGH", "rationale": "Undocumented integrations are fragile and hard to test."},
        {"id": "GOV-07", "category": "governance", "question": "Do you have a testing strategy for EC release updates?", "severity": "HIGH", "rationale": "Release updates can break config silently."},
        {"id": "GOV-08", "category": "governance", "question": "Is there a process to review and clean up deprecated event reasons?", "severity": "MEDIUM", "rationale": "Unused event reasons create reporting noise and confusion."},
        {"id": "CF-01", "category": "custom_fields", "question": "How many custom fields exist across EC objects?", "severity": "MEDIUM", "rationale": "High custom field counts increase complexity."},
        {"id": "CF-02", "category": "custom_fields", "question": "Do you know which custom fields are unused/always blank?", "severity": "HIGH", "rationale": "Blank custom fields waste UI space and integration payloads."},
        {"id": "CF-03", "category": "custom_fields", "question": "Do you have a naming convention for custom fields?", "severity": "LOW", "rationale": "Inconsistent naming makes maintenance harder."},
        {"id": "CF-04", "category": "custom_fields", "question": "Are custom fields documented with business purpose and owner?", "severity": "MEDIUM", "rationale": "Unknown custom fields become untouchable over time."},
        {"id": "CF-05", "category": "custom_fields", "question": "Do you track which custom fields are used in reports, integrations, or business rules?", "severity": "HIGH", "rationale": "Field dependency awareness prevents breaking changes."},
        {"id": "MDF-01", "category": "mdf", "question": "How many custom MDF objects exist in your tenant?", "severity": "MEDIUM", "rationale": "Excessive custom MDF objects indicate process gaps."},
        {"id": "MDF-02", "category": "mdf", "question": "Do your custom MDF objects use effective dating for historical tracking?", "severity": "HIGH", "rationale": "Non-effective-dated objects cannot track history properly."},
        {"id": "MDF-03", "category": "mdf", "question": "Are custom MDF objects documented with purpose and owner?", "severity": "MEDIUM", "rationale": "Undocumented custom MDF objects accumulate over time."},
        {"id": "MDF-04", "category": "mdf", "question": "Do you use standard objects before adding custom MDF?", "severity": "MEDIUM", "rationale": "Custom objects bypass standard functionality and upgrade paths."},
        {"id": "PL-01", "category": "picklists", "question": "Do you review picklists for duplicate or unused values?", "severity": "MEDIUM", "rationale": "Picklist drift causes integration and reporting issues."},
        {"id": "PL-02", "category": "picklists", "question": "Are global picklists used consistently across countries?", "severity": "HIGH", "rationale": "Inconsistent picklist use across countries creates integration complexity."},
        {"id": "PL-03", "category": "picklists", "question": "Do you maintain translations for picklist values?", "severity": "LOW", "rationale": "Missing translations affect employee experience."},
        {"id": "PL-04", "category": "picklists", "question": "Do you have a process to deprecate and clean old picklist values?", "severity": "MEDIUM", "rationale": "Stale picklist values add noise to integrations and reporting."},
        {"id": "ER-01", "category": "event_reasons", "question": "Are your EC event reasons standardised across countries?", "severity": "HIGH", "rationale": "Event reason variance causes reporting and process inconsistency."},
        {"id": "ER-02", "category": "event_reasons", "question": "Do you have event reasons that are never used?", "severity": "MEDIUM", "rationale": "Unused event reasons create noise and confusion."},
        {"id": "ER-03", "category": "event_reasons", "question": "Do you have a naming convention for event reasons?", "severity": "LOW", "rationale": "Inconsistent naming makes governance harder."},
        {"id": "ER-04", "category": "event_reasons", "question": "Are event reasons mapped correctly to trigger events?", "severity": "HIGH", "rationale": "Wrong event mapping breaks workflows, reporting, and payroll."},
        {"id": "FO-01", "category": "foundation", "question": "Do you regularly audit foundation objects for inactive or duplicate values?", "severity": "HIGH", "rationale": "Inactive or duplicate foundation objects cause processing errors downstream."},
        {"id": "FO-02", "category": "foundation", "question": "Is your position management hierarchy accurate and maintained?", "severity": "HIGH", "rationale": "Position hierarchy errors affect workflow routing and reporting."},
        {"id": "FO-03", "category": "foundation", "question": "Do you have a governance process for creating new foundation objects?", "severity": "MEDIUM", "rationale": "Uncontrolled foundation object creation leads to sprawl."},
        {"id": "FO-04", "category": "foundation", "question": "Are foundation objects cross-referenced correctly (department to division, position to job code)?", "severity": "HIGH", "rationale": "Cross-entity misalignments break reporting and integrations."},
        {"id": "BR-01", "category": "rules", "question": "Do you have duplicate or overlapping business rules?", "severity": "CRITICAL", "rationale": "Overlapping rules cause unpredictable field behaviour."},
        {"id": "BR-02", "category": "rules", "question": "Are your business rules documented with purpose and expected behaviour?", "severity": "HIGH", "rationale": "Undocumented rules are hard to maintain and test."},
        {"id": "BR-03", "category": "rules", "question": "Is there a process to test business rules before activating?", "severity": "HIGH", "rationale": "Untested rules cause production issues."},
        {"id": "BR-04", "category": "rules", "question": "Do you have business rules that fire on the same event and touch the same field?", "severity": "CRITICAL", "rationale": "Contending rules cause unpredictable behaviour depending on execution order."},
        {"id": "BR-05", "category": "rules", "question": "Are your business rules using country/entity guards appropriately?", "severity": "HIGH", "rationale": "Rules without proper scope affect unintended populations."},
    ]


# ── Tool: Rate Findings ───────────────────────────────────────────────


@mcp.tool(
    name="sf_rate_findings",
    description="Score a set of configuration debt findings and return an overall debt score with area breakdown and 90-day roadmap. Use after running sf_scan_metadata_xml to get structured scoring on custom findings.",
)
def rate_findings_tool(findings_json: str) -> str:
    """Take an array of findings and return a debt score + roadmap.

    Args:
        findings_json: JSON string of an array of finding objects.
                       Each finding should have 'severity' (CRITICAL/HIGH/MEDIUM/LOW)
                       and 'area' (e.g. 'Business Rules', 'Custom Fields', 'MDF Objects').

    Returns:
        JSON string with overall score, risk level, area scores, and 90-day roadmap.
    """
    try:
        findings = json.loads(findings_json)
        if not isinstance(findings, list):
            findings = [findings]
        report = build_report_model({"entity_count": 0}, findings)
        return json.dumps({
            "score": report["score"],
            "roadmap": report["roadmap"],
            "finding_count": len(findings),
        }, indent=2)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON: {e}"}, indent=2)


# ── Tool: List Known EC Entities ──────────────────────────────────────


@mcp.tool(
    name="sf_known_ec_entities",
    description="List the known SAP SuccessFactors EC entity names used for classification during metadata scanning. Useful for understanding what the scanner looks for.",
)
def known_ec_entities_tool() -> str:
    """Return the set of known EC, foundation, and custom entity patterns used in scanning."""
    return json.dumps({
        "core_ec_entities": sorted(CORE_EC_ENTITIES),
        "foundation_entity_prefixes": ["FO"],
        "core_entity_prefixes": ["Emp", "Per"],
        "custom_patterns": ["cust_", "custom_"],
    }, indent=2)


# ── Tool: About ───────────────────────────────────────────────────────


@mcp.tool(
    name="sf_about",
    description="Get information about this MCP server, its version, available tools, and the SF Config Debt Radar project.",
)
def about_tool() -> str:
    """Return metadata about this MCP server."""
    return json.dumps({
        "name": "SF Config Debt Scanner (MCP)",
        "version": "1.0.0",
        "description": "MCP server wrapping the SAP SuccessFactors EC Configuration Debt Radar",
        "project": "sf-config-debt-radar",
        "project_path": str(_project_root),
        "tools": [
            "sf_scan_metadata_xml",
            "sf_test_connection",
            "sf_scan_tenant",
            "sf_assessment_questions",
            "sf_rate_findings",
            "sf_known_ec_entities",
            "sf_about",
        ],
        "auth_methods": ["basic", "oauth2"],
        "data_policy": "Zero employee data stored. Schema, counts, and non-identifiable metadata only.",
    }, indent=2)


# ── Entry Point ───────────────────────────────────────────────────────

def main() -> None:
    """Run the MCP server on stdio (default) or SSE."""
    import argparse

    parser = argparse.ArgumentParser(description="SF Config Debt Radar - MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio for AI agent integration)",
    )
    parser.add_argument("--port", type=int, default=8090, help="Port for SSE transport (default: 8090)")
    parser.add_argument("--host", default="127.0.0.1", help="Host for SSE transport (default: 127.0.0.1)")
    args = parser.parse_args()

    if args.transport == "sse":
        print(f"Starting SF Config Debt Scanner MCP server on http://{args.host}:{args.port}/mcp", file=sys.stderr)
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        # Stdio is the default for local AI agent integration
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
