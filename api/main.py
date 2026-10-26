"""Pramaan web API (WK26). Thin FastAPI layer: every route calls api/views_*.py or api/actions.py, which call pramaan/.
  uvicorn api.main:app --port 8600          (from the repo root, .venv active; reads output/ written by the pipeline)
Query parameters on every read: lang (en, hi, ...), role (regulation_bureau, scrutiny, evc, shc, ec, sac). Actions take JSON."""
from __future__ import annotations

import io
import os

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, Response

from . import actions, views_case as C, views_case2 as C2, views_global as G
from .ctx import ROLES, Ctx

app = FastAPI(title="Pramaan API", version="1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def ctx(lang: str = "en", role: str = "regulation_bureau", user: str | None = None) -> Ctx:
    c = Ctx(lang=lang, role=role if role in ROLES else "regulation_bureau")
    os.environ.setdefault("PRAMAAN_OUTBOX", c.outbox)
    if user:
        u = next((x for x in c.users() if x["id"] == user), None)
        if u:
            c.user = u
    return c


def guard(fn, *a, **k):
    try:
        return fn(*a, **k)
    except KeyError as e:
        raise HTTPException(404, f"not found: {e}")


@app.get("/api/health")
def health():
    c = Ctx()
    return {"ok": True, "cases": len(c.results()), "today": c.today.isoformat(), "mode": "live"}


@app.get("/api/officers")
def officers():
    return [{"id": u["id"], "name": u["name"], "regions": u.get("regions", [])} for u in Ctx().users() if u.get("role") == "scrutiny_officer"]


@app.get("/api/roles")
def roles(lang: str = "en"):
    c = ctx(lang)
    return [{"id": k, "name": c.tr(v["name"])} for k, v in ROLES.items()]


@app.get("/api/queue")
def queue(lang: str = "en", role: str = "regulation_bureau", lane: str | None = None, due: str | None = None, sort: str = "priority"):
    return C.queue(ctx(lang, role), lane, due, sort)


@app.get("/api/cases/{app_id}")
def case(app_id: str, lang: str = "en", role: str = "regulation_bureau"):
    return guard(C.case, ctx(lang, role), app_id)


@app.get("/api/cases/{app_id}/checklist")
def checklist(app_id: str, lang: str = "en"):
    return guard(C.checklist, ctx(lang), app_id)


@app.get("/api/cases/{app_id}/sources")
def sources(app_id: str, lang: str = "en"):
    return guard(C2.sources, ctx(lang), app_id)


@app.get("/api/cases/{app_id}/sources/{row}/preview")
def preview(app_id: str, row: int, lang: str = "en"):
    return guard(C2.preview, ctx(lang), app_id, row)


@app.post("/api/cases/{app_id}/sources/reask")
def reask(app_id: str, lang: str = "en", user: str | None = None):
    return guard(actions.reask_sources, ctx(lang, user=user), app_id)


@app.get("/api/cases/{app_id}/changes")
def changes(app_id: str, lang: str = "en"):
    return guard(C2.changes, ctx(lang), app_id)


@app.get("/api/cases/{app_id}/resubmission")
def resubmission(app_id: str, lang: str = "en"):
    return guard(C2.resubmission, ctx(lang), app_id)


@app.get("/api/cases/{app_id}/notes")
def notes(app_id: str):
    from pramaan.notes import list_notes
    return list_notes(ctx().db, app_id)


@app.post("/api/cases/{app_id}/notes")
def add_note(app_id: str, body: dict = Body(...)):
    return actions.note(ctx(user=body.get("user")), app_id, body["text"], body.get("finding_id"))


@app.post("/api/cases/{app_id}/feedback")
def feedback(app_id: str, body: dict = Body(...)):
    if body.get("verdict") not in ("correct", "false alarm"):
        raise HTTPException(422, "verdict must be 'correct' or 'false alarm'")
    return guard(actions.feedback, ctx(user=body.get("user")), app_id, body["finding_id"], body["verdict"], body.get("note", ""))


@app.post("/api/cases/{app_id}/assign")
def assign(app_id: str, body: dict = Body(...)):
    return guard(actions.assign, ctx(user=body.get("user")), app_id, body["officer"])


@app.get("/api/cases/{app_id}/letter")
def letter(app_id: str, lang: str = "en", include: list[str] | None = Query(None)):
    inc = [x for v in include for x in v.split(",") if x] if include else None      # include=a,b or include=a&include=b
    return guard(C2.letter_draft, ctx(lang), app_id, inc)


@app.post("/api/cases/{app_id}/letter/seal")
def seal(app_id: str, body: dict = Body(...)):
    return guard(actions.seal_issue, ctx(body.get("lang", "en"), user=body.get("user")), app_id, body.get("include"), body.get("text"))


@app.get("/api/cases/{app_id}/zip")
def case_zip(app_id: str, copy: str = "officer"):
    p = guard(actions.case_zip, ctx(), app_id, copy)
    return FileResponse(p, filename=os.path.basename(p), media_type="application/zip")


@app.get("/api/cases/{app_id}/evc")
def evc(app_id: str, lang: str = "en"):
    return guard(G.evc, ctx(lang, "evc"), app_id)


@app.post("/api/cases/{app_id}/evc/report")
def evc_report(app_id: str, body: dict = Body(...)):
    return guard(actions.evc_report, ctx(body.get("lang", "en"), "evc", body.get("user")), app_id, body.get("answers", {}))


@app.get("/api/letters")
def letters(lang: str = "en"):
    return G.letters(ctx(lang))


@app.get("/api/letters/file/{name}", response_class=HTMLResponse)
def letter_file(name: str):
    p = os.path.join(ctx().out, "letters", os.path.basename(name))
    if not os.path.exists(p):
        raise HTTPException(404, "no such letter")
    return open(p, encoding="utf-8").read()


@app.post("/api/letters/verify")
def verify(body: dict = Body(...)):
    return actions.verify(ctx(), body.get("html"), body.get("file"))


@app.get("/api/outbox")
def outbox(lang: str = "en"):
    return G.outbox(ctx(lang))


@app.get("/api/calendar")
def calendar(lang: str = "en"):
    return G.calendar(ctx(lang))


@app.get("/api/appeals")
def appeals(lang: str = "en"):
    return G.appeals(ctx(lang))


@app.get("/api/analytics")
def analytics(lang: str = "en", role: str = "regulation_bureau"):
    return G.analytics(ctx(lang, role))


@app.get("/api/search")
def search(q: str = "", lang: str = "en", region: str | None = None, lane: str | None = None, user: str | None = None):
    return G.search(ctx(lang, user=user), q, region, lane)


@app.post("/api/search/filters")
def save_filter(body: dict = Body(...)):
    return actions.filter_save(ctx(user=body.get("user")), body["name"], body.get("query", ""), body.get("filters", {}))


@app.delete("/api/search/filters/{name}")
def delete_filter(name: str, user: str | None = None):
    return actions.filter_delete(ctx(user=user), name)


@app.get("/api/batch")
def batch(lang: str = "en"):
    return G.batch(ctx(lang))


@app.post("/api/batch/approve")
def batch_approve(body: dict = Body(...)):
    return actions.batch_approve(ctx(user=body.get("user")), body.get("opened", []))


@app.get("/api/docs/{name}")
def policy(name: str):
    if name not in ("privacy", "terms", "accessibility"):
        raise HTTPException(404, "no such document")
    return G.policy(ctx(), name)


def _png(img) -> Response:
    buf = io.BytesIO(); img.save(buf, format="PNG", optimize=True)
    return Response(buf.getvalue(), media_type="image/png", headers={"Cache-Control": "max-age=3600"})


@app.get("/api/documents/{app_id}/{doc_id}/page/{n}.png")
def page_image(app_id: str, doc_id: str, n: int):
    from .images import page
    img = guard(page, ctx(), app_id, doc_id, n)
    if img is None:
        raise HTTPException(404, "page not readable")
    return _png(img)


@app.get("/api/documents/{app_id}/{doc_id}/heatmap/{n}.png")
def heatmap(app_id: str, doc_id: str, n: int):
    p = os.path.join(ctx().out, "heatmaps", f"{doc_id}_p{n}.png")
    if not os.path.exists(p):
        raise HTTPException(404, "no heatmap for this page")
    return FileResponse(p, media_type="image/png")


@app.get("/api/photos/{app_id}/{name}")
def photo(app_id: str, name: str):
    m = ctx().manifest(app_id)
    p = next((x for x in m.get("photos", []) if os.path.basename(x) == name), None)
    if not p or not os.path.exists(p):
        raise HTTPException(404, "no such photo")
    return FileResponse(p, media_type="image/jpeg")
