"""WK23-19 Appeal window tracker. APH 1.11 a.: the institute may respond "within 7 days from the date of issue of Letter of
Deficiency". An LoD counts as issued when the officer finalises it (audit row "letter of deficiency finalised").
status(rows, app_id, today) -> None (no LoD) or {issued_on, deadline, days_left, state}; state = "open" / "window closed" /
"closed (read-only)" once the window has passed AND an officer decision is recorded. OWNER: Aryan."""
from __future__ import annotations

from datetime import date, timedelta

APPEAL_DAYS = 7
CLAUSE = "APH 1.11 a. - within 7 days from the date of issue of Letter of Deficiency"


def status(rows: list[dict], app_id: str, today: date) -> dict | None:
    mine = [r for r in rows if r["app_id"] == app_id]
    issued = [r for r in mine if r["action"] == "letter of deficiency finalised"]
    if not issued:
        return None
    on = date.fromisoformat(issued[-1]["ts"][:10])
    deadline = on + timedelta(days=APPEAL_DAYS)
    decided = any(r["action"].startswith("decision") and r["ts"] > issued[-1]["ts"] for r in mine)
    left = (deadline - today).days
    state = "open" if left >= 0 else "closed (read-only)" if decided else "window closed"
    return {"issued_on": on.isoformat(), "deadline": deadline.isoformat(), "days_left": max(left, 0), "state": state, "clause": CLAUSE}
