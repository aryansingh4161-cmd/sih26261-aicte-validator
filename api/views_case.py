"""Case-level views for the web API (WK26). Plain JSON built from pramaan/ results; the UI shows them as they are.
queue, case, checklist, verification (+ preview), changes since last year, resubmission, timeline, notes, letter draft."""
from __future__ import annotations

import os
from datetime import date

from pramaan.appeal import status as appeal_status
from pramaan.audit import AuditLog
from pramaan.case_timeline import build_timeline, case_summary
from pramaan.checklist import tick
from pramaan.evc_pack import items as evc_items
from pramaan.feedback import rows as feedback_rows
from pramaan.notes import list_notes
from pramaan.trust import app_score

from .ctx import CATEGORY_LABEL, DOC_LABEL, LANE_LABEL, ROLES, Ctx, clean_reason, due_word, place

SEV = {"high": 3, "medium": 2, "low": 1, "info": 0}
LANE_RANK = {"return_for_rectification": 3, "human_review": 2, "info": 1, "clear": 0}


def _feedback(ctx: Ctx) -> dict:
    try:
        last = {}
        for r in feedback_rows(ctx.db):
            last[r["finding_id"]] = r
        return last
    except Exception:
        return {}


def _audit(ctx: Ctx, app_id: str | None = None) -> list[dict]:
    with AuditLog(ctx.db) as log:
        return log.rows(app_id)


def stage_of(ctx: Ctx, r, rows: list[dict], record: dict | None) -> set[str]:
    """DESIGNED mapping of a demo case onto the Handbook stages (only used to pick each role's default queue)."""
    st = {"all"}
    acts = {x["action"] for x in rows}
    if r.lane == "human_review":
        st.add("scrutiny")
    if evc_items(r, record, ctx.today):
        st.add("evc")
    if "letter of deficiency finalised" in acts:
        st.add("shc")
    ap = appeal_status(rows, r.app_id, ctx.today)
    if ap and ap["state"] == "open":
        st.add("sac")
    if r.lane == "clear" or any(a.startswith("decision") for a in acts):
        st.add("ec")
    return st


def queue_item(ctx: Ctx, r, m: dict, rows: list[dict]) -> dict:
    d = m.get("declared", {})
    s = case_summary(r.app_id, ctx.out, ctx.db, ctx.apps, ctx.today, lang=ctx.lang)
    top = max(r.findings, key=lambda f: (LANE_RANK.get(f.lane, 0), SEV.get(f.severity, 0)), default=None)
    due = date.fromisoformat(s["due_by"])
    return {"app_id": r.app_id, "institute": d.get("institute_name"), "permanent_id": m.get("permanent_id"),
            "category": ctx.tr(CATEGORY_LABEL.get(r.category, r.category)), "academic_year": ctx.year(r.academic_year), "place": place(d.get("address")),
            "region": d.get("region"), "officer": ctx.name(s["assigned_officer"]), "trust": s["trust_score"], "lane": r.lane,
            "lane_label": ctx.tr(LANE_LABEL[r.lane]), "priority": round(r.priority, 2), "due_by": s["due_by"],
            "due_word": ctx.tr(due_word(due, ctx.today)), "headline": ctx.tr(top.title) if top else ctx.tr("All checks passed. Spot check due"),
            "headline_lane": top.lane if top else "clear"}


def queue(ctx: Ctx, lane: str | None = None, due: str | None = None, sort: str = "priority") -> dict:
    res, mans, recs = ctx.results(), ctx.manifests(), ctx.records()
    rows_all = _audit(ctx)
    role = ROLES.get(ctx.role, ROLES["regulation_bureau"])
    items = []
    for a, r in res.items():
        rows = [x for x in rows_all if x["app_id"] == a]
        if role["stage"] not in stage_of(ctx, r, rows, recs.get(mans.get(a, {}).get("permanent_id"))):
            continue
        items.append(queue_item(ctx, r, mans.get(a, {}), rows))
    n_role = len(items)
    if lane:
        items = [i for i in items if i["lane"] == lane]
    if due == "today":
        items = [i for i in items if i["due_by"] <= ctx.today.isoformat()]
    elif due == "week":
        items = [i for i in items if (date.fromisoformat(i["due_by"]) - ctx.today).days <= 7]
    key = {"priority": lambda i: (-i["priority"], i["due_by"]), "due": lambda i: (i["due_by"], -i["priority"]),
           "trust": lambda i: (i["trust"], i["due_by"])}.get(sort, lambda i: -i["priority"])
    items.sort(key=key)
    return {"role": {"id": ctx.role, **{k: ctx.tr(v) if k in ("name", "action") else v for k, v in role.items()}},
            "summary": ctx.tr(role["summary"].format(n=n_role)), "count": n_role, "items": items}


