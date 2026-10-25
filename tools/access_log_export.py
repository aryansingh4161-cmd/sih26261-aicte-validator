"""Export audit-log rows to CSV, filtered by application, actor and date (access-log review).
  python -m tools.access_log_export --out eval/access_log.csv [--app APP-07] [--actor officer.demo] [--since 2026-10-01] [--until 2026-10-31]
Reads audit.db READ-ONLY; personal values in details are already masked at write time. Prints the chain status.
The export itself is audited (one row "access log exported") unless --no-audit. OWNER: Nishchal / Aryan."""
from __future__ import annotations

import argparse
import csv
import os
import sqlite3

from pramaan.audit import GENESIS, AuditLog

COLS = ["id", "ts", "actor", "role", "action", "app_id", "detail", "prev_hash", "hash"]


def export(db: str, out: str, app: str | None = None, actor: str | None = None, since: str | None = None,
           until: str | None = None) -> tuple[int, bool, int | None]:
    con = sqlite3.connect(f"file:{os.path.abspath(db)}?mode=ro", uri=True)
    try:
        rows = [dict(zip(COLS, r)) for r in con.execute(f"SELECT {', '.join(COLS)} FROM audit ORDER BY id")]
    finally:
        con.close()
    ok, bad, prev = True, None, GENESIS                     # chain is checked over ALL rows, before filtering
    for r in rows:
        if r["prev_hash"] != prev or AuditLog._h(prev, r["ts"], r["actor"], r["role"], r["action"], r["app_id"], r["detail"]) != r["hash"]:
            ok, bad = False, r["id"]; break
        prev = r["hash"]
    keep = [r for r in rows if (not app or r["app_id"] == app) and (not actor or r["actor"] == actor)
            and (not since or r["ts"][:10] >= since) and (not until or r["ts"][:10] <= until)]
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(keep)
    return len(keep), ok, bad


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="output/audit.db"); ap.add_argument("--out", default="output/access_log.csv")
    ap.add_argument("--app"); ap.add_argument("--actor"); ap.add_argument("--since"); ap.add_argument("--until")
    ap.add_argument("--no-audit", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(a.db):
        raise SystemExit(f"no audit log at {a.db}")
    n, ok, bad = export(a.db, a.out, a.app, a.actor, a.since, a.until)
    if not a.no_audit:
        AuditLog(a.db).append("access-log-export", "system", "access log exported", a.app,
                              {"out": a.out, "rows": n, "filters": {"app": a.app, "actor": a.actor, "since": a.since, "until": a.until}})
    print(f"wrote {n} rows to {a.out}; audit chain {'intact' if ok else f'BROKEN at row {bad}'}")
