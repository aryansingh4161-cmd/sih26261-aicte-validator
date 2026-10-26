"""Cross-case views for the web API (WK26): letters, outbox, calendar, appeals, analytics (role scope), search, batch approve,
Expert Visit Committee pack, policy documents. Built from pramaan/ only."""
from __future__ import annotations

import glob
import json
import os
import statistics
from collections import Counter
from datetime import date, timedelta

from pramaan import analytics as A
from pramaan.appeal import status as appeal_status
from pramaan.evc_pack import items as evc_items
from pramaan.expiry import days_left, expiries
from pramaan.feedback import false_alarm_rate
from pramaan.geo import geocode
from pramaan.outbox import log as outbox_log
from pramaan.photo_check import km
from pramaan.queue import batch_seed, clear_queue, spot_sample
from pramaan.search import list_filters, search as engine_search

from .ctx import DOC_LABEL, LANE_LABEL, ROLES, Ctx
from .views_case import _audit, stage_of


def letters(ctx: Ctx) -> dict:
    res, mans, rows = ctx.results(), ctx.manifests(), _audit(ctx)
    box = outbox_log(ctx.outbox)
    out = []
    for r in rows:
        if r["action"] == "letter of deficiency finalised":
            sealed = sorted(glob.glob(os.path.join(ctx.out, "letters", f"{r['app_id']}_*.html")))
            sent = any(b["kind"] == "lod_issued" and r["app_id"] in b["subject"] for b in box)
            out.append({"kind": "Letter of Deficiency", "app_id": r["app_id"], "institute": mans.get(r["app_id"], {}).get("declared", {}).get("institute_name"),
                        "status": "sent" if sent else "sealed", "hash": "#" + json.loads(r["detail"]).get("sha256", "")[:6], "date": r["ts"][:10],
                        "file": os.path.basename(sealed[-1]) if sealed else None})
        elif r["action"].startswith("decision: approve for next step"):
            out.append({"kind": "Letter of Approval", "app_id": r["app_id"], "institute": mans.get(r["app_id"], {}).get("declared", {}).get("institute_name"),
                        "status": "sent", "hash": "#" + r["hash"][:6], "date": r["ts"][:10], "file": None})
    done = {x["app_id"] for x in out if x["kind"] == "Letter of Deficiency"}
    for a, r in res.items():
        if a not in done and any(f.lane == "return_for_rectification" for f in r.findings):
            out.append({"kind": "Letter of Deficiency", "app_id": a, "institute": mans.get(a, {}).get("declared", {}).get("institute_name"),
                        "status": "draft", "hash": None, "date": ctx.today.isoformat(), "file": None})
    for x in out:
        x["kind_label"] = ctx.tr(x["kind"])
        x["status_label"] = ctx.tr({"draft": "Draft", "sealed": "Sealed, not sent", "sent": "Sent"}[x["status"]])
    out.sort(key=lambda x: (x["date"], x["app_id"]), reverse=True)
    n = Counter(x["status"] for x in out)
    week = sum(1 for x in out if x["status"] != "draft" and (ctx.today - date.fromisoformat(x["date"])).days < 7)
    return {"letters": out, "counts": dict(n), "headline": ctx.tr(f"{n.get('draft', 0)} drafts to finish, {week} sealed this week.")}


def outbox(ctx: Ctx) -> list[dict]:
    return [{**b, "subject": ctx.tr(b["subject"])} for b in outbox_log(ctx.outbox)][::-1]


