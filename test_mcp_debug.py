#!/usr/bin/env python3
"""Debug test: print raw MCP responses."""
import json
import subprocess
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

def send(msg: dict) -> dict:
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())

# Initialize
resp = send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}})
print("INIT response keys:", list(resp.keys()))
print("INIT result keys:", list(resp.get("result", {}).keys()))

# Call sf_about
resp = send({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "sf_about", "arguments": {}}})
print("\nABOUT response keys:", list(resp.keys()))
print("ABOUT content type:", type(resp.get("result", {}).get("content", [])))
content = resp.get("result", {}).get("content", [])
if content:
    print("First content type:", content[0].get("type"))
    print("First content text (first 500):", content[0].get("text", "")[:500])

proc.stdin.close()
proc.wait()
