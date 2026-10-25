"""Append-only, hash-chained audit log in SQLite. Each row stores the previous row's hash, so editing or deleting any
row breaks verify_chain(). OWNER: Nishchal (reference version)."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime

from .privacy import mask_detail

GENESIS = "0" * 64


class AuditLog:
    """Hash-chained audit log in SQLite. Every method opens its own connection and CLOSES it before returning, so no
    file handle stays open (Windows cannot delete an open database: WinError 32). close() and `with AuditLog(p) as log:`
    are supported and safe to call any number of times."""

    def __init__(self, db_path: str):
        self.path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT,
                         role TEXT, action TEXT, app_id TEXT, detail TEXT, prev_hash TEXT, hash TEXT)""")
            c.commit()

    def _conn(self):
        return closing(sqlite3.connect(self.path))

    def close(self) -> None:
        """Nothing is held between calls; kept so callers can close explicitly (and for `with`)."""

    def __enter__(self) -> "AuditLog":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @staticmethod
    def _h(prev, ts, actor, role, action, app_id, detail_json):
        body = json.dumps([prev, ts, actor, role, action, app_id, detail_json], ensure_ascii=False)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    @staticmethod
    def _head(c) -> str:
        r = c.execute("SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
        return r[0] if r else GENESIS

    def head(self) -> str:
        with self._conn() as c:
            return self._head(c)

    def append(self, actor: str, role: str, action: str, app_id: str | None, detail: dict) -> str:
        ts = datetime.now().isoformat(timespec="seconds")
        dj = json.dumps(mask_detail(detail), sort_keys=True, ensure_ascii=False, default=str)   # personal values masked
        with self._conn() as c:                                      # head read + insert on ONE connection
            prev = self._head(c)
            h = self._h(prev, ts, actor, role, action, app_id, dj)
            c.execute("INSERT INTO audit (ts, actor, role, action, app_id, detail, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?)",
                      (ts, actor, role, action, app_id, dj, prev, h))
            c.commit()
        return h

    def verify_chain(self) -> tuple[bool, int | None]:
        prev = GENESIS
        with self._conn() as c:
            for (i, ts, actor, role, action, app_id, dj, p, h) in c.execute(
                    "SELECT id, ts, actor, role, action, app_id, detail, prev_hash, hash FROM audit ORDER BY id"):
                if p != prev or self._h(prev, ts, actor, role, action, app_id, dj) != h:
                    return False, i
                prev = h
        return True, None

    def rows(self, app_id: str | None = None) -> list[dict]:
        q = "SELECT id, ts, actor, role, action, app_id, detail, prev_hash, hash FROM audit"
        cols = ["id", "ts", "actor", "role", "action", "app_id", "detail", "prev_hash", "hash"]
        with self._conn() as c:
            cur = c.execute(q + " WHERE app_id = ? ORDER BY id", (app_id,)) if app_id else c.execute(q + " ORDER BY id")
            return [dict(zip(cols, r)) for r in cur]