def calendar(ctx: Ctx, month: str | None = None) -> dict:
    res, rows = ctx.results(), _audit(ctx)
    ev = []
    for e in expiries(list(res.values())):
        ev.append({"date": e["expires"], "kind": "expiry", "app_id": e["app_id"], "title": ctx.tr(f"{DOC_LABEL.get(e['doc_type'], e['doc_type'])} expires"),
                   "lane": "return_for_rectification" if days_left(e, ctx.today) < 0 else "human_review"})
    for a, r in res.items():
        from pramaan.case_timeline import case_summary
        s = case_summary(a, ctx.out, ctx.db, ctx.apps, ctx.today)
        if r.lane != "clear":
            ev.append({"date": s["due_by"], "kind": "due", "app_id": a, "title": ctx.tr(f"{a} due"), "lane": r.lane,
                       "detail": ctx.tr(r.findings[0].title) if r.findings else ""})
        ap = appeal_status([x for x in rows if x["app_id"] == a], a, ctx.today)
        if ap:
            ev.append({"date": ap["deadline"], "kind": "appeal", "app_id": a, "title": ctx.tr("Appeal window closes"), "lane": "not_automated",
                       "detail": f"{a}"})
    clear = clear_queue(list(res.values()))
    if clear:
        ev.append({"date": (ctx.today + timedelta(days=3)).isoformat(), "kind": "spot", "app_id": None, "lane": "clear",
                   "title": ctx.tr("Spot check"), "detail": ctx.tr(f"{len(clear)} clear files before batch approval")})
    ev.sort(key=lambda e: e["date"])
    nxt = [e for e in ev if 0 <= (date.fromisoformat(e["date"]) - ctx.today).days <= 7]
    return {"events": ev, "next7": nxt, "headline": ctx.tr(f"{len(nxt)} things need you this week."),
            "note": ctx.tr("Institutes get an email from the outbox 30 days before a certificate expires."), "today": ctx.today.isoformat()}


def appeals(ctx: Ctx) -> dict:
    rows, mans = _audit(ctx), ctx.manifests()
    out = []
    for a in sorted({r["app_id"] for r in rows if r["action"] == "letter of deficiency finalised"}):
        ap = appeal_status([x for x in rows if x["app_id"] == a], a, ctx.today)
        out.append({"appeal": "APL-" + a.split("-")[1], "app_id": a, "institute": mans.get(a, {}).get("declared", {}).get("institute_name"),
                    "against": ctx.tr("Letter of Deficiency"), "filed": ap["issued_on"], "days_left": ap["days_left"],
                    "state": ap["state"], "state_label": ctx.tr({"open": "Window open", "window closed": "Window closed",
                                                                 "closed (read-only)": "Decided: closed"}[ap["state"]]), "clause": ap["clause"]})
    n_open = sum(1 for x in out if x["state"] == "open")
    soon = sum(1 for x in out if x["state"] == "open" and x["days_left"] <= 1)
    return {"appeals": out, "open": n_open, "headline": ctx.tr(f"{n_open} open." + (" One window closes tomorrow." if soon == 1 else
                                                                                       f" {soon} windows close within a day." if soon else "")),
            "note": ctx.tr("Appeals go to the Standing Appellate Committee within 7 days (Handbook cl. 2.24). Each appeal links to its sealed letter and the case ZIP for RTI.")}


def analytics(ctx: Ctx) -> dict:
    res, mans, rows = ctx.results(), ctx.manifests(), _audit(ctx)
    role, recs = ROLES[ctx.role], ctx.records()
    scope = list(res.values())
    if role["stage"] != "all":
        scope = [r for r in scope if role["stage"] in stage_of(ctx, r, [x for x in rows if x["app_id"] == r.app_id],
                                                               recs.get(mans.get(r.app_id, {}).get("permanent_id")))]
    lanes = A.lane_split(scope)
    fa = false_alarm_rate(ctx.db)
    n_fb, n_fa = sum(v["n"] for v in fa.values()), sum(v["false_alarms"] for v in fa.values())
    weeks: dict = {}
    for r in scope:
        wk = date.fromisoformat(mans[r.app_id]["submitted_on"]).isocalendar()[1] if r.app_id in mans else 0
        weeks.setdefault(wk, Counter())[r.lane] += 1
    regions = A.by_region(scope, mans)
    reg_rows = []
    for g, v in regions.items():
        rs = [r for r in scope if mans.get(r.app_id, {}).get("declared", {}).get("region") == g]
        reg_rows.append({"region": g, "files": v["applications"], "clear": sum(r.lane == "clear" for r in rs),
                         "review": sum(r.lane == "human_review" for r in rs), "returned": sum(r.lane == "return_for_rectification" for r in rs),
                         "median_days": A.median_processing_days(rs, mans)})
    eyebrow = {"regulation_bureau": "Regulation Bureau · my numbers", "scrutiny": "Scrutiny / Re-Scrutiny Committee · files at your stage",
               "evc": "Expert Visit Committee · files at your stage", "shc": "Standing Hearing Committee · files at your stage",
               "ec": "Executive Committee · leadership view · all regions", "sac": "Standing Appellate Committee · files at your stage"}[ctx.role]
    return {"eyebrow": ctx.tr(eyebrow), "headline": ctx.tr(f"{len(scope)} files checked so far this season."), "synthetic": True,
            "kpis": [{"value": f"{A.median_processing_days(scope, mans) or 0:g} days", "label": ctx.tr("median time to first check (synthetic dates)")},
                     {"value": f"{round(100 * lanes.get('return_for_rectification', 0) / max(1, len(scope)))}%", "label": ctx.tr("returned for rectification")},
                     {"value": f"{round(100 * n_fa / n_fb) if n_fb else 0}%", "label": ctx.tr("findings marked \"false alarm\" by officers")},
                     {"value": "0", "label": ctx.tr("files decided by the AI alone")}],
            "weeks": [{"week": f"W{w}", **{k: c.get(k, 0) for k in ("clear", "human_review", "return_for_rectification")}} for w, c in sorted(weeks.items())],
            "top": [{"title": ctx.tr(tt), "count": n} for tt, n in A.top_deficiencies(scope, 5)], "regions": reg_rows,
            "note": ctx.tr("All numbers on this page are synthetic demo data. The AI never decides a file on its own: every lane is a suggestion an officer confirms.")}


