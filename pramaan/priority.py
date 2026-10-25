"""F10 inspection priority. score(result, record, settings) -> (0..1, reasons).
A transparent weighted sum; weights live in config/settings.yaml under priority_weights
(designed weights, ASSUMPTION, not trained). It only orders the officer's queue; it decides nothing.
OWNER: Aryan."""
from __future__ import annotations

from datetime import date

from .schemas import ApplicationResult
from .util import norm_name

DEFAULT_WEIGHTS = {"high": 0.25, "medium": 0.1, "low": 0.03, "suspected_anomaly": 0.2,
                   "old_building": 0.1, "old_building_years": 30, "noc_intake_above_approved": 0.15}


def _noc_above_approved(result: ApplicationResult, record: dict) -> list[str]:
    """Courses whose intake on the university NOC is above the intake AICTE approved last year (mock record)."""
    def group(rows, key):                  # a course can appear twice (e.g. two shifts): pair intakes largest-first
        g: dict = {}
        for r in rows:
            try:
                g.setdefault(norm_name(r.get("course")), []).append(int(r.get(key) or 0))
            except ValueError:
                continue
        return {c: sorted(v, reverse=True) for c, v in g.items()}
    approved = group(record.get("approved_programs", []), "intake_prev")
    out = []
    for d in result.documents:
        if d.doc_type != "noc_format2":
            continue
        for course, nocs in group(d.tables.get("programs", []), "intake_curr").items():
            for n, prev in zip(nocs, approved.get(course, [])):
                if n > prev:
                    out.append(f"{course} {n} > {prev}")
    return out


def score(result: ApplicationResult, record: dict | None, settings: dict, today: date | None = None) -> tuple[float, list[str]]:
    w = {**DEFAULT_WEIGHTS, **(settings.get("priority_weights") or {})}
    today = today or date.fromisoformat(result.run_at[:10])
    total, reasons = 0.0, []
    for sev in ("high", "medium", "low"):
        n = sum(f.severity == sev for f in result.findings)
        if n:
            total += n * w[sev]
            reasons.append(f"{n} {sev}-severity finding{'s' if n > 1 else ''} (+{n * w[sev]:.2f}).")
    if any(a.kind == "suspected_anomaly" for a in result.alerts):
        total += w["suspected_anomaly"]
        reasons.append(f"A possible alteration or anomaly was flagged (+{w['suspected_anomaly']:.2f}).")
    if record:
        try:
            built = date.fromisoformat(str(record.get("building_completion_date")))
            age = (today - built).days / 365.25
            if age > w["old_building_years"]:
                total += w["old_building"]
                reasons.append(f"Building is about {age:.0f} years old per AICTE records (+{w['old_building']:.2f}).")
        except ValueError:
            pass
        above = _noc_above_approved(result, record)
        if above:
            total += w["noc_intake_above_approved"]
            reasons.append(f"Intake on the university NOC is above last year's approval: {'; '.join(above)[:120]} "
                           f"(+{w['noc_intake_above_approved']:.2f}).")
    if total > 1.0:
        reasons.append("Score capped at 1.00.")
    return round(min(total, 1.0), 3), reasons
