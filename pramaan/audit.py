"""Append-only, hash-chained audit log in SQLite. Each row stores the previous row's hash, so editing or deleting any
row breaks verify_chain(). OWNER: Nishchal (reference version)."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime

from .privacy import mask_detail

GENESIS = "0" * 64


class AuditLog:
    def __init__(self, db_path: str):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db = sqlite3.connect(db_path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, actor TEXT,
                           role TEXT, action TEXT, app_id TEXT, detail TEXT, prev_hash TEXT, hash TEXT)""")
        self.db.commit()

    @staticmethod
    def _h(prev, ts, actor, role, action, app_id, detail_json):
        body = json.dumps([prev, ts, actor, role, action, app_id, detail_json], ensure_ascii=False)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    def head(self) -> str:
        r = self.db.execute("SELECT hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
        return r[0] if r else GENESIS

    def append(self, actor: str, role: str, action: str, app_id: str | None, detail: dict) -> str:
        prev = self.head()
        ts = datetime.now().isoformat(timespec="seconds")
        dj = json.dumps(mask_detail(detail), sort_keys=True, ensure_ascii=False, default=str)   # personal values masked
        h = self._h(prev, ts, actor, role, action, app_id, dj)
        self.db.execute("INSERT INTO audit (ts, actor, role, action, app_id, detail, prev_hash, hash) VALUES (?,?,?,?,?,?,?,?)",
                        (ts, actor, role, action, app_id, dj, prev, h))
        self.db.commit()
        return h

    def verify_chain(self) -> tuple[bool, int | None]:
        prev = GENESIS
        for (i, ts, actor, role, action, app_id, dj, p, h) in self.db.execute(
                "SELECT id, ts, actor, role, action, app_id, detail, prev_hash, hash FROM audit ORDER BY id"):
            if p != prev or self._h(prev, ts, actor, role, action, app_id, dj) != h:
                return False, i
            prev = h
        return True, None

    def rows(self, app_id: str | None = None) -> list[dict]:
        q = "SELECT id, ts, actor, role, action, app_id, detail, prev_hash, hash FROM audit"
        cur = self.db.execute(q + " WHERE app_id = ? ORDER BY id", (app_id,)) if app_id else self.db.execute(q + " ORDER BY id")
        cols = ["id", "ts", "actor", "role", "action", "app_id", "detail", "prev_hash", "hash"]
        return [dict(zip(cols, r)) for r in cur]
