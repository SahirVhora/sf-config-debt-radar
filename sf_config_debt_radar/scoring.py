"""Configuration debt scoring."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

AREA_WEIGHTS = {
    "Business Rules": 18,
    "RBP": 15,
    "Workflows": 12,
    "Event Reasons": 10,
    "Foundation Objects": 10,
    "Custom Fields": 10,
    "Picklists": 8,
    "MDF Objects": 8,
    "Integrations": 6,
    "Reports": 3,
    "Metadata": 8,
}

SEVERITY_POINTS = {
    "CRITICAL": 10,
    "HIGH": 6,
    "MEDIUM": 3,
    "LOW": 1,
}


def score_debt(findings: list[dict[str, Any]]) -> dict[str, Any]:
    debt_by_area: dict[str, int] = defaultdict(int)
    counts_by_severity: dict[str, int] = defaultdict(int)
    for finding in findings:
        severity = str(finding.get("severity", "LOW")).upper()
        area = str(finding.get("area", "Metadata"))
        points = SEVERITY_POINTS.get(severity, 1)
        weighted = points * AREA_WEIGHTS.get(area, 5)
        debt_by_area[area] += weighted
        counts_by_severity[severity] += 1

    area_scores = {}
    for area, weight in AREA_WEIGHTS.items():
        area_debt = debt_by_area.get(area, 0)
        area_scores[area] = max(0, min(100, 100 - round(area_debt / max(weight, 1) * 8)))

    total_weight = sum(AREA_WEIGHTS.values())
    overall = round(sum(area_scores[a] * AREA_WEIGHTS[a] for a in AREA_WEIGHTS) / total_weight)
    if overall >= 85:
        risk = "Low"
    elif overall >= 70:
        risk = "Medium"
    elif overall >= 50:
        risk = "High"
    else:
        risk = "Critical"
    return {
        "overall_score": overall,
        "risk_level": risk,
        "area_scores": area_scores,
        "debt_points_by_area": dict(debt_by_area),
        "findings_by_severity": dict(counts_by_severity),
    }


def severity_for_score(score: int) -> str:
    if score < 35:
        return "CRITICAL"
    if score < 55:
        return "HIGH"
    if score < 75:
        return "MEDIUM"
    return "LOW"
