"""Report model and HTML rendering."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from typing import Any

from .scoring import score_debt


def build_report_model(
    metadata_summary: dict[str, Any], findings: list[dict[str, Any]]
) -> dict[str, Any]:
    score = score_debt(findings)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": metadata_summary,
        "score": score,
        "findings": sorted(
            findings,
            key=lambda f: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(
                str(f.get("severity", "LOW")).upper(), 4
            ),
        ),
        "roadmap": build_roadmap(findings),
    }


def build_roadmap(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    high = [
        f
        for f in findings
        if str(f.get("severity", "")).upper() in {"CRITICAL", "HIGH"}
    ]
    medium = [f for f in findings if str(f.get("severity", "")).upper() == "MEDIUM"]
    return [
        {
            "phase": "Phase 1",
            "title": "Quick wins and control gaps",
            "timeline": "1-2 weeks",
            "actions": [action_text(f) for f in high[:6]]
            or ["Confirm scope, owners, and access for the EC configuration baseline."],
        },
        {
            "phase": "Phase 2",
            "title": "Risk reduction and simplification",
            "timeline": "3-6 weeks",
            "actions": [action_text(f) for f in (high[6:10] + medium[:4])]
            or ["Rationalise duplicate configuration and document critical decisions."],
        },
        {
            "phase": "Phase 3",
            "title": "Governance and debt trend",
            "timeline": "7-12 weeks",
            "actions": [
                "Introduce quarterly EC configuration debt review.",
                "Create naming and ownership standards for rules, fields, event reasons, and MDF objects.",
                "Track debt score before and after each release or transformation wave.",
            ],
        },
    ]


def action_text(finding: dict[str, Any]) -> str:
    title = finding.get("title", "Review finding")
    area = finding.get("area", "Configuration")
    return f"{area}: {title}"


def render_html_report(report: dict[str, Any]) -> str:
    score = report["score"]
    findings_rows = "\n".join(
        f"<tr><td>{html.escape(str(f.get('severity','')))}</td><td>{html.escape(str(f.get('area','')))}</td><td>{html.escape(str(f.get('title','')))}</td><td>{html.escape(str(f.get('detail','')))}</td></tr>"
        for f in report["findings"]
    )
    area_rows = "\n".join(
        f"<tr><td>{html.escape(area)}</td><td>{value}</td></tr>"
        for area, value in score["area_scores"].items()
    )
    roadmap = "\n".join(
        f"<section class='phase'><h3>{html.escape(p['phase'])}: {html.escape(p['title'])}</h3><p>{html.escape(p['timeline'])}</p><ul>"
        + "".join(f"<li>{html.escape(a)}</li>" for a in p["actions"])
        + "</ul></section>"
        for p in report["roadmap"]
    )
    data_json = html.escape(json.dumps(report, indent=2))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SF Config Debt Radar Report</title>
<style>
body{{margin:0;background:#08090a;color:#f6f3ea;font-family:Inter,Segoe UI,Arial,sans-serif}}
main{{max-width:1180px;margin:auto;padding:32px}}
.card{{background:#111317;border:1px solid #2a2f38;border-radius:18px;padding:22px;margin:16px 0;box-shadow:0 20px 60px rgba(0,0,0,.25)}}
h1{{font-size:38px;margin:0 0 8px}} h2{{color:#c8a84e}} .score{{font-size:64px;color:#c8a84e;font-weight:800}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}
table{{width:100%;border-collapse:collapse}} th,td{{padding:10px;border-bottom:1px solid #2a2f38;text-align:left;vertical-align:top}} th{{color:#c8a84e}}
.badge{{display:inline-block;padding:6px 10px;border-radius:999px;background:#26200f;color:#f4d06f;border:1px solid #5d4b16}}
.phase{{border-left:3px solid #c8a84e;padding-left:16px;margin:18px 0}}
pre{{white-space:pre-wrap;background:#050506;border:1px solid #222;padding:16px;border-radius:12px;color:#cfd6e4}}
@media print{{body{{background:white;color:#111}}.card{{box-shadow:none;border-color:#ccc}}h2,.score,th{{color:#7a5a00}}}}
</style>
</head>
<body><main>
<h1>SF Config Debt Radar</h1>
<p class="badge">EC-only configuration debt assessment</p>
<div class="card"><h2>Executive Summary</h2><div class="score">{score['overall_score']}</div><p>Risk level: <strong>{html.escape(score['risk_level'])}</strong></p><p>This report measures hidden configuration debt across EC metadata, custom fields, foundation objects, picklists, event reasons, and governance signals. It stores findings, counts, and schema only.</p></div>
<div class="grid"><div class="card"><h2>Entities</h2><p>{report['summary'].get('entity_count',0)}</p></div><div class="card"><h2>EC Entities</h2><p>{report['summary'].get('ec_entity_count',0)}</p></div><div class="card"><h2>Custom MDF</h2><p>{report['summary'].get('custom_mdf_count',0)}</p></div><div class="card"><h2>Findings</h2><p>{len(report['findings'])}</p></div></div>
<div class="card"><h2>Area Scores</h2><table><thead><tr><th>Area</th><th>Score</th></tr></thead><tbody>{area_rows}</tbody></table></div>
<div class="card"><h2>Findings</h2><table><thead><tr><th>Severity</th><th>Area</th><th>Finding</th><th>Detail</th></tr></thead><tbody>{findings_rows}</tbody></table></div>
<div class="card"><h2>90-Day Roadmap</h2>{roadmap}</div>
<div class="card"><h2>JSON</h2><pre>{data_json}</pre></div>
</main></body></html>"""
