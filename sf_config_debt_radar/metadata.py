"""Metadata parsing and EC entity classification."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

CORE_EC_ENTITIES = {
    "EmpJob",
    "EmpEmployment",
    "EmpCompensation",
    "EmpPayCompRecurring",
    "EmpPayCompNonRecurring",
    "PerPerson",
    "PerPersonal",
    "PerEmail",
    "PerPhone",
    "Position",
    "FOCompany",
    "FODepartment",
    "FOBusinessUnit",
    "FODivision",
    "FOLocation",
    "FOCostCenter",
    "FOJobCode",
    "EventReason",
    "PickListValue",
    "PicklistOption",
    "User",
}

FOUNDATION_ENTITIES = {
    "FOCompany",
    "FODepartment",
    "FOBusinessUnit",
    "FODivision",
    "FOLocation",
    "FOCostCenter",
    "FOJobCode",
    "FOEventReason",
    "FOPayGroup",
    "FOLegalEntity",
    "FOGeozone",
}

CUSTOM_PATTERNS = ("custom", "cust_", "customString", "custom-string", "cust_")


def parse_metadata_xml(xml_text: str) -> dict[str, dict[str, Any]]:
    root = ET.fromstring(xml_text)
    entities: dict[str, dict[str, Any]] = {}
    for element in root.iter():
        if not (element.tag.endswith("}EntityType") or element.tag == "EntityType"):
            continue
        name = element.get("Name")
        if not name:
            continue
        fields = []
        nav_props = []
        required_fields = []
        custom_field_count = 0
        nullable_count = 0
        has_effective_start = False
        has_effective_end = False
        has_status = False
        has_last_modified = False
        for child in element:
            if child.tag.endswith("}Property") or child.tag == "Property":
                field_name = child.get("Name", "")
                field_type = child.get("Type", "")
                nullable = child.get("Nullable", "true").lower() == "true"
                max_length = child.get("MaxLength")
                if any(field_name.startswith(p) for p in CUSTOM_PATTERNS) or "custom" in field_name.lower():
                    custom_field_count += 1
                if not nullable:
                    required_fields.append(field_name)
                else:
                    nullable_count += 1
                if field_name in {"effectiveStartDate", "cust_effectiveStartDate", "startDate"}:
                    has_effective_start = True
                if field_name in {"effectiveEndDate", "cust_effectiveEndDate", "endDate"}:
                    has_effective_end = True
                if field_name in {"status", "effectiveStatus", "active"}:
                    has_status = True
                if "lastmodified" in field_name.lower():
                    has_last_modified = True
                fields.append({
                    "name": field_name,
                    "type": field_type,
                    "nullable": nullable,
                    "max_length": max_length,
                    "is_custom": any(field_name.startswith(p) for p in CUSTOM_PATTERNS) or "custom" in field_name.lower(),
                })
            elif child.tag.endswith("}NavigationProperty") or child.tag == "NavigationProperty":
                nav_props.append({
                    "name": child.get("Name", ""),
                    "to": child.get("To", "") or child.get("ToRole", ""),
                    "relationship": child.get("Relationship", ""),
                })
        entities[name] = {
            "name": name,
            "fields": fields,
            "required_fields": required_fields,
            "field_count": len(fields),
            "custom_field_count": custom_field_count,
            "nullable_field_count": nullable_count,
            "nav_props": nav_props,
            "has_effective_start_date": has_effective_start,
            "has_effective_end_date": has_effective_end,
            "has_status_field": has_status,
            "has_last_modified": has_last_modified,
        }
    return entities


def classify_ec_entities(entities: dict[str, dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    core_ec = {}
    custom_mdf = {}
    foundation = {}
    picklists = {}
    for name, info in entities.items():
        if name in CORE_EC_ENTITIES or name.startswith(("Emp", "Per")):
            core_ec[name] = info
        if name.startswith(("cust_", "custom_")):
            custom_mdf[name] = info
        if name in FOUNDATION_ENTITIES:
            foundation[name] = info
        if "picklist" in name.lower() or name in {"PickListValue", "PicklistOption"}:
            picklists[name] = info
    return {
        "core_ec": core_ec,
        "custom_mdf": custom_mdf,
        "foundation": foundation,
        "picklists": picklists,
    }


def metadata_summary(entities: dict[str, dict[str, Any]]) -> dict[str, int]:
    classified = classify_ec_entities(entities)
    return {
        "entity_count": len(entities),
        "ec_entity_count": len(classified["core_ec"]),
        "custom_mdf_count": len(classified["custom_mdf"]),
        "foundation_count": len(classified["foundation"]),
        "picklist_entity_count": len(classified["picklists"]),
        "custom_field_count": sum(e["custom_field_count"] for e in entities.values()),
        "high_field_entity_count": sum(1 for e in entities.values() if e["field_count"] >= 100),
    }
