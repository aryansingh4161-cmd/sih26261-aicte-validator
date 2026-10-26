"""WK23-11 Officer feedback on findings: "correct" / "false alarm" + optional note + officer id + time, in table `feedback`
of the SAME SQLite file as the audit log (separate table; the hash chain is untouched, and each feedback also adds one audit
row so the trail is complete). export_csv() feeds the next model / rule version; false_alarm_rate() feeds Analytics. OWNER: Aryan."""
from __future__ import annotations

import csv
import sqlite3
from contextlib import closing

from .util import now_iso

VERDICTS = ("correct", "false alarm")
COLS = ["ts", "app_id", "finding_id", "rule_id", "verdict", "officer", "note"]


def _db(path: str):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE IF NOT EXISTS feedback (ts TEXT, app_id TEXT, finding_id TEXT, rule_id TEXT, verdict TEXT, officer TEXT, note TEXT)")
    return closing(c)


def record(db: str, finding, verdict: str, user: dict, note: str = "", log=None) -> None:
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}")
    with _db(db) as c:
        c.execute("INSERT INTO feedback VALUES (?,?,?,?,?,?,?)",
                  (now_iso(), finding.app_id, finding.finding_id, finding.rule_id, verdict, user["id"], note))
        c.commit()
    if log is not None:
        log.append(user["id"], user["role"], f"feedback: {verdict}", finding.app_id, {"finding_id": finding.finding_id, "note": note})


def rows(db: str) -> list[dict]:
    with _db(db) as c:
        return [dict(zip(COLS, r)) for r in c.execute(f"SELECT {', '.join(COLS)} FROM feedback ORDER BY ts")]


def export_csv(db: str, path: str) -> str:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(rows(db))
    return path


def false_alarm_rate(db: str) -> dict:
    """rule_id -> {"false_alarms", "n", "rate"}; the latest verdict per finding counts."""
    last = {}
    for r in rows(db):
        last[r["finding_id"]] = r
    out: dict = {}
    for r in last.values():
        s = out.setdefault(r["rule_id"], {"false_alarms": 0, "n": 0})
        s["n"] += 1; s["false_alarms"] += r["verdict"] == "false alarm"
    for s in out.values():
        s["rate"] = round(s["false_alarms"] / s["n"], 3)
    return out