def _doc_status(r, d) -> str:
    if d.doc_type == "unclassified" or (d.is_scanned and not d.blocks):
        return "not_automated"
    lanes = [f.lane for f in r.findings if f.doc_id == d.doc_id and f.lane != "info"]
    return max(lanes, key=lambda l: LANE_RANK[l]) if lanes else "clear"


def _page_url(app_id, doc_id, n, kind="page"):
    return f"/api/documents/{app_id}/{doc_id}/{kind}/{n}.png"


TL_NOTE = {"derived from the manifest": "From the application"}


def timeline(ctx: Ctx, app_id: str) -> list[dict]:
    """build_timeline with display names: officer names instead of ids, plain notes, and `real` = a real audit-log block."""
    out = []
    for e in build_timeline(app_id, ctx.out, ctx.db, ctx.apps, ctx.today):
        note = e["note"] or ""
        if note.startswith("lane "):
            note = LANE_LABEL.get(note[5:], note[5:])
        note = TL_NOTE.get(note, note)
        out.append({**e, "actor": ctx.name(e["actor"]), "note": ctx.tr(note), "real": e["hash"] != "-",
                    "refs": [ctx.name(x) if str(x).startswith("officer.") else x for x in e["refs"]]})
    return out


def _group(f) -> str:
    """Where a finding shows on the Evidence tab: a photo, one document, or the whole file (cross-checks, missing documents)."""
    if f.source == "photo" or any((e.doc_id or "").startswith("photo:") for e in f.evidence):
        return "photo"
    if f.source == "crosscheck" or not (f.doc_id or any(e.doc_id for e in f.evidence)):
        return "file"
    return "doc"


