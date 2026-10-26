"""Lanes and alerts. The system never rejects. OWNER: Aryan (reference version)."""
from __future__ import annotations

import os
from datetime import date, timedelta

import yaml

from .schemas import Alert, Application, Finding, VerificationResult

DEFAULT_SLA = {"high": 2, "medium": 5, "low": 7, "info": 10}
ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3}


def _sla(path="config/settings.yaml") -> dict:
    try:
        with open(path) as f:
            return {**DEFAULT_SLA, **((yaml.safe_load(f) or {}).get("sla_days") or {})}
    except Exception:
        return dict(DEFAULT_SLA)


def assign_lane(findings: list[Finding]) -> str:
    if any(f.lane == "human_review" for f in findings):
        return "human_review"
    if any(f.lane == "return_for_rectification" for f in findings):
        return "return_for_rectification"
    return "clear"


def _kind(f: Finding):
    r = f.rule_id
    if r.startswith(("R-MISS", "R-SIG")):
        return "missing_document"
    if r.startswith(("R-EXP", "R-PROV")):
        return "expired_document"
    if r.startswith(("X-", "R-REC", "R-FLD")):
        return "mismatch"
    if r.startswith("F-"):
        return "suspected_anomaly"
    if r.startswith("V-"):
        return "mismatch"
    return None


def make_alerts(app: Application, findings: list[Finding], verifications: list[VerificationResult], today: date,
                settings_path: str = "config/settings.yaml") -> list[Alert]:
    sla = _sla(settings_path)
    groups: dict = {}
    for f in findings:
        k = _kind(f)
        if f.lane == "info" or k is None:
            continue
        groups.setdefault(k, {"sev": [], "ids": [], "titles": []})
        g = groups[k]; g["sev"].append(f.severity); g["ids"].append(f.finding_id); g["titles"].append(f.title)
    for v in verifications:
        k = {"verification_pending": "pending_verification", "source_unavailable": "source_unavailable"}.get(v.status)
        if k:
            g = groups.setdefault(k, {"sev": [], "ids": [], "titles": []})
            g["sev"].append("low"); g["titles"].append(f"{v.method} for {v.doc_id}: {v.status}")
    out = []
    for n, (k, g) in enumerate(sorted(groups.items()), start=1):
        days = min(int(sla.get(s, 10)) for s in g["sev"])
        msg = "; ".join(dict.fromkeys(g["titles"]))
        out.append(Alert(alert_id=f"{app.app_id}-AL{n}", app_id=app.app_id, kind=k, message=msg[:160],
                         created_at=today.isoformat(), due_by=(today + timedelta(days=days)).isoformat(), finding_ids=g["ids"]))
    return out