def search(ctx: Ctx, q: str, region: str | None = None, lane: str | None = None) -> dict:
    hits = engine_search(q, {"region": region, "lane": lane}, ctx.out, ctx.apps, ctx.lang)
    mans, res = ctx.manifests(), ctx.results()
    rows = [{"app_id": h["app_id"], "institute": mans.get(h["app_id"], {}).get("declared", {}).get("institute_name"), "why": h["reason"],
             "lane": res[h["app_id"]].lane, "lane_label": ctx.tr(LANE_LABEL[res[h["app_id"]].lane]), "score": h["score"]} for h in hits if h["app_id"] in res]
    saved = []
    try:
        for f in list_filters(ctx.db, ctx.user["id"]):
            saved.append({**f, "count": len(engine_search(f["query"], f["filters"], ctx.out, ctx.apps))})
    except Exception:
        pass
    return {"query": q, "rows": rows, "saved": saved,
            "note": ctx.tr("Search finds Permanent Id, institute name (even with a typo), file, rule, document, region, lane, officer and status words like \"expired\", \"missing\" or \"serial\".")}


def batch(ctx: Ctx) -> dict:
    q = clear_queue(list(ctx.results().values()))
    ids, mans = [r.app_id for r in q], ctx.manifests()
    seed = batch_seed(ids, ctx.today.isoformat())
    return {"files": [{"app_id": a, "institute": mans.get(a, {}).get("declared", {}).get("institute_name")} for a in ids],
            "spot": spot_sample(ids, seed) if ids else [], "seed": seed,
            "note": ctx.tr("Before a batch, Pramaan picks one file at random for you to open. This keeps \"clear\" honest.")}


def evc(ctx: Ctx, app_id: str) -> dict:
    r, m = ctx.result(app_id), ctx.manifest(app_id)
    rec = ctx.records().get(m.get("permanent_id"))
    rows = [{"check": i["what"], "file_says": i["why"], "clause": i["clause"], "photos": len(m.get("photos", []))}
            for i in evc_items(r, rec, ctx.today, lang=ctx.lang)]
    dec, hit = m.get("declared", {}), geocode(m.get("declared", {}).get("address"))
    dist = km((float(dec["latitude"]), float(dec["longitude"])), (hit["latitude"], hit["longitude"])) if hit and dec.get("latitude") is not None else None
    return {"app_id": app_id, "institute": dec.get("institute_name"), "place": dec.get("address"), "rows": rows,
            "map": {"declared": [dec.get("latitude"), dec.get("longitude")], "geocoded": [hit["latitude"], hit["longitude"]] if hit else None,
                    "distance_km": round(dist, 2) if dist is not None else None, "demo": True},
            "photos": [f"/api/photos/{app_id}/{os.path.basename(p)}" for p in m.get("photos", [])],
            "note": ctx.tr("Each photo keeps its time and place. The report is sealed like a letter when you submit.")}


def policy(ctx: Ctx, name: str) -> dict:
    p = {"privacy": "docs/PRIVACY.md", "terms": "docs/TERMS.md", "accessibility": "docs/ACCESSIBILITY.md"}[name]
    return {"name": name, "markdown": open(p, encoding="utf-8").read()}
