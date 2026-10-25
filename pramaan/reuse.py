"""F8 reuse across applications. check_reuse(app, docs, index_db) -> list[Finding].
A small SQLite index of every application processed: photo perceptual hash (ahash from photo_check),
document sha256 and certificate numbers (certificate_no, ref_no, stamp_no). An application is compared only
with applications FIRST indexed before it, so re-running any application gives the same answer and never
matches itself. Rule ids X-REUSE-PHOTO / X-REUSE-CERT, lane human_review. OWNER: Aryan."""
from __future__ import annotations

import os
import sqlite3

from PIL import Image

from .photo_check import ahash
from .schemas import Application, DocumentRecord, Evidence, Finding

CERT_FIELDS = ("certificate_no", "ref_no", "stamp_no")
PHOTO_MAX_BITS = 6                 # same tolerance as photo_check duplicate test


def _db(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE IF NOT EXISTS apps (seq INTEGER PRIMARY KEY AUTOINCREMENT, app_id TEXT UNIQUE)")
    c.execute("CREATE TABLE IF NOT EXISTS items (app_id TEXT, kind TEXT, key TEXT, ref TEXT)")
    return c


def _items(app: Application, docs: list[DocumentRecord]) -> list[tuple[str, str, str]]:
    """(kind, key, ref) for this application. ref = doc_id or photo file name."""
    out = []
    for d in docs:
        out.append(("sha256", d.sha256, d.doc_id))
        for f in CERT_FIELDS:
            v = d.fields.get(f)
            if v and v.value and v.value.strip():
                out.append(("cert", f"{d.doc_type}:{f}:{v.value.strip().upper()}", d.doc_id))
    for p in app.photos:
        try:
            out.append(("photo", format(ahash(Image.open(p)), "x"), os.path.basename(p)))
        except Exception:
            continue
    return out


def _finding(app, rid, title, reason, ref, doc_id, other_app, other_ref):
    return Finding(finding_id=f"{app.app_id}-{rid}-{ref}", app_id=app.app_id, doc_id=doc_id, source="crosscheck", rule_id=rid,
                   title=title, reason=reason[:400], severity="high", confidence=0.9, lane="human_review",
                   evidence=[Evidence(doc_id=doc_id or f"photo:{ref}", page=1, text=f"also in application {other_app} ({other_ref})"[:200])])


def check_reuse(app: Application, docs: list[DocumentRecord], index_db: str = "output/reuse.db") -> list[Finding]:
    items = _items(app, docs)
    c = _db(index_db)
    try:
        c.execute("INSERT OR IGNORE INTO apps (app_id) VALUES (?)", (app.app_id,))
        seq = c.execute("SELECT seq FROM apps WHERE app_id=?", (app.app_id,)).fetchone()[0]
        earlier = "SELECT i.app_id, i.key, i.ref FROM items i JOIN apps a ON a.app_id=i.app_id WHERE a.seq<? AND i.kind=?"
        out, seen = [], set()
        for kind, key, ref in items:
            if kind == "photo":
                me = int(key, 16)
                hits = [(a, r) for a, k, r in c.execute(earlier, (seq, "photo")) if bin(me ^ int(k, 16)).count("1") <= PHOTO_MAX_BITS]
            else:
                hits = [(a, r) for a, k, r in c.execute(earlier, (seq, kind)) if k == key]
            rule = "X-REUSE-PHOTO" if kind == "photo" else "X-REUSE-CERT"
            if not hits or (rule, ref) in seen:
                continue
            seen.add((rule, ref)); other_app, other_ref = hits[0]
            if kind == "photo":
                out.append(_finding(app, "X-REUSE-PHOTO", "Campus photo also used in another application",
                                    f"{ref} looks the same as {other_ref} submitted with application {other_app}.",
                                    ref, None, other_app, other_ref))
            else:
                what = "the same file" if kind == "sha256" else f"the same {key.split(':')[1].replace('_', ' ')} {key.split(':', 2)[2]}"
                out.append(_finding(app, "X-REUSE-CERT", "Document also used in another application",
                                    f"{ref} carries {what} as {other_ref} in application {other_app}.",
                                    ref, ref, other_app, other_ref))
        c.execute("DELETE FROM items WHERE app_id=?", (app.app_id,))
        c.executemany("INSERT INTO items VALUES (?,?,?,?)", [(app.app_id, k, key, r) for k, key, r in items])
        c.commit()
        return out
    finally:
        c.close()
