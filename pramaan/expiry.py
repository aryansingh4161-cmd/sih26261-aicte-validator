"""WK23-10 Expiry calendar (named expiry.py, not calendar.py, so the standard library module is not shadowed).
expiries(results) -> every certificate's expiry: valid_until if printed, else issue_date + validity_years (structural).
reminders(rows, today, days) -> MOCK outbox records 60/30/7 days before (settings reminder_days, ASSUMPTION), once per threshold.
overdue(rows, today); to_ics(rows) -> an iCalendar text (all-day events), no extra package. OWNER: Aryan."""
from __future__ import annotations

from datetime import date, timedelta

from .outbox import send
from .schemas import ApplicationResult
from .util import add_years, parse_date


def expiries(results: list[ApplicationResult]) -> list[dict]:
    out = []
    for r in results:
        for d in r.documents:
            f = d.fields
            exp, how = None, ""
            if f.get("valid_until") and parse_date(f["valid_until"].value):
                exp, how = parse_date(f["valid_until"].value), "valid until (printed)"
            elif f.get("issue_date") and f.get("validity_years") and parse_date(f["issue_date"].value):
                n = int("".join(ch for ch in f["validity_years"].value if ch.isdigit()) or 0)
                if n:
                    exp, how = add_years(parse_date(f["issue_date"].value), n), f"issue date + {n} years"
            if exp:
                out.append({"app_id": r.app_id, "doc_id": d.doc_id, "doc_type": d.doc_type, "expires": exp.isoformat(), "how": how})
    return sorted(out, key=lambda x: x["expires"])


def days_left(row: dict, today: date) -> int:
    return (date.fromisoformat(row["expires"]) - today).days


def overdue(rows: list[dict], today: date) -> list[dict]:
    return [r for r in rows if days_left(r, today) < 0]


def reminders(rows: list[dict], today: date, days=(60, 30, 7), outbox: str | None = None) -> list[str]:
    """One reminder per (document, threshold), on the first run on or after the threshold day."""
    out = []
    for r in rows:
        left = days_left(r, today)
        due = [d for d in sorted(days) if 0 <= left <= d]
        if due:
            out.append(send("expiry_reminder", f"institute of {r['app_id']}", {**r, "days": left},
                            key=f"reminder-{r['doc_id']}-{due[0]}d", outbox=outbox))
    return out


def to_ics(rows: list[dict]) -> str:
    ev = []
    for r in rows:
        d = date.fromisoformat(r["expires"])
        ev += ["BEGIN:VEVENT", f"UID:{r['doc_id']}-expiry@pramaan.local", f"DTSTAMP:{d:%Y%m%d}T000000Z",
               f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}",
               f"SUMMARY:{r['doc_type']} expires ({r['app_id']})", f"DESCRIPTION:{r['how']}", "END:VEVENT"]
    return "\r\n".join(["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Pramaan//expiry calendar//EN"] + ev + ["END:VCALENDAR"]) + "\r\n"
