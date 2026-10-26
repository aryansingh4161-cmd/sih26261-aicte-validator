"""WK23-8 Serial reuse across institutes: one certificate body re-issued (or copied) for several institutes.
serial_check(app, docs, index_db, settings) -> X-SERIAL findings (human_review) against EARLIER applications of a DIFFERENT
Permanent Id, same document type. Fingerprint = the document's text with the institute name and address masked (numbers kept),
compared with rapidfuzz (difflib if missing). Designed rule (settings `serial`, ASSUMPTION): text similarity >= text_min AND the
same issuer AND issue dates within `days` AND certificate numbers within `number_gap`. A shared template alone never fires.
Index rows live in the reuse database (table serial). OWNER: Aryan."""
from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from datetime import date

from .i18n import t
from .schemas import Application, DocumentRecord, Evidence, Finding
from .util import similarity

ISSUER = {"structural_cert": "issuing_authority", "fire_cert": "issuing_authority", "occupancy_cert": "issuing_authority"}


def _ratio(a: str, b: str) -> float:
    try:
        from rapidfuzz import fuzz
        return fuzz.ratio(a, b) / 100.0
    except ImportError:
        import difflib
        return difflib.SequenceMatcher(None, a, b).ratio()


def fingerprint(doc: DocumentRecord, app: Application) -> str:
    text = " ".join(b.text for b in doc.blocks)
    for v in [app.declared.get("institute_name"), app.declared.get("address"), (doc.fields.get("institute_name") or None) and doc.fields["institute_name"].value]:
        for part in [v] + (v.split(",") if v else []):
            if part and len(part.strip()) > 3:
                text = re.sub(re.escape(part.strip()), " <MASK> ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip().lower()


def _num(v: str | None) -> int | None:
    m = re.findall(r"\d+", v or "")
    return int(m[-1]) if m else None


def _val(doc, f):
    x = doc.fields.get(f)
    return (x.value or "") if x else ""


def serial_check(app: Application, docs: list[DocumentRecord], index_db: str, settings: dict) -> list[Finding]:
    cfg = settings.get("serial", {}) or {}
    out = []
    with closing(sqlite3.connect(index_db)) as c:
        c.execute("CREATE TABLE IF NOT EXISTS serial (app_id TEXT, pid TEXT, doc_type TEXT, doc_id TEXT, fp TEXT, issuer TEXT, "
                  "issued TEXT, number INTEGER, PRIMARY KEY (app_id, doc_type))")
        c.execute("CREATE TABLE IF NOT EXISTS apps (seq INTEGER PRIMARY KEY AUTOINCREMENT, app_id TEXT UNIQUE)")
        c.execute("INSERT OR IGNORE INTO apps (app_id) VALUES (?)", (app.app_id,))
        seq = c.execute("SELECT seq FROM apps WHERE app_id=?", (app.app_id,)).fetchone()[0]
        for d in docs:
            if d.doc_type not in cfg.get("doc_types", list(ISSUER)):
                continue
            fp, iss, issued, no = fingerprint(d, app), _val(d, ISSUER.get(d.doc_type, "")), _val(d, "issue_date"), _num(_val(d, "certificate_no"))
            rows = c.execute("SELECT s.app_id, s.doc_id, s.fp, s.issuer, s.issued, s.number FROM serial s JOIN apps a ON a.app_id=s.app_id "
                             "WHERE a.seq<? AND s.doc_type=? AND s.pid!=?", (seq, d.doc_type, app.permanent_id)).fetchall()
            for other, odoc, ofp, oiss, oissued, ono in rows:
                sim = _ratio(fp, ofp)
                try:
                    days = abs((date.fromisoformat(issued) - date.fromisoformat(oissued)).days)
                except ValueError:
                    days = None
                if (sim >= cfg.get("text_min", 0.95) and iss and similarity(iss, oiss) >= 0.85 and days is not None
                        and days <= cfg.get("days", 30) and no is not None and ono is not None and abs(no - ono) <= cfg.get("number_gap", 20)):
                    label = d.doc_type.replace("_", " ").replace("cert", "certificate")
                    out.append(Finding(finding_id=f"{app.app_id}-X-SERIAL-{d.doc_id}", app_id=app.app_id, doc_id=d.doc_id,
                                       source="crosscheck", rule_id="X-SERIAL", severity="high", confidence=round(sim, 3),
                                       lane="human_review", title=t("Same certificate text as another institute's"),
                                       reason=t(f"{label.capitalize()} text is {100 * sim:.0f}% identical to the one submitted by {other} "
                                                f"(another institute): same issuer, issued {days} day(s) apart, numbers {ono} and {no}.")[:400],
                                       evidence=[Evidence(doc_id=d.doc_id, page=1, text=f"also {odoc}"[:200])]))
                    break
            c.execute("INSERT OR REPLACE INTO serial VALUES (?,?,?,?,?,?,?,?)", (app.app_id, app.permanent_id, d.doc_type, d.doc_id, fp, iss, issued, no))
        c.commit()
    return out
