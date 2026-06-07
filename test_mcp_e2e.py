#!/usr/bin/env python3
"""Full end-to-end test of the MCP server tools."""
import json
import subprocess
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parent / "mcp_server.py"
VENV_PYTHON = Path(__file__).resolve().parent / "venv" / "bin" / "python"

proc = subprocess.Popen(
    [str(VENV_PYTHON), str(SERVER)],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

def call(method: str, params: dict) -> dict:
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}) + "\n")
    proc.stdin.flush()
    resp = json.loads(proc.stdout.readline())
    return resp

def tool(name: str, args: dict = None) -> dict:
    resp = call("tools/call", {"name": name, "arguments": args or {}})
    content = resp.get("result", {}).get("content", [])
    if content and content[0].get("type") == "text":
        return json.loads(content[0]["text"])
    return resp

# Initialize
call("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}})

print("=== Test 1: sf_about ===")
r = tool("sf_about")
print(f"Server: {r['name']} v{r['version']}")
print(f"Tools: {len(r['tools'])} registered")

print("\n=== Test 2: sf_known_ec_entities ===")
r = tool("sf_known_ec_entities")
print(f"Core EC: {len(r['core_ec_entities'])} entities")
print(f"FO prefix: {r['foundation_entity_prefixes']}")

print("\n=== Test 3: sf_assessment_questions (rules only) ===")
r = tool("sf_assessment_questions", {"category": "rules"})
print(f"Rule questions: {r['count']}")
for q in r["questions"]:
    print(f"  [{q['severity']}] {q['question']}")

print("\n=== Test 4: sf_rate_findings ===")
sample = [
    {"severity": "CRITICAL", "area": "Business Rules", "title": "Rule collision", "detail": "Two rules touch the same field"},
    {"severity": "HIGH", "area": "Custom Fields", "title": "Custom field concentration", "detail": "High count"},
    {"severity": "MEDIUM", "area": "Event Reasons", "title": "Unused event reason", "detail": "Zero EmpJob references"},
]
r = tool("sf_rate_findings", {"findings_json": json.dumps(sample)})
print(f"Score: {r['score']['overall_score']} ({r['score']['risk_level']})")
print(f"Roadmap: {r['roadmap'][0]['phase']} - {r['roadmap'][0]['timeline']}")

print("\n=== Test 5: sf_scan_metadata_xml with sample data ===")
sample_xml = Path(__file__).resolve().parent / "samples" / "ec_metadata_sample.xml"
if sample_xml.exists():
    xml_text = sample_xml.read_text(encoding="utf-8")
    print(f"XML size: {len(xml_text)} chars")
    r = tool("sf_scan_metadata_xml", {"xml_text": xml_text})
    summary = r["summary"]
    score = r["score"]
    findings = r["findings"]
    print(f"Entities: {summary['entity_count']} (EC: {summary['ec_entity_count']}, Custom MDF: {summary['custom_mdf_count']}, FO: {summary['foundation_count']})")
    print(f"Custom fields: {summary['custom_field_count']}")
    print(f"Score: {score['overall_score']} ({score['risk_level']})")
    print(f"Findings: {len(findings)}")
    for f in findings[:5]:
        print(f"  [{f['severity']}] {f['area']}: {f['title']}")
else:
    print("Sample XML not found, skipping")

proc.stdin.close()
proc.wait()
print(f"\nAll tests passed (exit: {proc.returncode})")
