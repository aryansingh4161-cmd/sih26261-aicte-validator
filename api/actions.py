"""State-changing calls for the web API (WK26). Each is a thin wrapper over a pramaan/ function; every change is audited there.
The letter that goes to the institute is sealed WITHOUT the officers' internal annex (letters.to_html(text, notes=[]))."""
from __future__ import annotations

import hashlib
import html as H
import os

from pramaan.appeal import status as appeal_status
from pramaan.assign import due_date, record_assignment
from pramaan.audit import AuditLog
from pramaan.evc_pack import items as evc_items
from pramaan.export_case import export_case
from pramaan.feedback import record as record_feedback
from pramaan.issuer import load_records, verify_document
from pramaan.letters import save_final, to_html
from pramaan.notes import add_note
from pramaan.outbox import send
from pramaan.queue import SpotCheckIncomplete, approve_batch, batch_seed, clear_queue
from pramaan.schemas import Application
from pramaan.search import delete_filter, save_filter
from pramaan.seal import seal_html, verify_sealed

from .ctx import Ctx
from .views_case2 import letter_draft, sources


def feedback(ctx: Ctx, app_id: str, finding_id: str, verdict: str, note: str = "") -> dict:
    f = next(f for f in ctx.result(app_id).findings if f.finding_id == finding_id)
    with AuditLog(ctx.db) as log:
        record_feedback(ctx.db, f, verdict, ctx.user, note, log)
    return {"finding_id": finding_id, "verdict": verdict}


def note(ctx: Ctx, app_id: str, text: str, finding_id: str | None = None) -> dict:
    return add_note(ctx.db, app_id, ctx.user, text, finding_id)


def assign(ctx: Ctx, app_id: str, officer: str) -> dict:
    r = ctx.result(app_id)
    due = due_date(r, ctx.today, ctx.settings())
    with AuditLog(ctx.db) as log:
        h = record_assignment(log, ctx.user, app_id, officer, due)
    return {"app_id": app_id, "officer": officer, "due_by": due.isoformat(), "audit_hash": h[:12]}


def seal_issue(ctx: Ctx, app_id: str, include: list[str] | None = None, text: str | None = None) -> dict:
    letter = text or letter_draft(ctx, app_id, include)["text"]
    os.makedirs(os.path.join(ctx.out, "letters"), exist_ok=True)
    with AuditLog(ctx.db) as log:
        issued = save_final(log, ctx.user, app_id, letter, outbox=ctx.outbox)          # issues the letter: 7-day appeal window starts
        sealed = seal_html(to_html(letter, [], ctx.lang, annex_section=False), app_id, log, kind="letter of deficiency")
        rows = log.rows(app_id)
    sha = hashlib.sha256(sealed.encode()).hexdigest()[:12]
    path = os.path.join(ctx.out, "letters", f"{app_id}_{sha}.html")
    open(path, "w", encoding="utf-8").write(sealed)
    return {"app_id": app_id, "file": os.path.basename(path), "issued_hash": issued[:12], "seal": verify_sealed(sealed, ctx.db),
            "appeal": appeal_status(rows, app_id, ctx.today), "text": letter}


def verify(ctx: Ctx, html: str | None = None, file: str | None = None) -> dict:
    text = html if html is not None else open(os.path.join(ctx.out, "letters", os.path.basename(file)), encoding="utf-8").read()
    msg = verify_sealed(text, ctx.db)
    return {"result": msg, "valid": msg.startswith("VALID")}


def batch_approve(ctx: Ctx, opened: list[str]) -> dict:
    q = clear_queue(list(ctx.results().values()))
    seed = batch_seed([r.app_id for r in q], ctx.today.isoformat())
    try:
        with AuditLog(ctx.db) as log:
            hashes = approve_batch(log, ctx.user, q, set(opened), seed)
    except SpotCheckIncomplete as e:
        return {"approved": [], "error": str(e)}
    for r in q:                                                    # Letters of Approval are drafted into the MOCK outbox
        send("loa_draft", f"institute of {r.app_id}", {"app_id": r.app_id}, key=f"loa-{r.app_id}-{ctx.today}", outbox=ctx.outbox)
    return {"approved": [r.app_id for r in q], "audit_hashes": [h[:12] for h in hashes]}


def reask_sources(ctx: Ctx, app_id: str) -> dict:
    r, m = ctx.result(app_id), ctx.manifest(app_id)
    app, recs = Application(**m), load_records()
    got = [v for d in r.documents for v in verify_document(d, app, recs)]
    with AuditLog(ctx.db) as log:
        log.append(ctx.user["id"], ctx.user["role"], "sources asked again", app_id,
                   {"answers": [{"doc_id": v.doc_id, "status": v.status, "source": v.source} for v in got]})
    return sources(ctx, app_id)


def case_zip(ctx: Ctx, app_id: str, copy: str = "officer") -> str:
    return export_case(app_id, ctx.out, ctx.db, ctx.apps, os.path.join(ctx.out, f"{app_id}_{copy}_case.zip"), institute_copy=copy == "institute")


def evc_report(ctx: Ctx, app_id: str, answers: dict) -> dict:
    r, m = ctx.result(app_id), ctx.manifest(app_id)
    rows = evc_items(r, ctx.records().get(m.get("permanent_id")), ctx.today, lang=ctx.lang)
    li = "".join(f"<tr><td>{H.escape(i['what'])}</td><td>{H.escape(i['why'])}</td><td>{H.escape(answers.get(str(k), 'Not seen'))}</td></tr>"
                 for k, i in enumerate(rows))
    body = (f"<!doctype html><meta charset='utf-8'><title>Visit report {app_id}</title><body style='font-family:sans-serif'>"
            f"<h2>Expert Visit Committee report: {app_id}</h2><table border=1 cellpadding=6><tr><th>Check</th><th>The file says</th>"
            f"<th>Committee answer</th></tr>{li}</table></body>")
    with AuditLog(ctx.db) as log:
        sealed = seal_html(body, app_id, log, kind="EVC pack")
    os.makedirs(os.path.join(ctx.out, "letters"), exist_ok=True)
    path = os.path.join(ctx.out, "letters", f"{app_id}_evc_{hashlib.sha256(sealed.encode()).hexdigest()[:12]}.html")
    open(path, "w", encoding="utf-8").write(sealed)
    return {"file": os.path.basename(path), "seal": verify_sealed(sealed, ctx.db)}


def filter_save(ctx: Ctx, name: str, query: str, filters: dict) -> dict:
    save_filter(ctx.db, ctx.user["id"], name, query, filters)
    return {"saved": name}


def filter_delete(ctx: Ctx, name: str) -> dict:
    return {"deleted": delete_filter(ctx.db, ctx.user["id"], name)}
