"""CLI for SF Config Debt Radar."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from .auth import SFClient
from .report import build_report_model, render_html_report
from .scanner import pull_and_scan_metadata, run_count_checks, scan_metadata_xml


def load_config(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def save_outputs(report: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "config_debt_report.json"
    html_path = out / "config_debt_report.html"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    html_path.write_text(render_html_report(report), encoding="utf-8")
    return json_path, html_path


def run_scan(config: dict[str, Any], metadata_file: str | None = None) -> dict[str, Any]:
    if metadata_file:
        xml_text = Path(metadata_file).read_text(encoding="utf-8")
        result = scan_metadata_xml(xml_text, config)
    else:
        client = SFClient.from_config(config)
        ok, message = client.test_connection()
        print(message)
        if not ok:
            raise RuntimeError(message)
        result = pull_and_scan_metadata(client, config)
        if config.get("scan", {}).get("tier1_enabled", True):
            result["findings"].extend(run_count_checks(client, result, config))
    return build_report_model(result["summary"], result["findings"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EC-only SuccessFactors configuration debt scanner")
    parser.add_argument("command", choices=["scan", "metadata-demo"], help="Command to run")
    parser.add_argument("--config", default="config.yaml", help="YAML config path")
    parser.add_argument("--metadata-file", help="Use local $metadata XML file instead of live tenant")
    parser.add_argument("--output", default="output", help="Output directory")
    args = parser.parse_args(argv)

    config = load_config(args.config) if Path(args.config).exists() else {}
    if args.command == "metadata-demo" and not args.metadata_file:
        args.metadata_file = "samples/ec_metadata_sample.xml"
    report = run_scan(config, args.metadata_file)
    json_path, html_path = save_outputs(report, args.output)
    print(f"JSON report: {json_path}")
    print(f"HTML report: {html_path}")
    print(f"Overall score: {report['score']['overall_score']} ({report['score']['risk_level']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
