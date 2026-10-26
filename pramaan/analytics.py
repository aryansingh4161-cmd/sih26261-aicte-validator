"""WK23-16 Leadership analytics (read only): top deficiencies, deficiencies by region, lane split, share auto-cleared,
median processing time (SYNTHETIC timestamps: demo submission dates vs pipeline run time), false-alarm rate per rule (officer
feedback), SLA breaches (alerts past due with no officer decision). OWNER: Aryan."""
from __future__ import annotations

import os
import sqlite3
import statistics
from collections import Counter
from contextlib import closing
from datetime import date

from .schemas import ApplicationResult


def top_deficiencies(results: list[ApplicationResult], n: int = 10) -> list[tuple[str, int]]:
    return Counter(f.title for r in results for f in r.findings if f.lane == "return_for_rectification").most_common(n)


def by_region(results: list[ApplicationResult], manifests: dict) -> dict:
    out: dict = {}
    for r in results:
        reg = manifests.get(r.app_id, {}).get("declared", {}).get("region", "unknown")
        s = out.setdefault(reg, {"applications": 0, "deficiencies": 0, "review items": 0})
        s["applications"] += 1
        s["deficiencies"] += sum(f.lane == "return_for_rectification" for f in r.findings)
        s["review items"] += sum(f.lane == "human_review" for f in r.findings)
    return dict(sorted(out.items()))


def lane_split(results: list[ApplicationResult]) -> dict:
    return dict(Counter(r.lane for r in results))


def auto_cleared_share(results: list[ApplicationResult], audit_rows: list[dict]) -> tuple[int, int]:
    done = {r["app_id"] for r in audit_rows if r["action"].startswith("decision: approve for next step (clear-queue batch)")}
    return len(done & {r.app_id for r in results}), len(results)


def median_processing_days(results: list[ApplicationResult], manifests: dict) -> float | None:
    days = [(date.fromisoformat(r.run_at[:10]) - date.fromisoformat(manifests[r.app_id]["submitted_on"])).days
            for r in results if r.app_id in manifests and manifests[r.app_id].get("submitted_on")]
    return statistics.median(days) if days else None


def sla_breaches(results: list[ApplicationResult], audit_rows: list[dict], today: date) -> list[dict]:
    decided = {r["app_id"] for r in audit_rows if r["action"].startswith("decision")}
    return [{"app_id": r.app_id, "alert": a.kind, "due_by": a.due_by} for r in results for a in r.alerts
            if a.due_by < today.isoformat() and r.app_id not in decided]


def false_alarms_readonly(db: str) -> dict:
    """Same numbers as feedback.false_alarm_rate, from a read-only connection (the Analytics page writes nothing)."""
    if not os.path.exists(db):
        return {}
    with closing(sqlite3.connect(f"file:{os.path.abspath(db)}?mode=ro", uri=True)) as c:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='feedback'").fetchone():
            return {}
        last = {fid: (rule, v) for _, fid, rule, v in c.execute("SELECT ts, finding_id, rule_id, verdict FROM feedback ORDER BY ts")}
    out: dict = {}
    for rule, v in last.values():
        s = out.setdefault(rule, {"false_alarms": 0, "n": 0}); s["n"] += 1; s["false_alarms"] += v == "false alarm"
    for s in out.values():
        s["rate"] = round(s["false_alarms"] / s["n"], 3)
    return out
