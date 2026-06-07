#!/usr/bin/env python3
"""Test the SF Config Debt Radar MCP server."""
import json
import subprocess
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parent / "mcp_server.py"
VENV_PYTHON = Path(__file__).resolve().parent / "venv" / "bin" / "python"

def send(proc, msg: dict) -> dict:
    line = json.dumps(msg)
    proc.stdin.write(line + "\n")
    proc.stdin.flush()
    resp = proc.stdout.readline()
    return json.loads(resp)

proc = subprocess.Popen(
    [str(VENV_PYTHON), str(SERVER)],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

# Initialize
init = send(proc, {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}},
})
print(f"INIT: {init.get('result', {}).get('serverInfo', 'OK')}")

# Test sf_about
about = send(proc, {
    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
    "params": {"name": "sf_about", "arguments": {}},
})
result = json.loads(about["result"]["result"]["result"])
print(f"\nABOUT:")
for k, v in result.items():
    print(f"  {k}: {v}")

# Test sf_known_ec_entities
known = send(proc, {
    "jsonrpc": "2.0", "id": 3, "method": "tools/call",
    "params": {"name": "sf_known_ec_entities", "arguments": {}},
})
result = json.loads(known["result"]["result"]["result"])
print(f"\nKNOWN EC ENTITIES:")
print(f"  Core EC count: {len(result['core_ec_entities'])}")
print(f"  First 5: {result['core_ec_entities'][:5]}")

# Test sf_assessment_questions with filter
questions = send(proc, {
    "jsonrpc": "2.0", "id": 4, "method": "tools/call",
    "params": {"name": "sf_assessment_questions", "arguments": {"category": "governance"}},
})
result = json.loads(questions["result"]["result"]["result"])
print(f"\nASSESSMENT (governance only):")
print(f"  Questions: {result['count']}")
for q in result["questions"][:3]:
    print(f"  - [{q['id']}] {q['question']}")

# Test sf_rate_findings
sample = [
    {"severity": "HIGH", "area": "Business Rules", "title": "Rule collision risk", "detail": "Two rules touch the same field"},
    {"severity": "MEDIUM", "area": "Custom Fields", "title": "High custom field count", "detail": "EmpJob has 45 custom fields"},
]
rated = send(proc, {
    "jsonrpc": "2.0", "id": 5, "method": "tools/call",
    "params": {"name": "sf_rate_findings", "arguments": {"findings_json": json.dumps(sample)}},
})
result = json.loads(rated["result"]["result"]["result"])
print(f"\nRATE FINDINGS:")
print(f"  Score: {result['score']['overall_score']} ({result['score']['risk_level']})")
print(f"  Phases: {len(result['roadmap'])}")

proc.stdin.close()
proc.wait()
print(f"\nExit code: {proc.returncode}")
