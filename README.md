# SF Config Debt Radar

SAP SuccessFactors EC configuration debt scanner. Analyse metadata, detect config debt, score risk - from your terminal, browser, or any MCP-compatible AI agent.

![mcp](https://img.shields.io/badge/MCP-Server-7B61FF)
![python](https://img.shields.io/badge/python-3.10%2B-blue)

## What It Does

- Pulls OData `$metadata` with Basic Auth or OAuth2
- Parses EC, Position, Foundation Object, Picklist, and custom MDF entities
- Scores hidden configuration debt from schema complexity, field counts, and null rates
- Runs safe Tier 1 `$count` checks for null/blank signals
- Produces JSON reports with debt score + 90-day remediation roadmap
- Exposes everything as **MCP tools** for AI agent integration

## Privacy

Zero employee data is stored or leaves the tenant. Schema metadata, entity counts, and non-identifiable signals only.

---

## Quick Start

```bash
pip install -r requirements.txt

# Offline metadata demo (no tenant needed)
python -m sf_config_debt_radar metadata-demo --output output

# Live tenant scan
cp config.example.yaml config.yaml
# edit config.yaml with your connection
python -m sf_config_debt_radar scan --config config.yaml --output output
```

### Browser Dashboard

```bash
python -m http.server 8088
# open http://localhost:8088/index.html
```

---

## MCP Server (AI Agent Integration)

The MCP server lets any MCP-compatible AI agent (Hermes Agent, Claude Code, Cursor, VS Code) discover and call the scanner's tools automatically.

### One-liner run

```bash
python mcp_server.py
```

### Connect from any MCP client

**Hermes Agent** - add to `~/.hermes/config.yaml`:
```yaml
mcp_servers:
  sf-config-debt-scanner:
    command: /path/to/sf-config-debt-radar/run_mcp_server.sh
    enabled: true
```

**Claude Code** - add to `~/.claude/claude_desktop_config.json` (or project `.claude/settings.json`):
```json
{
  "mcpServers": {
    "sf-config-debt-scanner": {
      "command": "python",
      "args": ["/path/to/sf-config-debt-radar/mcp_server.py"]
    }
  }
}
```

**Cursor** - add under Settings > MCP Servers:
```
name: sf-config-debt-scanner
type: command
command: python /path/to/sf-config-debt-radar/mcp_server.py
```

### Available MCP Tools

| Tool | What it does |
|------|-------------|
| `sf_scan_metadata_xml` | Analyse raw $metadata XML for config debt (offline) |
| `sf_test_connection` | Test OData v2 connectivity + get entity counts |
| `sf_scan_tenant` | Full live tenant scan - pulls metadata + $count checks |
| `sf_assessment_questions` | Generate guided config debt workshop questions |
| `sf_rate_findings` | Score a set of findings with debt score + roadmap |
| `sf_known_ec_entities` | List entity patterns the scanner recognises |
| `sf_about` | Server metadata and version |

### Example prompts

> "Scan this SF metadata XML for custom field sprawl"
> "Test connection to api55.sapsf.eu"
> "Run a full config debt scan against my tenant"
> "Give me assessment questions for governance"

---

## Browser App

The `index.html` dashboard is best for:
- Client workshops
- Self-assessment sessions
- Demo metadata import / paste
- Team walkthroughs

Note: Live tenant calls from the browser usually need a CORS proxy. The Python scanner is the reliable live-tenant path.

---

## Config Examples

**Basic Auth**:
```yaml
sf:
  auth_method: basic
  base_url: "https://api55.sapsf.eu/odata/v2"
  username: "admin@COMPANYID"
  password: "..."
```

**OAuth2**:
```yaml
sf:
  auth_method: oauth2
  base_url: "https://api55.sapsf.eu/odata/v2"
  client_id: "..."
  client_secret: "..."
  company_id: "COMPANYID"
  token_url: "https://api55.sapsf.eu/oauth/token"
```

---

## Project Structure

```
sf-config-debt-radar/
  mcp_server.py              # MCP server (7 tools, stdio or SSE)
  run_mcp_server.sh           # Hermes launcher script
  index.html                  # Browser dashboard
  config.example.yaml         # Config template
  pyproject.toml              # Package definition
  requirements.txt            # Dependencies
  sf_config_debt_radar/       # Core library
    cli.py                    # CLI entry point
    auth.py                   # SF OData authentication
    metadata.py               # XML metadata parser
    scanner.py                # Scan engine
    scoring.py                # Debt scoring
    report.py                 # Report generation
    __main__.py               # python -m support
  tests/
    test_core.py
  data/                       # Client evidence templates
```

---

## Part of the SF Compass Suite

One of 10 free, open tools for SAP SuccessFactors consultants. Explore the full suite at [SF Compass](https://sahirvhora.github.io/sf-compass/).

Related tools:

- [Position Integrity Checker](https://github.com/SahirVhora/sf-position-integrity-checker) - Validate position data integrity
- [Config Compare](https://github.com/SahirVhora/sf-config-compare) - Compare metadata and picklists across tenants
- [ObjectSync](https://github.com/SahirVhora/SAPSF_ObjectSync) - Sync OM foundation objects PRD to Dev