def case(ctx: Ctx, app_id: str) -> dict:
    r, m = ctx.result(app_id), ctx.manifest(app_id)
    rows = _audit(ctx, app_id)
    s = case_summary(app_id, ctx.out, ctx.db, ctx.apps, ctx.today, lang=ctx.lang)
    ck = tick(r, lang=ctx.lang)
    fb = _feedback(ctx)
    docs = []
    for d in r.documents:
        heat = [n for n in range(1, max(1, d.pages) + 1) if ctx.heatmap(d.doc_id, n)]
        docs.append({"doc_id": d.doc_id, "label": ctx.tr(DOC_LABEL.get(d.doc_type, d.doc_type)), "doc_type": d.doc_type, "kind": "document",
                     "pages": max(1, d.pages), "status": _doc_status(r, d), "scanned": d.is_scanned,
                     "page_urls": [_page_url(app_id, d.doc_id, n) for n in range(1, max(1, d.pages) + 1)],
                     "heatmap_urls": {n: _page_url(app_id, d.doc_id, n, "heatmap") for n in heat}})
    photos = m.get("photos", [])
    for k, ph in enumerate(photos, 1):                     # photos are documents too (WK27 D2)
        pid = f"photo:{os.path.basename(ph)}"
        lanes = [f.lane for f in r.findings if f.lane != "info" and any(e.doc_id == pid for e in f.evidence)]
        docs.append({"doc_id": pid, "label": ctx.tr("Campus photo") + (f" {k}" if len(photos) > 1 else ""), "doc_type": "photo", "kind": "photo",
                     "pages": 1, "status": max(lanes, key=lambda l: LANE_RANK[l]) if lanes else "clear", "scanned": False,
                     "page_urls": [f"/api/photos/{app_id}/{os.path.basename(ph)}"], "heatmap_urls": {}})
    findings = [{"finding_id": f.finding_id, "rule_id": f.rule_id, "title": ctx.tr(f.title), "reason": ctx.tr(clean_reason(f.reason)), "lane": f.lane,
                 "severity": f.severity, "source": f.source, "doc_id": f.doc_id, "clause": f.aph_clause, "clause_verified": f.clause_verified,
                 "evidence": [{"doc_id": e.doc_id, "page": e.page, "bbox": e.bbox.model_dump() if e.bbox else None} for e in f.evidence],
                 "group": _group(f), "feedback": (fb.get(f.finding_id) or {}).get("verdict")}
                for f in sorted(r.findings, key=lambda f: (-LANE_RANK.get(f.lane, 0), -SEV.get(f.severity, 0)))]
    tamper = [f for f in findings if f["rule_id"] == "F-TAMPER"]
    sc = app_score(r, ctx.lang)
    return {"app_id": app_id, "institute": m.get("declared", {}).get("institute_name"), "permanent_id": m.get("permanent_id"),
            "category": ctx.tr(CATEGORY_LABEL.get(r.category, r.category)), "academic_year": ctx.year(r.academic_year),
            "place": place(m.get("declared", {}).get("address")), "lane": r.lane, "lane_label": ctx.tr(LANE_LABEL[r.lane]),
            "trust": {"score": sc["score"], "reasons": sc["reasons"], "label": sc["label"]},
            "checklist": {k: sum(x["status"] == s_ for x in ck) for k, s_ in (("passed", "green"), ("to_check", "amber"),
                                                                              ("to_return", "red"), ("not_automated", "grey"))},
            "assigned": ctx.name(s["assigned_officer"]), "due_by": s["due_by"], "due_word": ctx.tr(due_word(date.fromisoformat(s["due_by"]), ctx.today)),
            "appeal": s["appeal"], "notes_count": len(list_notes(ctx.db, app_id)), "documents": docs, "findings": findings,
            "tamper": {"ran": any(d["scanned"] for d in docs), "found": bool(tamper),
                       "text": ctx.tr("Tamper check: possible alteration, needs human review") if tamper else
                       ctx.tr("Tamper check: no edit marks found") if any(d["scanned"] for d in docs) else
                       ctx.tr("Tamper check: text PDFs, checked for edits in the file structure")},
            "timeline": timeline(ctx, app_id), "action": ctx.tr(ROLES[ctx.role]["action"])}


def notes(ctx: Ctx, app_id: str) -> list[dict]:
    """Internal notes with display names (author and @mentions), never raw user ids (WK27 A4)."""
    out = []
    for n in list_notes(ctx.db, app_id):
        text = n["text"]
        for m in n.get("mentions") or []:
            text = text.replace(f"@{m}", f"@{ctx.name(m)}")
        out.append({**n, "author": ctx.name(n["author"]), "text": text})
    return out


def checklist(ctx: Ctx, app_id: str) -> list[dict]:
    r = ctx.result(app_id)
    fb, byid = _feedback(ctx), {f.finding_id: f for f in r.findings}
    word = {"green": "Passed", "amber": "To check", "red": "To return", "grey": "Not automated"}
    out = []
    for i, row in enumerate(tick(r, lang=ctx.lang), 1):
        fs = [byid[x] for x in row.get("finding_ids", []) if x in byid]
        src = ("Officer checks by hand" if row["status"] == "grey" else "Map check (demo adapter)" if row["id"] == "R06" else
               next((f"{v.source.replace('MOCK ', '')} (demo adapter)" for f in fs if f.source == "verification" for v in r.verifications
                     if v.doc_id == f.doc_id and f.rule_id == f"V-{v.method}"), None) or
               ("Cross-check" if any(f.source == "crosscheck" for f in fs) else "AICTE records (demo adapter)" if row["id"] == "R02" else "Document text"))
        verdicts = [fb[f.finding_id]["verdict"] for f in fs if f.finding_id in fb]
        out.append({"n": i, "id": row["id"], "ref": row.get("ref"), "item": row["item"], "status": row["status"], "status_label": ctx.tr(word[row["status"]]),
                    "found": ctx.plain(ctx.year(row["why"])), "source": ctx.tr(src), "finding_ids": [f.finding_id for f in fs], "officer": verdicts[-1] if verdicts else None})
    return out
