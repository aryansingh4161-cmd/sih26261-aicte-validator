"""Retention: delete generated output older than N days. DRY RUN by default; --apply deletes.
  python -m tools.retention                 # list what WOULD be deleted (retention_days from config/settings.yaml, default 30)
  python -m tools.retention --days 7 --apply
In scope (under --out, default output/): *.result.json, *.report.html, heatmaps/**, uploads/** (uploaded-document copies;
designed location, nothing writes there yet). NEVER deleted: audit.db (the hash chain is kept so past decisions stay
provable; rows hold masked personal values only), reuse.db and issuer_webhook.db (indexes; no per-row expiry yet = designed).
Every run, dry or not, writes one audit row. OWNER: Aryan."""
from __future__ import annotations

import argparse
import fnmatch
import os
import time

from pramaan.audit import AuditLog
from pramaan.pipeline import _settings

PATTERNS = ("*.result.json", "*.report.html", "heatmaps/*", "uploads/*")
KEEP = ("audit.db", "reuse.db", "issuer_webhook.db")


def candidates(out_dir: str, days: float, now: float | None = None) -> list[tuple[str, float, int]]:
    """(path, age_days, bytes) of in-scope files older than `days`. Never returns a KEEP file."""
    now, found = now or time.time(), []
    for root, _, files in os.walk(out_dir):
        for fn in files:
            p = os.path.join(root, fn); rel = os.path.relpath(p, out_dir).replace(os.sep, "/")
            if fn.split("-journal")[0] in KEEP or not any(fnmatch.fnmatch(rel, pat) for pat in PATTERNS):
                continue
            age = (now - os.path.getmtime(p)) / 86400
            if age > days:
                found.append((p, round(age, 1), os.path.getsize(p)))
    return sorted(found)


def run(out_dir: str = "output", days: float | None = None, apply: bool = False, audit_db: str | None = None,
        now: float | None = None) -> dict:
    days = float(days if days is not None else _settings().get("retention_days", 30))
    found = candidates(out_dir, days, now)
    deleted = 0
    if apply:
        for p, _, _ in found:
            try:
                os.remove(p); deleted += 1
            except OSError:
                pass
    summary = {"days": days, "apply": apply, "matched": len(found), "deleted": deleted, "bytes": sum(b for _, _, b in found),
               "sample": [os.path.relpath(p, out_dir) for p, _, _ in found[:20]], "kept_always": list(KEEP)}
    AuditLog(audit_db or os.path.join(out_dir, "audit.db")).append(
        "retention-tool", "system", "retention applied" if apply else "retention dry-run", None, summary)
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output"); ap.add_argument("--days", type=float, default=None)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    s = run(a.out, a.days, a.apply)
    verb = "deleted" if a.apply else "would delete (dry run; add --apply)"
    print(f"retention {s['days']:g} days (ASSUMPTION): {verb} {s['matched'] if not a.apply else s['deleted']} files, "
          f"{s['bytes'] / 1e6:.1f} MB; audit.db kept (hash chain). Audit row written.")
    for p in s["sample"]:
        print("  ", p)
