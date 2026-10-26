"""WK25-23 Internal notes between officers (back-end; no UI here). Table `notes` in the audit DB file.
add_note(db, app_id, author, text, finding_id=None) -> {note_id, mentions, warnings}: @mentions are officer ids from
config/users.yaml (unknown ids: stored as plain text, a warning returned, no mention). Every note also writes an audit row
"internal note" holding only the note id, mentions and the SHA-256 of the text (never the text), so audit exports cannot leak it.
Notes are NEVER part of letters, the institute self-check or the institute copy of the case ZIP (export_case institute_copy=True).
list_notes(db, app_id); mentions_for(db, officer).                                        OWNER: Aryan."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import closing

import yaml

from .audit import AuditLog
from .i18n import t
from .util import now_iso


def _db(path: str):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE IF NOT EXISTS notes (note_id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, app_id TEXT, author TEXT, "
              "finding_id TEXT, text TEXT, mentions TEXT)")
    return closing(c)


def officer_ids(users_path: str = "config/users.yaml") -> set[str]:
    return {u["id"] for u in (yaml.safe_load(open(users_path)) or {}).get("users", []) if u.get("role") in ("scrutiny_officer", "admin")}


def add_note(db: str, app_id: str, author: dict, text: str, finding_id: str | None = None, users_path: str = "config/users.yaml") -> dict:
    known = officer_ids(users_path)
    asked = re.findall(r"@([\w.]+[\w])", text)
    mentions = sorted({m for m in asked if m in known})
    warnings = [t(f"@{m} is not an officer in config/users.yaml; no one was notified.") for m in sorted(set(asked) - known)]
    with _db(db) as c:
        cur = c.execute("INSERT INTO notes (ts, app_id, author, finding_id, text, mentions) VALUES (?,?,?,?,?,?)",
                        (now_iso(), app_id, author["id"], finding_id, text, json.dumps(mentions)))
        nid = cur.lastrowid; c.commit()
    with AuditLog(db) as log:
        log.append(author["id"], author["role"], "internal note", app_id,
                   {"note_id": nid, "finding_id": finding_id, "mentions": mentions, "sha256": hashlib.sha256(text.encode()).hexdigest()})
    return {"note_id": nid, "mentions": mentions, "warnings": warnings}


def list_notes(db: str, app_id: str) -> list[dict]:
    with _db(db) as c:
        cols = ["note_id", "ts", "app_id", "author", "finding_id", "text", "mentions"]
        rows = [dict(zip(cols, r)) for r in c.execute(f"SELECT {', '.join(cols)} FROM notes WHERE app_id=? ORDER BY note_id", (app_id,))]
    for r in rows:
        r["mentions"] = json.loads(r["mentions"])
    return rows


def mentions_for(db: str, officer: str) -> list[dict]:
    with _db(db) as c:
        cols = ["note_id", "ts", "app_id", "author", "finding_id", "text", "mentions"]
        rows = [dict(zip(cols, r)) for r in c.execute(f"SELECT {', '.join(cols)} FROM notes ORDER BY note_id")]
    return [r for r in rows if officer in json.loads(r["mentions"])]
