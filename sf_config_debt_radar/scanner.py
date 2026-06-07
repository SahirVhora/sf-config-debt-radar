"""EC-only configuration debt scanner."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from .auth import SFClient
from .metadata import classify_ec_entities, metadata_summary, parse_metadata_xml


def pull_and_scan_metadata(client: SFClient, config: dict[str, Any]) -> dict[str, Any]:
    xml_text = client.get_text("$metadata", accept="application/xml", timeout=120)
    return scan_metadata_xml(xml_text, config)


def scan_metadata_xml(xml_text: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or {}
    entities = parse_metadata_xml(xml_text)
    findings = metadata_findings(entities, config)
    return {
        "scan_type": "metadata",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "summary": metadata_summary(entities),
        "entities": entities,
        "classified": classify_ec_entities(entities),
        "findings": findings,
    }


def metadata_findings(entities: dict[str, dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    thresholds = config.get("thresholds", {})
    high_field_limit = int(thresholds.get("high_field_limit", 100))
    custom_field_limit = int(thresholds.get("custom_field_limit", 20))
    findings = []
    classified = classify_ec_entities(entities)

    for name, info in entities.items():
        if name in classified["core_ec"] or name in classified["custom_mdf"] or name in classified["foundation"]:
            if info["field_count"] >= high_field_limit:
                findings.append({
                    "severity": "MEDIUM",
                    "area": "Metadata",
                    "object": name,
                    "title": "High field count",
                    "detail": f"{name} has {info['field_count']} fields. Large object schemas are harder to govern and test.",
                    "recommendation": "Review field ownership, report usage, and integration dependency before adding more fields.",
                })
            if (
                info["custom_field_count"] >= custom_field_limit
                and not name.startswith("PerGlobalInfo")
            ):
                findings.append({
                    "severity": "HIGH",
                    "area": "Custom Fields",
                    "object": name,
                    "title": "Custom field concentration",
                    "detail": f"{name} has {info['custom_field_count']} custom-looking fields.",
                    "recommendation": "Confirm each custom field has owner, purpose, report usage, and integration status.",
                })
            if name in classified["custom_mdf"] and not info["has_effective_start_date"]:
                findings.append({
                    "severity": "MEDIUM",
                    "area": "MDF Objects",
                    "object": name,
                    "title": "Custom MDF object without effective dating",
                    "detail": f"{name} does not expose an effective start date field in metadata.",
                    "recommendation": "Confirm whether the object stores historical data. If yes, redesign or document limitation.",
                })
            if name in classified["foundation"] and not info["has_status_field"]:
                findings.append({
                    "severity": "LOW",
                    "area": "Foundation Objects",
                    "object": name,
                    "title": "Foundation object without obvious status field",
                    "detail": f"{name} metadata did not show status/effectiveStatus/active.",
                    "recommendation": "Confirm active/inactive governance and cleanup approach.",
                })

    if len(classified["custom_mdf"]) >= int(thresholds.get("custom_mdf_warning", 15)):
        findings.append({
            "severity": "HIGH",
            "area": "MDF Objects",
            "title": "Custom MDF object sprawl",
            "detail": f"Tenant exposes {len(classified['custom_mdf'])} custom MDF entities.",
            "recommendation": "Create an owner and purpose register for custom MDF objects.",
        })
    return findings


def run_count_checks(client: SFClient, metadata_result: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    findings = []
    entities = metadata_result["entities"]
    ec_entities = metadata_result["classified"]["core_ec"]
    max_fields = int(config.get("scan", {}).get("max_null_rate_fields", 25))

    for entity in ("EmpJob", "Position", "EmpEmployment"):
        if entity not in entities:
            continue
        total = client.count(entity)
        if total is None:
            findings.append({
                "severity": "LOW",
                "area": "Metadata",
                "object": entity,
                "title": "Count query not available",
                "detail": f"Could not run $count against {entity}. This may be RBP, API visibility, or object availability.",
                "recommendation": "Check API permission for the scanner user.",
            })
            continue
        if total == 0:
            findings.append({
                "severity": "MEDIUM",
                "area": "Metadata",
                "object": entity,
                "title": "No records returned",
                "detail": f"{entity} returned zero records in $count.",
                "recommendation": "Confirm whether this is expected for the test tenant.",
            })
        fields = [f for f in ec_entities.get(entity, {}).get("fields", []) if f.get("nullable")][:max_fields]
        for field in fields:
            name = field["name"]
            if name.startswith("_") or name.endswith("Nav"):
                continue
            null_count = client.count(entity, f"{name} eq null")
            if total and null_count is not None:
                null_rate = null_count / total * 100
                if null_rate >= float(config.get("thresholds", {}).get("blank_rate_high", 95)) and (field.get("is_custom") or "custom" in name.lower()):
                    findings.append({
                        "severity": "HIGH",
                        "area": "Custom Fields",
                        "object": entity,
                        "field": name,
                        "title": "Mostly blank custom field",
                        "detail": f"{entity}.{name} is blank for {null_rate:.1f}% of records based on $count checks.",
                        "recommendation": "Confirm whether the field is still required before using it in reports, integrations, or new design.",
                    })

    event_reason_entities = [e for e in ("EventReason", "FOEventReason") if e in entities]
    if event_reason_entities and "EmpJob" in entities:
        event_entity = event_reason_entities[0]
        sample = _read_top_external_codes(client, event_entity, 50)
        for code in sample[:25]:
            count = client.count("EmpJob", f"eventReason eq '{quote_single(code)}'")
            if count == 0:
                findings.append({
                    "severity": "MEDIUM",
                    "area": "Event Reasons",
                    "object": event_entity,
                    "title": "Unused event reason candidate",
                    "detail": f"Event reason {code} returned zero EmpJob references in count check.",
                    "recommendation": "Review whether the event reason should be retired, hidden, or documented as reserved.",
                })
    return findings


def _read_top_external_codes(client: SFClient, entity: str, top: int) -> list[str]:
    for field in ("externalCode", "eventReason", "code"):
        try:
            payload = client.get_json(f"{entity}?$select={field}&$top={top}")
            rows = payload.get("d", {}).get("results", [])
            values = [str(row.get(field)) for row in rows if row.get(field)]
            if values:
                return values
        except Exception:
            continue
    return []


def quote_single(value: str) -> str:
    return value.replace("'", "''")
