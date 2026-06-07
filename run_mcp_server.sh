#!/usr/bin/env bash
# Launcher for the SF Config Debt Radar MCP server.
# Use in Hermes config.yaml as:
#
# mcp_servers:
#   sf-config-debt-scanner:
#     command: "/home/sahirvhora/projects/sapsf/sf-config-debt-radar/run_mcp_server.sh"
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$DIR/venv/bin/python" "$DIR/mcp_server.py" "$@"
